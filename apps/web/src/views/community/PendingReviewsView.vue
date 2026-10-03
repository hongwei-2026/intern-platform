<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import api from '@/api/client'
import LiaisonBubble from '@/components/LiaisonBubble.vue'
import LiaisonComposer from '@/components/LiaisonComposer.vue'
import type { ApplicationOut, CommunityOut } from '@/api/types'
import { formatDateTime, statusLabel } from '@/utils/statusLabel'

type Mode = 'student' | 'mentor' | 'committee'

type StudentRow = {
  user_id: number
  name: string
  email: string
  project_title: string
  application_id: number
  status: string
  ended: boolean
  case_kind?: string | null
  case_status?: string | null
}
type MentorRow = { user_id: number; name: string; email: string; projects: string[] }
type Msg = { id: number; sender_name: string; body: string; mine: boolean; created_at?: string | null }

const mode = ref<Mode>('student')
const community = ref<CommunityOut | null>(null)
const students = ref<StudentRow[]>([])
const mentors = ref<MentorRow[]>([])
const pickedStudent = ref<number | null>(null)
const pickedMentor = ref<number | null>(null)
const thread = ref<Msg[]>([])
const draft = ref('')
const finals = ref<ApplicationOut[]>([])
const finalNote = ref('')
const error = ref('')
const msg = ref('')
const endOpen = ref(false)
const termCode = ref('idle')
const termReason = ref('')
const termLinks = ref('')
const busy = ref(false)

const picked = computed(() => {
  if (mode.value === 'student') return students.value.find((s) => s.application_id === pickedStudent.value) || null
  if (mode.value === 'mentor') return mentors.value.find((m) => m.user_id === pickedMentor.value) || null
  return { name: '组委会' }
})
const studentNow = computed(() =>
  mode.value === 'student' ? students.value.find((s) => s.application_id === pickedStudent.value) || null : null,
)

async function loadPeople() {
  const { data: mine } = await api.get<CommunityOut[]>('/communities/admin-of')
  community.value = mine[0] || null
  if (!community.value) return
  const { data } = await api.get<{ students: StudentRow[]; mentors: MentorRow[] }>('/liaison/people', {
    params: { community_id: community.value.id },
  })
  students.value = data.students
  mentors.value = data.mentors
  if (!pickedStudent.value && students.value[0]) pickedStudent.value = students.value[0].application_id
  if (!pickedMentor.value && mentors.value[0]) pickedMentor.value = mentors.value[0].user_id
  const { data: inbox } = await api.get<ApplicationOut[]>('/applications/inbox')
  finals.value = inbox.filter((a) => a.status === 'community_final_review')
}

async function loadThread() {
  if (!community.value) return
  const channel = mode.value
  const peer =
    channel === 'student'
      ? students.value.find((s) => s.application_id === pickedStudent.value)?.user_id
      : channel === 'mentor'
        ? pickedMentor.value
        : undefined
  if (channel !== 'committee' && !peer) {
    thread.value = []
    return
  }
  const { data } = await api.get<Msg[]>('/liaison/thread', {
    params: {
      community_id: community.value.id,
      channel,
      peer_user_id: peer,
      application_id: channel === 'student' ? pickedStudent.value : undefined,
    },
  })
  thread.value = data
}

async function send(body: string) {
  if (!community.value || !body.trim()) return
  const student = students.value.find((s) => s.application_id === pickedStudent.value)
  if (mode.value === 'student' && !student) {
    error.value = '请先在左边点一位学生'
    return
  }
  if (mode.value === 'mentor' && !pickedMentor.value) {
    error.value = '请先在左边点一位导师'
    return
  }
  busy.value = true
  error.value = ''
  try {
    await api.post('/liaison', {
      community_id: community.value.id,
      channel: mode.value,
      peer_user_id:
        mode.value === 'student' ? student?.user_id : mode.value === 'mentor' ? pickedMentor.value : null,
      application_id: mode.value === 'student' ? student?.application_id : null,
      body,
    })
    draft.value = ''
    msg.value = mode.value === 'student' ? '通知已发给这位学生' : '已发送'
    await loadThread()
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : '发送失败'
  } finally {
    busy.value = false
  }
}

async function submitFinal(id: number) {
  if (!finalNote.value.trim()) return
  busy.value = true
  try {
    await api.post(`/applications/${id}/community-final`, { note: finalNote.value.trim() })
    msg.value = '结项材料已报送，组委会已自动接收'
    finalNote.value = ''
    await loadPeople()
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : '提交失败'
  } finally {
    busy.value = false
  }
}

