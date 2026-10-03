<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import api, { withFileAuth } from '@/api/client'
import type { ApplicationOut, CommunityOut, MessageOut, ProjectOut, ReviewRecordOut, ReviewResponse } from '@/api/types'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import DocReader from '@/components/DocReader.vue'
import PdfPreviewModal from '@/components/PdfPreviewModal.vue'
import LiaisonBubble from '@/components/LiaisonBubble.vue'
import LiaisonComposer from '@/components/LiaisonComposer.vue'
import ToastFeedback from '@/components/ToastFeedback.vue'
import { useAuthStore } from '@/stores/auth'
import { formatDateTime, statusLabel } from '@/utils/statusLabel'

type CommunityMsg = { id: number; sender_name: string; body: string; mine: boolean; created_at?: string | null }
type Filter = 'all' | 'todo' | 'doing' | 'done' | 'liaison'
type DocTab = 'design' | 'resume'
type WorkTab = 'brief' | 'progress' | 'final'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const communityTalk = ref<CommunityMsg[]>([])
const communities = ref<CommunityOut[]>([])
const talkCommunityId = ref(0)
const toast = ref<InstanceType<typeof ToastFeedback> | null>(null)

const projects = ref<ProjectOut[]>([])
const rows = ref<ApplicationOut[]>([])
const detail = ref<ApplicationOut | null>(null)
const logs = ref<MessageOut[]>([])
const filter = ref<Filter>('all')
const docTab = ref<DocTab>('design')
const previewOpen = ref(false)
const previewUrl = ref('')
const previewTitle = ref('')
const workTab = ref<WorkTab>('brief')
const advice = ref('')
const showHistory = ref(false)
const comment = ref('')
const busy = ref(false)
const loading = ref(true)
const error = ref('')
const confirmOpen = ref(false)
const pending = ref<'approve' | 'reject' | null>(null)

const preferTab = ref<WorkTab | null>(null)
const pickedProjectId = ref(0)
const personQuery = ref('')
const page = ref(1)
const pageSize = 20

const selectedId = computed(() => Number(route.params.id) || 0)

const project = computed(() => projects.value.find((item) => item.id === pickedProjectId.value) || null)

const talkTargets = computed(() => {
  const ids = [...new Set(projects.value.map((item) => item.community_id))]
  return ids.map((id) => ({
    id,
    name: communities.value.find((item) => item.id === id)?.name || `社区 #${id}`,
  }))
})

const talkName = computed(() => talkTargets.value.find((item) => item.id === talkCommunityId.value)?.name || '社区')

function seatsLeftOf(a: ApplicationOut) {
  const owned = projects.value.find((item) => item.id === a.project_id)
  if (!owned) return 1
  return Math.max(0, (owned.quota || 0) - (owned.seats_taken || 0))
}

const slotsLeft = computed(() => {
  const owned = project.value
  if (!owned) return 1
  return Math.max(0, (owned.quota || 0) - (owned.seats_taken || 0))
})

function groupOf(a: ApplicationOut): Filter {
  if (['final_submitted', 'mentor_final_review'].includes(a.status)) return 'todo'
  if (['submitted', 'mentor_review'].includes(a.status)) return 'todo'
  if (['rejected', 'final_rejected'].includes(a.status)) return 'doing'
  if (['completed', 'committee_final_review', 'withdrawn'].includes(a.status)) return 'done'
  return 'doing'
}

function jobLabel(a: ApplicationOut) {
  if (['final_submitted', 'mentor_final_review'].includes(a.status)) return '待验收'
  if (a.status === 'final_rejected') return '已打回，等再交验收'
  if (a.status === 'rejected') return '已打回，等再交设计'
  if (['submitted', 'mentor_review'].includes(a.status)) {
    if (seatsLeftOf(a) <= 0) return '人选已满'
    return '待看设计'
  }
  if (a.status === 'completed') return '已结项'
  if (a.status === 'community_final_review') return '验收已通过'
  if (a.status === 'committee_final_review') return '已交组委会'
  if (a.status === 'withdrawn') return '已放弃'
  return '开发中'
}

const projectOptions = computed(() =>
  projects.value
    .filter((owned) => owned.status === 'published')
    .map((owned) => ({
      id: owned.id,
      title: owned.title,
      quota: owned.quota || 0,
      taken: owned.seats_taken || 0,
    })),
)

