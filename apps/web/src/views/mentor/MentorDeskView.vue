<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import api from '@/api/client'
import type { ApplicationOut, MessageOut, ProjectOut, ReviewRecordOut, ReviewResponse } from '@/api/types'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import DocReader from '@/components/DocReader.vue'
import ToastFeedback from '@/components/ToastFeedback.vue'
import { formatDateTime, statusLabel } from '@/utils/statusLabel'

type Filter = 'todo' | 'doing' | 'done'
type DocTab = 'design' | 'resume'

const route = useRoute()
const router = useRouter()
const toast = ref<InstanceType<typeof ToastFeedback> | null>(null)

const project = ref<ProjectOut | null>(null)
const rows = ref<ApplicationOut[]>([])
const detail = ref<ApplicationOut | null>(null)
const logs = ref<MessageOut[]>([])
const filter = ref<Filter>('todo')
const docTab = ref<DocTab>('design')
const showHistory = ref(false)
const comment = ref('')
const busy = ref(false)
const loading = ref(true)
const error = ref('')
const confirmOpen = ref(false)
const pending = ref<'approve' | 'reject' | null>(null)

const selectedId = computed(() => Number(route.params.id) || 0)

const slotsLeft = computed(() =>
  Math.max(0, (project.value?.quota || 0) - (project.value?.seats_taken || 0)),
)

function groupOf(a: ApplicationOut): Filter {
  if (['final_submitted', 'mentor_final_review'].includes(a.status)) return 'todo'
  if (['submitted', 'mentor_review'].includes(a.status)) {
    if (slotsLeft.value <= 0) return 'done'
    return inWindow(a) ? 'todo' : 'doing'
  }
  if (['rejected', 'final_rejected'].includes(a.status)) return 'doing'
  if (['completed', 'committee_final_review', 'withdrawn'].includes(a.status)) return 'done'
  return 'doing'
}

function jobLabel(a: ApplicationOut) {
  if (['final_submitted', 'mentor_final_review'].includes(a.status)) return '待验收'
  if (a.status === 'final_rejected') return '已打回，等再交验收'
  if (a.status === 'rejected') return '已打回，等再交设计'
  if (['submitted', 'mentor_review'].includes(a.status)) {
    const rank = designOrder(a)
    if (slotsLeft.value <= 0) return '人选已满'
    if (rank > slotsLeft.value) return '排队'
    return '待看设计'
  }
  if (a.status === 'completed') return '已结项'
  if (a.status === 'committee_final_review') return '已交组委会'
  if (a.status === 'withdrawn') return '已放弃'
  return '开发中'
}

function designOrder(a: ApplicationOut) {
  const list = rows.value
    .filter((x) => ['submitted', 'mentor_review'].includes(x.status))
    .slice()
    .sort((x, y) => String(x.created_at || '').localeCompare(String(y.created_at || '')))
  return list.findIndex((x) => x.id === a.id) + 1
}

function inWindow(a: ApplicationOut) {
  if (!['submitted', 'mentor_review'].includes(a.status)) return false
  if (slotsLeft.value <= 0) return false
  const rank = designOrder(a)
  return rank > 0 && rank <= slotsLeft.value
}

const visible = computed(() =>
  rows.value
    .filter((a) => groupOf(a) === filter.value)
    .slice()
    .sort((a, b) => String(a.created_at || '').localeCompare(String(b.created_at || ''))),
)

const counts = computed(() => ({
  todo: rows.value.filter((a) => groupOf(a) === 'todo').length,
  doing: rows.value.filter((a) => groupOf(a) === 'doing').length,
  done: rows.value.filter((a) => groupOf(a) === 'done').length,
}))

const current = computed(() => detail.value || rows.value.find((a) => a.id === selectedId.value) || null)

const pdfs = computed(() => {
  const a = current.value
  const out: { resume?: string; design?: string } = {}
  if (!a) return out
  if (a.resume_pdf) out.resume = a.resume_pdf
  if (a.design_pdf) out.design = a.design_pdf
  if (a.extra_fields) {
    try {
      const obj = typeof a.extra_fields === 'string' ? JSON.parse(a.extra_fields) : a.extra_fields
      if (!out.resume && obj?.resume_pdf) out.resume = String(obj.resume_pdf)
      if (!out.design && obj?.design_pdf) out.design = String(obj.design_pdf)
    } catch {
      /* ignore */
    }
  }
  return out
})

const docUrl = computed(() => (docTab.value === 'resume' ? pdfs.value.resume : pdfs.value.design) || '')