async function endLiaison() {
  const student = students.value.find((s) => s.application_id === pickedStudent.value)
  if (!community.value || !student) return
  busy.value = true
  error.value = ''
  try {
    await api.post('/liaison/close', { community_id: community.value.id, application_id: student.application_id })
    msg.value = '已结束与这位学生的对接'
    endOpen.value = false
    await loadPeople()
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : '结束失败'
  } finally {
    busy.value = false
  }
}

async function askTerminate() {
  const student = students.value.find((s) => s.application_id === pickedStudent.value)
  if (!community.value || !student) return
  busy.value = true
  error.value = ''
  try {
    await api.post('/liaison/terminate', {
      community_id: community.value.id,
      application_id: student.application_id,
      reason_code: termCode.value,
      reason: termReason.value.trim(),
      evidence: termLinks.value.trim(),
    })
    msg.value = '已交给组委会查证，通过之前不能终止'
    termReason.value = ''
    termLinks.value = ''
    await loadPeople()
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : '提交失败'
  } finally {
    busy.value = false
  }
}

watch([mode, pickedStudent, pickedMentor], () => {
  void loadThread()
})

onMounted(() => {
  loadPeople().catch((e: unknown) => {
    error.value = e instanceof Error ? e.message : '加载失败'
  })
})
</script>

<template>
  <div class="desk">
    <div class="bar">
      <div class="modes">
        <button type="button" :class="{ on: mode === 'student' }" @click="mode = 'student'">通知学生</button>
        <button type="button" :class="{ on: mode === 'mentor' }" @click="mode = 'mentor'">对接导师</button>
        <button type="button" :class="{ on: mode === 'committee' }" @click="mode = 'committee'">对接组委会</button>
      </div>
      <p>
        {{
          mode === 'student'
            ? '一次只通知左边这位学生，记录只留在这个人下面。'
            : mode === 'mentor'
              ? '点开一位导师，只和这一位来回说。'
              : '和组委会的对话随时可以写，不等结项材料。'
        }}
      </p>
    </div>
    <p v-if="error" class="error">{{ error }}</p>
    <p v-if="msg" class="success-msg">{{ msg }}</p>

    <div class="board">
      <aside class="col people">
        <h2>{{ mode === 'student' ? '学生' : mode === 'mentor' ? '导师' : '对象' }}</h2>
        <template v-if="mode === 'student'">
          <button
            v-for="s in students"
            :key="s.application_id"
            type="button"
            :class="{ on: pickedStudent === s.application_id }"
            @click="pickedStudent = s.application_id"
          >
            <strong>{{ s.name }}</strong>
            <span>{{ s.project_title }} · {{ s.ended ? '对接已结束' : statusLabel(s.status) }}</span>
          </button>
          <p v-if="!students.length" class="empty">还没有学生接取本组织的项目。之后不论哪个项目，接取后都会出现在这里。</p>
        </template>
        <template v-else-if="mode === 'mentor'">
          <button
            v-for="m in mentors"
            :key="m.user_id"
            type="button"
            :class="{ on: pickedMentor === m.user_id }"
            @click="pickedMentor = m.user_id"
          >
            <strong>{{ m.name }}</strong>
            <span>{{ m.projects.length ? m.projects.join('、') : '尚未负责项目' }}</span>
          </button>
          <p v-if="!mentors.length" class="empty">还没有导师。</p>
        </template>
        <button v-else type="button" class="on static">
          <strong>组委会</strong>
          <span>本社区与组委会</span>
        </button>
      </aside>

      <section class="col talk">
        <header>
          <h2 v-if="mode === 'committee'">组委会</h2>
          <h2 v-else-if="picked">{{ 'name' in picked ? picked.name : '' }}</h2>
          <h2 v-else>选择左边的人</h2>
          <span v-if="mode === 'student'">正式通知</span>
          <span v-else>来回对话</span>
          <RouterLink v-for="item in finals" :key="item.id" class="submit-link" :to="`/org/final/${item.id}`">
            提交{{ item.student_name }}的结项
          </RouterLink>
        </header>
        <p v-if="mode === 'student' && studentNow?.ended" class="hint">对接已结束，不能再发通知。</p>
        <p v-else-if="mode === 'student' && studentNow?.case_status === 'pending'" class="hint">终止申请已交给组委会，查证通过前合作继续。</p>
        <div v-if="mode === 'student' && studentNow && !studentNow.ended" class="row-actions">
          <button
            v-if="studentNow.status === 'completed'"
            class="btn sm"
            type="button"
            :disabled="busy"
            @click="endLiaison"
          >
            结束对接
          </button>
          <button v-else class="btn sm outline" type="button" @click="endOpen = !endOpen">申请终止合作</button>
        </div>
        <form v-if="endOpen && mode === 'student' && studentNow && studentNow.status !== 'completed'" class="term" @submit.prevent="askTerminate">
          <p>只用于不做、不回复、乱做、辱骂等情况。组委会核对证明后才会终止，社区不能直接结束。</p>
          <select v-model="termCode">
            <option value="idle">不做</option>
            <option value="silent">不回复</option>
            <option value="messy">乱做</option>
            <option value="abuse">辱骂</option>
            <option value="other">其他严重问题</option>
          </select>
          <textarea v-model="termReason" rows="3" placeholder="说明发生了什么，至少写清楚时间和事情" />
          <textarea v-model="termLinks" rows="2" placeholder="证明链接，一行一个。可以是截图地址或相关页面" />
          <button class="btn sm" type="submit" :disabled="busy">提交组委会</button>
        </form>
        <div class="log">
          <p v-if="!thread.length" class="empty">还没有记录。写在下面的内容只发给当前这一位。</p>
          <LiaisonBubble
            v-for="m in thread"
            :key="m.id"
            :body="m.body"
            :mine="m.mine"
            :name="m.sender_name"
            :time="formatDateTime(m.created_at)"
          />
        </div>
        <LiaisonComposer
          v-if="!(mode === 'student' && studentNow?.ended)"
          :disabled="busy"
          :placeholder="mode === 'student' ? '写给这一位学生的通知，可附图片、表格或文件' : '写消息，可附图片、表格或文件'"
          :send-label="mode === 'student' ? '发送通知' : '发送'"
          @send="send"
        />
      </section>
    </div>
  </div>