const inProject = computed(() =>
  rows.value.filter((row) => !pickedProjectId.value || row.project_id === pickedProjectId.value),
)

const matched = computed(() => {
  const q = personQuery.value.trim().toLowerCase()
  return inProject.value
    .filter((row) => filter.value === 'all' || groupOf(row) === filter.value)
    .filter((row) => {
      if (!q) return true
      const name = `${row.student_name || ''} ${row.student_email || ''}`.toLowerCase()
      return name.includes(q)
    })
    .slice()
    .sort((a, b) =>
      String(b.latest_update_at || b.updated_at || b.created_at || '').localeCompare(
        String(a.latest_update_at || a.updated_at || a.created_at || ''),
      ),
    )
})

const pageCount = computed(() => Math.max(1, Math.ceil(matched.value.length / pageSize)))

const pageRows = computed(() => {
  const start = (page.value - 1) * pageSize
  return matched.value.slice(start, start + pageSize)
})

const counts = computed(() => ({
  todo: inProject.value.filter((a) => groupOf(a) === 'todo').length,
  doing: inProject.value.filter((a) => groupOf(a) === 'doing').length,
  done: inProject.value.filter((a) => groupOf(a) === 'done').length,
}))

const pendingDesigns = computed(() =>
  inProject.value.filter((a) => ['submitted', 'mentor_review'].includes(a.status)).length,
)

function onPickProject(event: Event) {
  chooseProject(Number((event.target as HTMLSelectElement).value))
}

function chooseProject(id: number) {
  if (!id || id === pickedProjectId.value) return
  pickedProjectId.value = id
  page.value = 1
  personQuery.value = ''
  const open = rows.value.find((row) => row.id === selectedId.value)
  if (open && open.project_id !== id) router.push('/mentor')
}

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

function openDoc(kind: DocTab) {
  const url = kind === 'resume' ? pdfs.value.resume : pdfs.value.design
  if (!url) return
  previewTitle.value = kind === 'resume' ? '简历' : '设计文档'
  previewUrl.value = url
  previewOpen.value = true
}

const progressItems = computed(() =>
  logs.value
    .filter((m) => m.kind === 'progress')
    .slice()
    .sort((a, b) => String(b.created_at || '').localeCompare(String(a.created_at || ''))),
)

const acceptanceItems = computed(() =>
  logs.value
    .filter((m) => m.kind === 'acceptance')
    .slice()
    .sort((a, b) => String(b.created_at || '').localeCompare(String(a.created_at || ''))),
)

function filledLink(url?: string | null) {
  const value = (url || '').trim()
  return value && value !== '暂无' ? value : ''
}

function defaultWork(status: string): WorkTab {
  if (['final_submitted', 'mentor_final_review', 'final_rejected', 'community_final_review', 'committee_final_review'].includes(status)) return 'final'
  if (['submitted', 'mentor_review', 'rejected'].includes(status)) return 'brief'
  return 'progress'
}

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

const finalOpen = computed(() => ['final_submitted', 'mentor_final_review'].includes(current.value?.status || ''))
const designOpen = computed(() => {
  const row = current.value
  if (!row) return false
  return ['submitted', 'mentor_review'].includes(row.status) && seatsLeftOf(row) > 0
})

const canPass = computed(() => (workTab.value === 'final' ? finalOpen.value : designOpen.value))
const canReturn = computed(() => canPass.value)

function openStudent(id: number) {
  router.push(`/mentor/a/${id}`)
}

async function ackUpdate(row: ApplicationOut) {
  const kind = row.update_badge
  if (!kind) return
  try {
    await api.post(`/mentor/inbox/${row.id}/ack-update`)
    row.update_badge = null
    preferTab.value = kind === 'acceptance' ? 'final' : 'progress'
    if (selectedId.value === row.id) {
      workTab.value = preferTab.value
      preferTab.value = null
      return
    }
    await router.push(`/mentor/a/${row.id}`)
  } catch (e: unknown) {
    preferTab.value = null
    toast.value?.show(e instanceof Error ? e.message : '标记清除失败', 'err')
  }
}