const acceptances = computed(() =>
  logs.value.filter((m) => m.kind === 'acceptance').slice().sort((a, b) => String(a.created_at || '').localeCompare(String(b.created_at || ''))),
)

const mentorNotes = computed(() => {
  const notes: { id: string; at?: string | null; text: string; tag: string }[] = []
  const seen = new Set<string>()
  const push = (id: string, text: string, at?: string | null, tag = '留言') => {
    const clean = text.trim()
    if (!clean || clean.startsWith('系统：') || seen.has(clean)) return
    seen.add(clean)
    notes.push({ id, at, text: clean, tag })
  }
  for (const m of logs.value) {
    if (m.kind === 'feedback') push(`m-${m.id}`, m.body || '', m.created_at, '留言')
  }
  for (const r of (current.value?.review_records || []) as ReviewRecordOut[]) {
    const rejected = (r.action || '').includes('reject') || (r.to_status || '').includes('reject')
    push(`r-${r.id || r.created_at}`, r.comment || '', r.created_at, rejected ? '打回' : '审核意见')
  }
  return notes.sort((a, b) => String(b.at || '').localeCompare(String(a.at || '')))
})

const canPass = computed(() => {
  const s = current.value?.status || ''
  if (['final_submitted', 'mentor_final_review'].includes(s)) return true
  return !!current.value && inWindow(current.value)
})

const canReturn = computed(() => canPass.value)

const nextId = computed(() => {
  const list = visible.value
  const idx = list.findIndex((a) => a.id === selectedId.value)
  return list[idx + 1]?.id || list.find((a) => a.id !== selectedId.value)?.id || 0
})

function openStudent(id: number) {
  router.push(`/mentor/a/${id}`)
}

async function loadDetail(id: number) {
  const { data } = await api.get<ApplicationOut>(`/applications/${id}`)
  detail.value = data
  const { data: msgs } = await api.get<MessageOut[]>(`/applications/${id}/messages`)
  logs.value = msgs
  docTab.value = data.design_pdf ? 'design' : 'resume'
  showHistory.value = false
  comment.value = ''
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const { data: owned } = await api.get<ProjectOut[]>('/projects', { params: { owned: true } })
    project.value = owned[0] || null
    const { data } = await api.get<ApplicationOut[]>('/mentor/inbox')
    rows.value = data
    if (selectedId.value && data.some((a) => a.id === selectedId.value)) {
      await loadDetail(selectedId.value)
    } else {
      detail.value = null
      logs.value = []
    }
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : '加载失败'
  } finally {
    loading.value = false
  }
}

function ask(kind: 'approve' | 'reject') {
  if (kind === 'reject' && !comment.value.trim()) {
    toast.value?.show('打回时请写下这次的问题', 'err')
    return
  }
  if (!canPass.value && kind === 'approve') {
    toast.value?.show('这一位现在不能通过', 'err')
    return
  }
  pending.value = kind
  confirmOpen.value = true
}

async function runDecide() {
  const decision = pending.value
  if (!decision || !current.value) return
  busy.value = true
  try {
    const finalPhase = ['final_submitted', 'mentor_final_review'].includes(current.value.status)
    const url = finalPhase
      ? `/applications/${current.value.id}/final/reviews`
      : `/applications/${current.value.id}/reviews`
    await api.post<ReviewResponse>(url, {
      decision,
      comment: comment.value || null,
      version: current.value.version,
    })
    toast.value?.show(decision === 'approve' ? '已通过' : '已打回，学生会看到这次的问题', 'ok')
    comment.value = ''
    await load()
  } catch (e: unknown) {
    toast.value?.show(e instanceof Error ? e.message : '操作失败', 'err')
  } finally {
    busy.value = false
    pending.value = null
  }
}

async function sendNote() {
  if (!current.value || !comment.value.trim()) {
    toast.value?.show('请先填写留言', 'err')
    return
  }
  busy.value = true
  try {
    await api.post(`/applications/${current.value.id}/messages`, {
      body: comment.value.trim(),
      kind: 'feedback',
    })
    comment.value = ''
    toast.value?.show('留言已发给这位同学', 'ok')
    await loadDetail(current.value.id)
  } catch (e: unknown) {
    toast.value?.show(e instanceof Error ? e.message : '发送失败', 'err')
  } finally {
    busy.value = false
  }
}

watch(selectedId, (id) => {
  if (id) void loadDetail(id).catch(() => undefined)
})

onMounted(load)
</script>