</template>

<style scoped>
.desk { width: 100%; }
.bar { display: flex; flex-direction: column; align-items: flex-start; gap: 8px; margin-bottom: 12px; }
.bar p { margin: 0; color: #5c6b80; font-size: 0.88rem; }
.modes { display: flex; border: 1px solid #c5d0e0; border-radius: 8px; overflow: hidden; background: #fff; }
.modes button { border: 0; border-right: 1px solid #c5d0e0; background: #fff; padding: 8px 16px; cursor: pointer; font: inherit; color: #334155; }
.modes button:last-child { border-right: 0; }
.modes button.on { background: #1677ff; color: #fff; }
.board { display: grid; grid-template-columns: 280px minmax(0, 1fr); gap: 12px; min-height: calc(100vh - 250px); }
.col { background: #fff; border: 1px solid #b7c3d4; border-radius: 10px; box-shadow: 0 1px 2px rgba(20, 40, 80, 0.05); min-height: 420px; }
.people, .finals { padding: 12px; overflow: auto; background: #f7f9fc; }
.people h2, .finals h2 { margin: 0 0 10px; font-size: 0.95rem; }
.people button, .finals article { display: block; width: 100%; text-align: left; border: 1px solid #c5d0e0; background: #fff; border-radius: 8px; padding: 10px 12px; margin-bottom: 8px; cursor: pointer; font: inherit; }
.people button.on { border-color: #1677ff; background: #e8f3ff; box-shadow: inset 3px 0 0 #1677ff; }
.people button.static { cursor: default; }
.people span, .finals span, .log small { display: block; color: #64748b; font-size: 0.8rem; margin-top: 2px; }
.talk { display: flex; flex-direction: column; padding: 0; background: #fff; }
.talk header { display: flex; justify-content: space-between; align-items: baseline; gap: 8px; padding: 12px 14px; border-bottom: 1px solid #d5deea; }
.talk h2 { margin: 0; font-size: 1.05rem; }
.talk header .submit-link { color: #1677ff; font-size: 0.88rem; font-weight: 650; text-decoration: none; }
.log { flex: 1; margin: 12px; padding: 12px; overflow: auto; background: #eef3f9; border: 1px dashed #b7c3d4; border-radius: 8px; display: flex; flex-direction: column; gap: 8px; }
.log article { background: #fff; border: 1px solid #d5deea; border-radius: 8px; padding: 8px 10px; }
.log article.mine { border-color: #91caff; background: #f0f7ff; }
.log p { margin: 4px 0 0; }
.empty { margin: 0; color: #64748b; font-size: 0.88rem; }
.hint { margin: 0 0 10px; color: #64748b; font-size: 0.82rem; }
.row-actions { display: flex; gap: 8px; padding: 0 14px 8px; }
.term { padding: 0 14px 12px; display: flex; flex-direction: column; gap: 8px; }
.term p, .term select { font-size: 0.84rem; color: #475569; }
.btn.outline { background: #fff; color: #1677ff; border: 1px solid #1677ff; }
.talk :deep(.composer) { padding: 0 12px 12px; }
form textarea, .finals textarea { width: 100%; box-sizing: border-box; border: 1px solid #b7c3d4; border-radius: 8px; padding: 8px 10px; background: #fff; font: inherit; }
@media (max-width: 1100px) { .board { grid-template-columns: 1fr; } }
</style>