async function loadDetail(id: number) {
  const { data } = await api.get<ApplicationOut>(`/applications/${id}`)
  detail.value = data
  const { data: msgs } = await api.get<MessageOut[]>(`/applications/${id}/messages`)
  logs.value = msgs
  docTab.value = data.design_pdf ? 'design' : 'resume'
  workTab.value = preferTab.value || defaultWork(data.status)
  preferTab.value = null
  showHistory.value = false
  comment.value = ''
  advice.value = ''
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const { data: owned } = await api.get<ProjectOut[]>('/projects', { params: { owned: true } })
    projects.value = owned
    const { data: catalog } = await api.get<CommunityOut[]>('/communities')
    communities.value = catalog
    const { data } = await api.get<ApplicationOut[]>('/mentor/inbox')
    rows.value = data
    const open = data.find((row) => row.id === selectedId.value)
    const live = projectOptions.value
    const openLive = !!(open && live.some((item) => item.id === open.project_id))
    if (openLive && open) pickedProjectId.value = open.project_id
    else if (!live.some((item) => item.id === pickedProjectId.value)) {
      pickedProjectId.value = live[0]?.id || 0
    }
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
    toast.value?.show('退回时请写下这次的问题', 'err')
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
    toast.value?.show(decision === 'approve' ? (finalOpen.value && workTab.value === 'final' ? '结项已通过' : '已通过') : '已退回，学生会看到这次的问题', 'ok')
    comment.value = ''
    await load()
  } catch (e: unknown) {
    toast.value?.show(e instanceof Error ? e.message : '操作失败', 'err')
  } finally {
    busy.value = false
    pending.value = null
  }
}

async function sendAdvice() {
  if (!current.value || !advice.value.trim()) {
    toast.value?.show('请先写下给这次进展的建议', 'err')
    return
  }
  busy.value = true
  try {
    await api.post(`/applications/${current.value.id}/messages`, {
      body: advice.value.trim(),
      kind: 'feedback',
    })
    advice.value = ''
    toast.value?.show('建议已发给学生，不改变结项状态', 'ok')
    await loadDetail(current.value.id)
    workTab.value = 'progress'
  } catch (e: unknown) {
    toast.value?.show(e instanceof Error ? e.message : '发送失败', 'err')
  } finally {
    busy.value = false
  }
}

watch(selectedId, (id) => {
  const row = rows.value.find((item) => item.id === id)
  if (row && projectOptions.value.some((item) => item.id === row.project_id)) {
    pickedProjectId.value = row.project_id
  }
  if (id) void loadDetail(id).catch(() => undefined)
})

watch([filter, personQuery], () => {
  page.value = 1
})

watch(pageCount, (count) => {
  if (page.value > count) page.value = count
})

async function loadCommunityTalk() {
  const cid = talkCommunityId.value
  const me = auth.user?.id
  if (!cid || !me) {
    communityTalk.value = []
    return
  }
  const { data } = await api.get<CommunityMsg[]>('/liaison/thread', {
    params: { community_id: cid, channel: 'mentor', peer_user_id: me },
  })
  communityTalk.value = data
}

async function sendCommunity(body: string) {
  const cid = talkCommunityId.value
  const me = auth.user?.id
  if (!cid || !me || !body.trim()) return
  await api.post('/liaison', {
    community_id: cid,
    channel: 'mentor',
    peer_user_id: me,
    body,
  })
  await loadCommunityTalk()
}

watch(project, (item) => {
  if (item) talkCommunityId.value = item.community_id
})

watch(talkCommunityId, () => {
  void loadCommunityTalk()
})

onMounted(load)
</script>