<template>
  <div class="bench">
    <ToastFeedback ref="toast" />
    <ConfirmDialog
      v-model:open="confirmOpen"
      :title="pending === 'reject' ? '确认打回？' : '确认通过？'"
      :message="current ? `${current.student_name || '同学'} · 申请 #${current.id}` : ''"
      :danger="pending === 'reject'"
      confirm-text="确定"
      @confirm="runDecide"
    />

    <header class="top">
      <div>
        <h1>{{ project?.title || '导师工作台' }}</h1>
        <p>
          已入选 {{ project?.seats_taken || 0 }} / 名额 {{ project?.quota || 0 }}
          <template v-if="slotsLeft <= 0"> · 设计审核已关闭</template>
        </p>
      </div>
      <RouterLink v-if="project" class="book" :to="`/projects/${project.id}`">任务书</RouterLink>
    </header>

    <div class="filters">
      <button type="button" :class="{ on: filter === 'todo' }" @click="filter = 'todo'">
        待我处理 <b>{{ counts.todo }}</b>
      </button>
      <button type="button" :class="{ on: filter === 'doing' }" @click="filter = 'doing'">
        进行中 <b>{{ counts.doing }}</b>
      </button>
      <button type="button" :class="{ on: filter === 'done' }" @click="filter = 'done'">
        已结束 <b>{{ counts.done }}</b>
      </button>
    </div>

    <p v-if="error" class="error">{{ error }}</p>
    <p v-else-if="loading" class="muted pad">加载中…</p>

    <div v-else class="body">
      <aside class="list">
        <button
          v-for="a in visible"
          :key="a.id"
          type="button"
          class="person"
          :class="{ on: a.id === selectedId }"
          @click="openStudent(a.id)"
        >
          <strong>{{ a.student_name || a.student_email || `同学 #${a.student_id}` }}</strong>
          <span>{{ jobLabel(a) }}</span>
          <small>{{ formatDateTime(a.updated_at || a.created_at) }}</small>
        </button>
        <p v-if="!visible.length" class="muted empty">这一组没有同学。</p>
      </aside>

      <section v-if="!current" class="idle">
        <p>从左边打开一位同学。默认只显示现在要处理的人，按提交时间从早到晚。</p>
      </section>

      <template v-else>
        <section class="read">
          <div class="read-bar">
            <div>
              <strong>{{ current.student_name || '同学' }}</strong>
              <span>申请 #{{ current.id }} · {{ jobLabel(current) }} · {{ statusLabel(current.status) }}</span>
            </div>
            <div class="tabs">
              <button type="button" :class="{ on: docTab === 'design' }" @click="docTab = 'design'">设计文档</button>
              <button type="button" :class="{ on: docTab === 'resume' }" @click="docTab = 'resume'">简历</button>
            </div>
          </div>
          <DocReader v-if="docUrl" :key="docUrl" :url="docUrl" />
          <div v-else class="idle">
            <p v-if="docTab === 'design' && acceptances.length">
              最新验收：
              <a :href="acceptances[acceptances.length - 1].attachment_url || '#'" target="_blank" rel="noopener">
                {{ acceptances[acceptances.length - 1].attachment_name || '验收附件' }}
              </a>
            </p>
            <p v-else>这一侧没有可预览的 PDF。</p>
          </div>
        </section>

        <aside class="rail">
          <div v-if="mentorNotes.length" class="notes">
            <b>已有留言</b>
            <article v-for="n in mentorNotes" :key="n.id" :class="{ back: n.tag === '打回' }">
              <small>{{ n.tag }} · {{ formatDateTime(n.at) }}</small>
              <p>{{ n.text }}</p>
            </article>
          </div>
          <p v-else class="muted">这位同学还没有设计审核留言。</p>

          <label>
            这次的意见
            <textarea v-model="comment" rows="5" placeholder="打回时必填，学生再次提交时会看到" />
          </label>

          <div class="acts">
            <button class="btn" type="button" :disabled="busy || !canPass" @click="ask('approve')">通过</button>
            <button class="btn danger" type="button" :disabled="busy || !canReturn" @click="ask('reject')">打回</button>
            <button class="btn outline" type="button" :disabled="busy" @click="sendNote">留言</button>
          </div>
          <button v-if="nextId" class="next" type="button" @click="openStudent(nextId)">下一位</button>

          <button class="hist" type="button" @click="showHistory = !showHistory">
            {{ showHistory ? '收起记录' : '全部记录' }}
          </button>
          <ol v-if="showHistory" class="history">
            <li v-for="(m, i) in acceptances" :key="m.id">
              验收第 {{ i + 1 }} 次 · {{ formatDateTime(m.created_at) }}
              <a v-if="m.attachment_url" :href="m.attachment_url" target="_blank" rel="noopener">附件</a>
              <span>{{ m.body }}</span>
            </li>
            <li v-for="r in current.review_records || []" :key="r.id || r.created_at">
              {{ formatDateTime(r.created_at) }} · {{ r.comment || r.action }}
            </li>
            <li v-for="m in logs.filter((x) => x.kind === 'feedback')" :key="'f' + m.id">
              留言 · {{ formatDateTime(m.created_at) }} · {{ m.body }}
            </li>
          </ol>
        </aside>
      </template>
    </div>
  </div>