<template>
  <div class="bench">
    <ToastFeedback ref="toast" />
    <ConfirmDialog
      v-model:open="confirmOpen"
      :title="pending === 'reject' ? '确认退回？' : '确认通过？'"
      :message="current ? `${current.student_name || '同学'} · 申请 #${current.id}` : ''"
      :danger="pending === 'reject'"
      confirm-text="确定"
      @confirm="runDecide"
    />

    <header class="top">
      <div class="top-head">
        <div>
          <h1>导师工作台</h1>
          <div class="task-line">
            <label class="task-field">
              <span>任务</span>
              <select class="task-select" :value="pickedProjectId || ''" @change="onPickProject">
                <option v-if="!projectOptions.length" value="">没有正在招生的任务</option>
                <option v-for="item in projectOptions" :key="item.id" :value="item.id">
                  {{ item.title }}
                </option>
              </select>
            </label>
            <label class="task-field find-field">
              <span>查找同学</span>
              <input v-model="personQuery" type="search" placeholder="输入姓名" />
            </label>
            <p v-if="project">
              已入选 {{ project.seats_taken || 0 }} / 名额 {{ project.quota || 0 }}
              <template v-if="slotsLeft <= 0"> · 设计审核已关闭</template>
              <template v-else-if="pendingDesigns > 1"> · 先把材料对照完，再通过最合适的人</template>
            </p>
          </div>
        </div>
        <div class="top-links">
          <RouterLink v-if="project" :to="`/projects/${project.id}`">任务书</RouterLink>
        </div>
      </div>
    </header>

    <div class="filters">
      <div class="filter-tabs">
        <button type="button" :class="{ on: filter === 'all' }" @click="filter = 'all'">
          全部 <b>{{ inProject.length }}</b>
        </button>
        <button type="button" :class="{ on: filter === 'todo' }" @click="filter = 'todo'">
          待我处理 <b>{{ counts.todo }}</b>
        </button>
        <button type="button" :class="{ on: filter === 'doing' }" @click="filter = 'doing'">
          进行中 <b>{{ counts.doing }}</b>
        </button>
        <button type="button" :class="{ on: filter === 'done' }" @click="filter = 'done'">
          已结束 <b>{{ counts.done }}</b>
        </button>
        <button type="button" :class="{ on: filter === 'liaison' }" @click="filter = 'liaison'">
          社区对接
        </button>
      </div>
    </div>

    <p v-if="error" class="error">{{ error }}</p>
    <p v-else-if="loading" class="muted pad">加载中…</p>

    <div v-else-if="filter === 'liaison'" class="body liaison">
      <aside class="col people">
        <h2>社区</h2>
        <button
          v-for="item in talkTargets"
          :key="item.id"
          type="button"
          :class="{ on: talkCommunityId === item.id }"
          @click="talkCommunityId = item.id"
        >
          <strong>{{ item.name }}</strong>
          <span>社区管理员</span>
        </button>
        <p v-if="!talkTargets.length" class="empty">还没有可对接的社区。</p>
      </aside>
      <section class="col talk">
        <header>
          <h2>{{ talkName }}</h2>
          <span>来回对话</span>
        </header>
        <p class="hint">只和这位社区管理员来回说，不进学生的开发记录。</p>
        <div class="log">
          <p v-if="!communityTalk.length" class="empty">还没有记录。写在下面的内容只发给当前这个社区。</p>
          <LiaisonBubble
            v-for="m in communityTalk"
            :key="m.id"
            :body="m.body"
            :mine="m.mine"
            :name="m.sender_name"
            :time="formatDateTime(m.created_at)"
          />
        </div>
        <LiaisonComposer placeholder="写给社区管理员，可附图片、表格或文件" send-label="发送" @send="sendCommunity" />
      </section>
    </div>

    <div v-else class="body">
      <aside class="list">
        <div
          v-for="a in pageRows"
          :key="a.id"
          class="person"
          :class="{ on: a.id === selectedId }"
          role="button"
          tabindex="0"
          @click="openStudent(a.id)"
          @keydown.enter="openStudent(a.id)"
        >
          <div class="person-top">
            <strong>{{ a.student_name || a.student_email || `同学 #${a.student_id}` }}</strong>
            <button
              v-if="a.update_badge"
              type="button"
              class="flag"
              :class="{ accept: a.update_badge === 'acceptance' }"
              @click.stop="ackUpdate(a)"
            >
              {{ a.update_badge === 'acceptance' ? '新验收' : '新进展' }}
            </button>
          </div>
          <span>{{ jobLabel(a) }}</span>
          <small>{{ formatDateTime(a.latest_update_at || a.updated_at || a.created_at) }}</small>
        </div>
        <p v-if="!pageRows.length" class="muted empty">这个任务里没有符合条件的同学。</p>
        <div v-if="matched.length > pageSize" class="pager">
          <button type="button" :disabled="page <= 1" @click="page = page - 1">上一页</button>
          <span>{{ page }} / {{ pageCount }} · {{ matched.length }} 人</span>
          <button type="button" :disabled="page >= pageCount" @click="page = page + 1">下一页</button>
        </div>
      </aside>

      <section v-if="!current" class="idle">
        <p>先在上面选一个任务。新进展和新验收在名字旁边，点标记才会消失。人多时用姓名查找，或翻页，每页 20 人。</p>
      </section>

      <template v-else>
        <section class="read">
          <div class="read-bar">
            <div>
              <strong>{{ current.student_name || '同学' }}</strong>
              <span>申请 #{{ current.id }} · {{ current.project_title || '任务' }} · {{ jobLabel(current) }} · {{ statusLabel(current.status) }}</span>
            </div>
            <div class="tabs">
              <button type="button" :class="{ on: workTab === 'brief' }" @click="workTab = 'brief'">申请书</button>
              <button type="button" :class="{ on: workTab === 'progress' }" @click="workTab = 'progress'">进展</button>
              <button type="button" :class="{ on: workTab === 'final' }" @click="workTab = 'final'">结项验收</button>
            </div>
          </div>

          <div v-if="workTab === 'brief'" class="pane">
            <div class="tabs sub">
              <button type="button" :class="{ on: docTab === 'design' }" @click="docTab = 'design'">设计文档</button>
              <button type="button" :class="{ on: docTab === 'resume' }" @click="docTab = 'resume'">简历</button>
              <button type="button" class="linkish" :disabled="!docUrl" @click="openDoc(docTab)">放大预览</button>
            </div>
            <DocReader v-if="docUrl" :key="docUrl" :url="docUrl" />
            <p v-else class="muted pad">还没有可预览的申请书 PDF。</p>
            <PdfPreviewModal v-model:open="previewOpen" :url="previewUrl" :title="previewTitle" />
            <div v-if="designOpen" class="decide">
              <label>
                退回意见
                <textarea v-model="comment" rows="3" placeholder="通过可以不写。退回时必须写明问题。" />
              </label>
              <div class="acts">
                <button class="btn pass" type="button" :disabled="busy" @click="ask('approve')">通过设计</button>
                <button class="btn danger" type="button" :disabled="busy" @click="ask('reject')">退回</button>
              </div>
            </div>
          </div>

          <div v-else-if="workTab === 'progress'" class="pane scroll">
            <p class="hint">进展只是让你知道学生做到哪一步。下载看过之后，在下面写建议。这里不能结项，也不能退回验收。</p>
            <p v-if="!progressItems.length" class="muted">这位同学还没有更新进展。</p>
            <article v-for="m in progressItems" :key="m.id" class="card">
              <small>更新进展 · {{ formatDateTime(m.created_at) }}</small>
              <p>{{ m.body || '没有写说明' }}</p>
              <p v-if="filledLink(m.design_doc_url)" class="as-text">设计文档：{{ filledLink(m.design_doc_url) }}</p>
              <p v-if="filledLink(m.code_url)" class="as-text">代码链接：{{ filledLink(m.code_url) }}</p>
              <a v-if="m.attachment_url" :href="withFileAuth(m.attachment_url)" :download="m.attachment_name || '交付件.zip'">下载 {{ m.attachment_name || '交付件' }}</a>
            </article>
            <label>
              给这次进展的建议
              <textarea v-model="advice" rows="3" placeholder="看完材料后写给同学。这只是建议，不会变成未通过。" />
            </label>
            <button class="btn pass" type="button" :disabled="busy" @click="sendAdvice">发给学生</button>
          </div>

          <div v-else class="pane scroll">
            <p class="hint">这里是结项。只看学生交来的验收，和上面的进展不是同一件事。</p>
            <p v-if="!acceptanceItems.length" class="muted">还没有提交验收。</p>
            <article v-for="m in acceptanceItems" :key="m.id" class="card final">
              <small>提交验收 · {{ formatDateTime(m.created_at) }}</small>
              <p>{{ m.body || '没有写说明' }}</p>
              <p v-if="filledLink(m.design_doc_url)" class="as-text">设计文档：{{ filledLink(m.design_doc_url) }}</p>
              <p v-if="filledLink(m.code_url)" class="as-text">代码链接：{{ filledLink(m.code_url) }}</p>
              <a v-if="m.attachment_url" :href="withFileAuth(m.attachment_url)" :download="m.attachment_name || '交付件.zip'">下载 {{ m.attachment_name || '交付件' }}</a>
            </article>
            <div v-if="mentorNotes.length" class="notes">
              <b>以往退回时写过的话</b>
              <article v-for="n in mentorNotes.filter((item) => item.tag === '打回')" :key="n.id">
                <small>{{ formatDateTime(n.at) }}</small>
                <p>{{ n.text }}</p>
              </article>
            </div>
            <div v-if="finalOpen" class="decide">
              <label>
                退回意见
                <textarea v-model="comment" rows="3" placeholder="结项通过可以不写。退回时必须写明要改什么。" />
              </label>
              <div class="acts">
                <button class="btn pass" type="button" :disabled="busy" @click="ask('approve')">结项通过</button>
                <button class="btn danger" type="button" :disabled="busy" @click="ask('reject')">退回</button>
              </div>
            </div>
            <p v-else-if="current.status === 'community_final_review'" class="muted">验收已经通过。学生可以向本社区申请奖励，材料只交给社区管理员。结项完成后，名单直接进入组委会，不再走社区对接。</p>
            <p v-else-if="current.status === 'committee_final_review'" class="muted">你已通过结项，材料在组委会审核。</p>
            <p v-else-if="acceptanceItems.length" class="muted">现在不是结项审核阶段，只能查看已交的验收材料。</p>
          </div>
        </section>
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
  flex-direction: column;
  gap: 0;
}
.top-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: 16px;
}
.top h1 { margin: 0; font-size: 1.05rem; font-weight: 650; color: #8c8c8c; }
.task-line {
  display: flex;
  align-items: flex-end;
  gap: 12px;
  margin-top: 10px;
  flex-wrap: wrap;
}
.task-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}
.task-field span { color: #595959; font-size: 0.8rem; }
.task-field.find-field { width: 220px; }
.task-select,
.task-field input {
  font: inherit;
  font-size: 1rem;
  font-weight: 650;
  color: #141414;
  background: #fff;
  border: 1px solid #d9d9d9;
  border-radius: 8px;
  padding: 8px 12px;
}
.task-select { min-width: 280px; }
.task-field input { width: 100%; box-sizing: border-box; font-weight: 500; }
.task-line p { margin: 0 0 8px; color: #8c8c8c; font-size: 0.86rem; }
.body.liaison {
  grid-template-columns: 280px minmax(0, 1fr);
  align-items: stretch;
}
.body.liaison .col {
  background: #fff;
  border: 1px solid #b7c3d4;
  border-radius: 10px;
  min-height: 0;
}
.body.liaison .people {
  padding: 12px;
  overflow: auto;
  background: #f7f9fc;
}
.body.liaison .people h2 { margin: 0 0 10px; font-size: 0.95rem; }
.body.liaison .people button {
  display: block;
  width: 100%;
  text-align: left;
  border: 1px solid #c5d0e0;
  background: #fff;
  border-radius: 8px;
  padding: 10px 12px;
  margin-bottom: 8px;
  cursor: pointer;
  font: inherit;
}
.body.liaison .people button.on {
  border-color: #1677ff;
  background: #e8f3ff;
  box-shadow: inset 3px 0 0 #1677ff;
}
.body.liaison .people span { display: block; color: #64748b; font-size: 0.8rem; margin-top: 2px; }
.body.liaison .talk { display: flex; flex-direction: column; padding: 0; }
.body.liaison .talk header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 8px;
  padding: 12px 14px;
  border-bottom: 1px solid #d5deea;
}
.body.liaison .talk h2 { margin: 0; font-size: 1.05rem; }
.body.liaison .talk header span { color: #1677ff; font-size: 0.88rem; }
.body.liaison .hint { margin: 8px 14px 0; color: #64748b; font-size: 0.82rem; }
.body.liaison .log {
  flex: 1;
  margin: 12px;
  padding: 12px;
  overflow: auto;
  background: #eef3f9;
  border: 1px dashed #b7c3d4;
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-height: 160px;
}
.body.liaison .empty { margin: 0; color: #64748b; font-size: 0.88rem; }
.body.liaison .talk :deep(.composer) { padding: 0 12px 12px; }
.top-links { display: flex; gap: 8px; }
.top-links a {
  border: 1px solid #e5e7eb;
  background: #fff;
  color: #262626;
  border-radius: 8px;
  padding: 6px 12px;
  font-size: 0.88rem;
  text-decoration: none;
}
.top-links a:hover { border-color: #91caff; color: #0b3d91; }
.filters {
  display: flex;
  align-items: center;
  gap: 8px;
  padding-bottom: 12px;
}
.filter-tabs { display: flex; gap: 8px; flex-wrap: wrap; }
.pager {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 8px;
  color: #64748b;
  font-size: 0.82rem;
}
.pager button {
  border: 1px solid #d9d9d9;
  background: #fff;
  border-radius: 8px;
  padding: 4px 8px;
  font: inherit;
  cursor: pointer;
}
.pager button:disabled { opacity: 0.45; cursor: not-allowed; }
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
  grid-template-columns: 260px minmax(0, 1fr);
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
.task-name {
  margin: 10px 8px 0;
  font-size: 0.92rem;
  color: #0f172a;
}
.task-meta {
  margin: 0 8px 4px;
  color: #94a3b8;
  font-size: 0.75rem;
}
.task-empty { margin: 0 8px 8px; font-size: 0.78rem; }
.task-block + .task-block { border-top: 1px solid #eef2f6; margin-top: 8px; padding-top: 4px; }
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
.person-top { display: flex; align-items: flex-start; justify-content: space-between; gap: 8px; }
.person-top strong { min-width: 0; }
.flag {
  flex: none;
  border: 0;
  border-radius: 999px;
  background: #1677ff;
  color: #fff;
  font-size: 0.72rem;
  line-height: 1.4;
  padding: 1px 7px;
  cursor: pointer;
}
.flag.accept { background: #d97706; }
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
.pane { display: flex; flex-direction: column; min-height: 0; flex: 1; }
.preview-acts { display: flex; gap: 8px; margin: 8px 0 12px; }
.pane.scroll { overflow: auto; padding: 16px 18px 20px; gap: 10px; }
.hint { margin: 0 0 8px; color: #64748b; line-height: 1.6; }
.tabs.sub { padding: 8px 12px 0; }
.card { border: 1px solid #e5e7eb; border-radius: 10px; padding: 12px 14px; background: #f8fafc; }
.card.final { background: #fff; border-color: #d6e4ff; }
.card small { color: #64748b; }
.card p { margin: 8px 0; white-space: pre-wrap; line-height: 1.6; }
.card .as-text { color: #1f2937; word-break: break-word; }
.card a, .pane > .btn { color: #1677ff; }
.card a { margin-right: 12px; }
.decide { margin-top: 8px; padding: 12px 14px 4px; border-top: 1px solid #eef2f6; }
.decide textarea, .pane textarea { width: 100%; box-sizing: border-box; margin-top: 6px; }
.pane > .btn.pass { align-self: flex-start; background: #1677ff; color: #fff; border: 0; border-radius: 8px; padding: 8px 14px; }
.rail label { font-size: 0.88rem; }
.rail textarea { width: 100%; margin-top: 6px; box-sizing: border-box; }
.acts { display: flex; flex-wrap: wrap; gap: 8px; }
.acts .btn.pass { background: #1677ff; color: #fff; border-color: #1677ff; }
.acts .btn.pass:disabled { background: #e8eef5; color: #8c8c8c; border-color: #d9d9d9; }
.btn.danger { background: #fff; color: #b91c1c; border: 1px solid #fecaca; }
.btn.outline { background: #fff; color: #0b3d91; border: 1px solid #91caff; }
.next { width: 100%; }
.last {
  background: #fff7ed;
  border: 1px solid #fed7aa;
  border-radius: 8px;
  padding: 10px;
}
.deliveries { display: flex; flex-direction: column; gap: 8px; }
.deliveries > b { font-size: 0.92rem; color: #1e3a5f; }
.deliveries article { background: #f8fafc; border: 1px solid #e5e7eb; border-radius: 8px; padding: 8px 10px; }
.deliveries small { color: #64748b; }
.deliveries p { margin: 6px 0; white-space: pre-wrap; line-height: 1.55; }
.deliveries a { display: inline-block; margin: 0 10px 0 0; color: #1677ff; }
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