</template>

<style scoped>
.bench {
  height: calc(100vh - var(--nav-h, 64px));
  display: flex;
  flex-direction: column;
  background: #f4f6f8;
}
.top, .filters { padding: 12px 20px 0; }
.top {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: 16px;
}
.top h1 { margin: 0; font-size: 1.25rem; }
.top p { margin: 4px 0 0; color: #8c8c8c; font-size: 0.88rem; }
.book { color: #0b3d91; font-weight: 650; }
.filters { display: flex; gap: 8px; padding-bottom: 12px; }
.filters button {
  border: 1px solid #e5e7eb;
  background: #fff;
  border-radius: 999px;
  padding: 6px 12px;
  font: inherit;
  cursor: pointer;
}
.filters button.on { background: #0b3d91; color: #fff; border-color: #0b3d91; }
.filters b { font-weight: 700; }
.body {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: 260px minmax(0, 1fr) 320px;
  gap: 10px;
  padding: 0 12px 12px;
}
.list, .read, .rail, .idle {
  background: #fff;
  border: 1px solid #e8e8e8;
  border-radius: 10px;
  min-height: 0;
}
.list { overflow: auto; padding: 6px; }
.person {
  width: 100%;
  text-align: left;
  border: 0;
  background: transparent;
  border-radius: 8px;
  padding: 10px;
  cursor: pointer;
  font: inherit;
}
.person.on { background: #e8f1ff; }
.person strong, .person span, .person small { display: block; }
.person span { color: #0b3d91; font-size: 0.82rem; margin-top: 2px; }
.person small { color: #8c8c8c; font-size: 0.75rem; }
.read { display: flex; flex-direction: column; overflow: hidden; }
.read-bar {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  padding: 10px 12px;
  border-bottom: 1px solid #f0f0f0;
}
.read-bar span { display: block; color: #8c8c8c; font-size: 0.8rem; }
.tabs { display: flex; gap: 6px; }
.tabs button, .acts button, .next, .hist {
  border: 1px solid #d9d9d9;
  background: #fff;
  border-radius: 6px;
  padding: 4px 10px;
  font: inherit;
  cursor: pointer;
}
.tabs button.on { background: #0b3d91; color: #fff; border-color: #0b3d91; }
.rail { overflow: auto; padding: 14px; display: flex; flex-direction: column; gap: 10px; }
.rail label { font-size: 0.88rem; }
.rail textarea { width: 100%; margin-top: 6px; box-sizing: border-box; }
.acts { display: flex; flex-wrap: wrap; gap: 8px; }
.btn.danger { background: #fff; color: #b91c1c; border: 1px solid #fecaca; }
.btn.outline { background: #fff; color: #0b3d91; border: 1px solid #91caff; }
.next { width: 100%; }
.last {
  background: #fff7ed;
  border: 1px solid #fed7aa;
  border-radius: 8px;
  padding: 10px;
}
.notes { display: flex; flex-direction: column; gap: 8px; }
.notes > b { font-size: 0.88rem; }
.notes article {
  background: #f8fafc;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 8px 10px;
}
.notes article.back { background: #fff7ed; border-color: #fed7aa; }
.notes small { color: #8c8c8c; }
.notes p { margin: 4px 0 0; }
.history { margin: 0; padding-left: 1.1rem; font-size: 0.82rem; color: #434343; }
.history li { margin: 0 0 8px; }
.idle { display: grid; place-items: center; color: #8c8c8c; padding: 24px; text-align: center; }
.empty { padding: 12px; }
.pad { padding: 12px 20px; }
@media (max-width: 1100px) {
  .bench { height: auto; }
  .body { grid-template-columns: 1fr; }
  .read { min-height: 70vh; }
}
</style>
