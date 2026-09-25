<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, RouterLink, useRouter } from 'vue-router'
import api from '@/api/client'
import type { ApplicationOut, MessageOut, ReviewRecordOut, TaskDynamicsRow } from '@/api/types'
import PdfPreviewModal from '@/components/PdfPreviewModal.vue'
import PageCrumb from '@/components/PageCrumb.vue'
import EllipsisTip from '@/components/EllipsisTip.vue'
import {
  actionLabel,
  actorRoleLabel,
  formatDateTime,
  statusLabel,
} from '@/utils/statusLabel'
import { resolveCrumbs } from '@/utils/crumbTrail'

type SideTab = 'guide' | 'feed' | 'result' | 'task'
type DynSortKey =
  | 'registered_at'
  | 'last_progress_at'
  | 'progress_count'
  | 'last_acceptance_at'
  | 'acceptance_passed_at'

const route = useRoute()
const router = useRouter()
const app = ref<ApplicationOut | null>(null)
const logs = ref<MessageOut[]>([])
const taskDynamics = ref<TaskDynamicsRow[]>([])
const error = ref('')
const actionMsg = ref('')
const actionErr = ref('')
const busy = ref(false)
const sideTab = ref<SideTab>('task')
const dynSort = ref<{ key: DynSortKey; dir: 'asc' | 'desc' }>({
  key: 'registered_at',
  dir: 'desc',
})

const previewOpen = ref(false)
const previewUrl = ref('')
const previewTitle = ref('')

const appId = computed(() => String(route.params.id))

const crumbs = computed(() => {
  const title = app.value?.project_title
  if (!title) return [{ label: '我的项目' }]
  return resolveCrumbs(
    { label: title, to: `/student/applications/${appId.value}?tab=task` },
    [
      { label: '查看项目', to: '/projects' },
      { label: '我的项目', to: '/projects?tab=mine' },
    ],
  )
})

const canSubmit = computed(() => app.value?.status === 'draft')
const canReapply = computed(
  () => !!app.value && ['rejected', 'final_rejected', 'withdrawn'].includes(app.value.status),
)

/** 验收审核中：不可再交验收（可继续更新进展） */
const acceptancePending = computed(() =>
  ['final_submitted', 'mentor_final_review', 'committee_final_review'].includes(
    app.value?.status || '',
  ),
)

const inTaskDev = computed(() =>
  [
    'community_review',
    'committee_review',
    'selected',
    'in_progress',
    'final_rejected',
    'final_submitted',
    'mentor_final_review',
    'committee_final_review',
  ].includes(app.value?.status || ''),
)

/** 可点提交验收：开发期且非验收中 */
const canGoFinal = computed(
  () =>
    [
      'community_review',
      'committee_review',
      'selected',
      'in_progress',
      'final_rejected',
    ].includes(app.value?.status || '') && !acceptancePending.value,
)

const canWithdraw = computed(() =>
  [
    'community_review',
    'committee_review',
    'selected',
    'in_progress',
    'final_rejected',
  ].includes(app.value?.status || ''),
)

const phase = computed(() => {
  const s = app.value?.status || ''
  if (['draft', 'submitted', 'mentor_review', 'rejected', 'withdrawn'].includes(s)) return 1
  if (s === 'completed') return 3
  if (inTaskDev.value) return 2
  return 1
})

const reviewPipe = computed(() => {
  const s = app.value?.status || ''
  const stages = [
    { key: 'mentor', label: '导师', state: 'pending' as 'done' | 'current' | 'pending' | 'fail' },
    { key: 'community', label: '社区', state: 'pending' as 'done' | 'current' | 'pending' | 'fail' },
    { key: 'committee', label: '组委会', state: 'pending' as 'done' | 'current' | 'pending' | 'fail' },
  ]
  if (
    [
      'selected',
      'in_progress',
      'final_submitted',
      'mentor_final_review',
      'committee_final_review',
      'completed',
      'final_rejected',
    ].includes(s)
  ) {
    stages.forEach((x) => {
      x.state = 'done'
    })
    return stages
  }
  if (s === 'rejected') {
    stages[0].state = 'fail'
    return stages
  }
  if (['draft', 'submitted', 'mentor_review'].includes(s)) stages[0].state = 'current'
  else if (s === 'community_review') {
    stages[0].state = 'done'
    stages[1].state = 'current'
  } else if (s === 'committee_review') {
    stages[0].state = 'done'
    stages[1].state = 'done'
    stages[2].state = 'current'
  }
  return stages
})

type DynRow = {
  key: string
  at?: string | null
  type: string
  body: string
  attach?: string
  statusText: string
  statusTone: string
  teacherNote?: string
}

/** 个人审核/进展流水（仅「我的任务」） */
const personalDynamics = computed<DynRow[]>(() => {
  const rows: DynRow[] = []
  const feedbackPool: { id: number; at?: string | null; body: string }[] = []
  const acceptanceMsgs: MessageOut[] = []

  for (const m of logs.value) {
    const kind = m.kind || 'note'
    if (kind === 'feedback' || kind === 'note') {
      const body = String(m.body || '').trim()
      if (body) feedbackPool.push({ id: m.id, at: m.created_at, body })
    } else if (kind === 'progress' || kind === 'midterm') {
      const attachName =
        m.attachment_name ||
        (m.attachment_url ? m.attachment_url.split('/').pop() || '交付件.zip' : '')
      rows.push({
        key: `msg-${m.id}`,
        at: m.created_at,
        type: kind === 'midterm' ? '中期反馈' : '更新进展',
        body: m.body,
        attach: m.attachment_url
          ? JSON.stringify({ url: m.attachment_url, name: attachName })
          : undefined,
        statusText: '—',
        statusTone: 'empty',
      })
    } else if (kind === 'acceptance') {
      acceptanceMsgs.push(m)
    }
  }

  const sortedAcc = [...acceptanceMsgs].sort((a, b) =>
    String(b.created_at || '').localeCompare(String(a.created_at || '')),
  )
  sortedAcc.forEach((m, idx) => {
    const attachName =
      m.attachment_name ||
      (m.attachment_url ? m.attachment_url.split('/').pop() || '交付件.zip' : '')
    let statusText = '已提交'
    let tone = 'ok'
    if (idx === 0 && acceptancePending.value) {
      statusText = '验收中'
      tone = 'pending'
    }
    rows.push({
      key: `acc-${m.id}`,
      at: m.created_at,
      type: '提交验收',
      body: m.body || '—',
      attach: m.attachment_url
        ? JSON.stringify({ url: m.attachment_url, name: attachName })
        : undefined,
      statusText,
      statusTone: tone,
    })
  })

  const SKIP = new Set([
    'start_mentor_review',
    'start_mentor_final',
    'start_progress',
    'submit_final',
  ])
  const reviewRows: DynRow[] = []
  for (const r of (app.value?.review_records || []) as ReviewRecordOut[]) {
    const action = (r.action || '').toLowerCase()
    if (SKIP.has(action)) continue
    const to = (r.to_status || '').toLowerCase()
    const comment = String(r.comment || '').trim()
    const isSystem =
      !comment ||
      comment.startsWith('系统：') ||
      comment === '提交申请' ||
      comment === '学生主动放弃接取' ||
      comment === '导师取消学生接取'
    const rejected = action.includes('reject') || to.includes('reject')
    const approved =
      action.includes('approve') || to === 'selected' || to === 'completed'
    let statusText = actionLabel(r.action) || statusLabel(r.to_status)
    let tone = 'step'
    if (rejected) {
      statusText = '未通过'
      tone = 'fail'
    } else if (approved) {
      statusText = '已通过'
      tone = 'ok'
    } else if (action === 'submit') {
      statusText = '已提交'
      tone = 'ok'
    }
    const role = r.actor_role ? actorRoleLabel(r.actor_role) : ''
    reviewRows.push({
      key: `rev-${r.id || r.seq_no}-${r.created_at}`,
      at: r.created_at,
      type: actionLabel(r.action) || '审核',
      body: role
        ? `${statusLabel(r.from_status)} → ${statusLabel(r.to_status)} · ${role}`
        : `${statusLabel(r.from_status)} → ${statusLabel(r.to_status)}`,
      statusText,
      statusTone: tone,
      teacherNote: comment && !isSystem ? comment : undefined,
    })
  }

  const used = new Set<number>()
  const targets = reviewRows
    .filter((r) => r.statusTone === 'fail' || r.statusTone === 'ok')
    .sort((a, b) => String(b.at || '').localeCompare(String(a.at || '')))
  for (const fb of [...feedbackPool].sort((a, b) =>
    String(b.at || '').localeCompare(String(a.at || '')),
  )) {
    const target = targets.find((r) => !r.teacherNote)
    if (target) {
      target.teacherNote = fb.body
      used.add(fb.id)
    }
  }

  const failNotes = reviewRows.filter((r) => r.statusTone === 'fail' && r.teacherNote)
  if (failNotes.length && sortedAcc.length && !acceptancePending.value) {
    const latestAcc = rows.find((r) => r.key === `acc-${sortedAcc[0].id}`)
    const note = failNotes.sort((a, b) =>
      String(b.at || '').localeCompare(String(a.at || '')),
    )[0]
    if (latestAcc && note?.teacherNote) {
      latestAcc.statusText = '未通过'
      latestAcc.statusTone = 'fail'
      latestAcc.teacherNote = note.teacherNote
    }
  }

  rows.push(...reviewRows)
  for (const fb of feedbackPool) {
    if (used.has(fb.id)) continue
    rows.push({
      key: `msg-${fb.id}`,
      at: fb.at,
      type: '导师反馈',
      body: '—',
      statusText: '意见',
      statusTone: 'fail',
      teacherNote: fb.body,
    })
  }
  return rows.sort((a, b) => String(b.at || '').localeCompare(String(a.at || '')))
})

const sortedTaskDynamics = computed(() => {
  const list = [...taskDynamics.value]
  const { key, dir } = dynSort.value
  const mul = dir === 'asc' ? 1 : -1
  list.sort((a, b) => {
    if (key === 'progress_count') {
      return (a.progress_count - b.progress_count) * mul
    }
    const av = String(a[key] ?? '')
    const bv = String(b[key] ?? '')
    if (!av && !bv) return 0
    if (!av) return 1
    if (!bv) return -1
    return av.localeCompare(bv) * mul
  })
  return list
})

type PdfLinks = { resume?: string; design?: string }
const pdfs = computed<PdfLinks>(() => {
  const out: PdfLinks = {}
  const a = app.value
  if (!a) return out
  if (a.resume_pdf) out.resume = a.resume_pdf
  if (a.design_pdf) out.design = a.design_pdf
  const raw = a.extra_fields
  if (raw) {
    try {
      const obj = typeof raw === 'string' ? JSON.parse(raw) : raw
      if (!out.resume && obj?.resume_pdf) out.resume = String(obj.resume_pdf)
      if (!out.design && obj?.design_pdf) out.design = String(obj.design_pdf)
    } catch {
      /* ignore */
    }
  }
  if (!out.resume && a.attachment_url) out.resume = a.attachment_url
  return out
})

function fileLabel(url: string) {
  try {
    const name = decodeURIComponent(url.split('/').pop() || '文件.pdf')
    return name.replace(/^[a-f0-9]+_/i, '')
  } catch {
    return '文件.pdf'
  }
}

function attachMeta(raw?: string) {
  if (!raw) return null
  try {
    const o = JSON.parse(raw) as { url?: string; name?: string }
    if (o?.url) return { url: o.url, name: o.name || fileLabel(o.url) }
  } catch {
    /* ignore */
  }
  return null
}

/** 昇腾表：2026/09/20 14:10:32 */
function formatHwTime(raw?: string | null): string {
  if (!raw) return '—'
  const d = new Date(raw)
  if (Number.isNaN(d.getTime())) {
    return String(raw).replace('T', ' ').replace(/-/g, '/').slice(0, 19)
  }
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}/${pad(d.getMonth() + 1)}/${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

function openPreview(url: string, title: string) {
  previewUrl.value = url
  previewTitle.value = title
  previewOpen.value = true
}

function syncTabFromQuery() {
  const t = String(route.query.tab || 'task')
  if (t === 'guide' || t === 'feed' || t === 'result' || t === 'task') sideTab.value = t
  else sideTab.value = 'task'
}

function setTab(tab: SideTab) {
  sideTab.value = tab
  router.replace({ query: { ...route.query, tab } })
  if (tab === 'feed') void loadDynamics()
}

function toggleSort(key: DynSortKey) {
  if (dynSort.value.key === key) {
    dynSort.value = { key, dir: dynSort.value.dir === 'asc' ? 'desc' : 'asc' }
  } else {
    dynSort.value = { key, dir: 'desc' }
  }
}

function sortMark(key: DynSortKey) {
  if (dynSort.value.key !== key) return '↕'
  return dynSort.value.dir === 'asc' ? '↑' : '↓'
}

async function loadLogs() {
  try {
    const { data } = await api.get<MessageOut[]>(`/applications/${appId.value}/messages`)
    logs.value = data
  } catch {
    logs.value = []
  }
}

async function loadDynamics() {
  const pid = app.value?.project_id
  if (!pid) {
    taskDynamics.value = []
    return
  }
  try {
    const { data } = await api.get<TaskDynamicsRow[]>(`/projects/${pid}/task-dynamics`)
    taskDynamics.value = data
  } catch {
    taskDynamics.value = []
  }
}

async function load() {
  error.value = ''
  actionMsg.value = ''
  actionErr.value = ''
  try {
    const { data } = await api.get<ApplicationOut>(`/applications/${appId.value}`)
    app.value = data
    await loadLogs()
    if (sideTab.value === 'feed') await loadDynamics()
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : '加载失败'
  }
}

async function submitApp() {
  busy.value = true
  actionErr.value = ''
  try {
    await api.post(`/applications/${appId.value}/submit`)
    await load()
    actionMsg.value = '已提交审核'
  } catch (e: unknown) {
    actionErr.value = e instanceof Error ? e.message : '提交失败'
  } finally {
    busy.value = false
  }
}

async function withdrawApp() {
  if (!window.confirm('确定放弃接取该任务？放弃后名额将释放。')) return
  busy.value = true
  actionErr.value = ''
  try {
    await api.post(`/applications/${appId.value}/withdraw`)
    await load()
    actionMsg.value = '已放弃接取'
  } catch (e: unknown) {
    actionErr.value = e instanceof Error ? e.message : '操作失败'
  } finally {
    busy.value = false
  }
}

watch(() => route.params.id, load)
watch(() => route.query.tab, syncTabFromQuery, { immediate: true })
onMounted(load)
</script>

<template>
  <div class="page wide ascend-page">
    <PdfPreviewModal v-model:open="previewOpen" :url="previewUrl" :title="previewTitle" />
    <p v-if="error" class="error">{{ error }}</p>

    <template v-else-if="app">
      <PageCrumb :items="crumbs" />

      <div class="ascend-shell">
        <aside class="ascend-nav">
          <button type="button" :class="{ on: sideTab === 'guide' }" @click="setTab('guide')">
            任务指南
          </button>
          <button type="button" :class="{ on: sideTab === 'feed' }" @click="setTab('feed')">
            任务动态
          </button>
          <button type="button" :class="{ on: sideTab === 'result' }" @click="setTab('result')">
            结果公示
          </button>
          <button type="button" :class="{ on: sideTab === 'task' }" @click="setTab('task')">
            我的项目
          </button>
        </aside>

        <div class="ascend-main">
          <!-- 任务指南 -->
          <section v-if="sideTab === 'guide'" class="panel">
            <h2>一、任务指南</h2>
            <ol>
              <li>请先阅读项目任务书与申请材料要求，按导师反馈完善设计。</li>
              <li>导师通过并预留名额后，可在「我的项目」中多次「更新进展」。</li>
              <li>
                「提交验收」一次仅允许一份在审；审核未通过后，方可再次提交验收。
              </li>
            </ol>
            <h2>二、三级确认</h2>
            <p class="muted">
              导师通过后名额即预留；社区与组委会确认并行进行，不阻断任务开发。
            </p>
            <p class="guide-links">
              <RouterLink
                v-if="app.project_id"
                :to="`/projects/${app.project_id}`"
                >查看任务书 ›</RouterLink
              >
            </p>
          </section>

          <!-- 任务动态：项目维度报名/进展汇总（昇腾式） -->
          <section v-else-if="sideTab === 'feed'" class="panel feed-panel">
            <h2>任务动态</h2>
            <p class="muted feed-sub">实时展示报名状态与任务进展</p>
            <div class="hw-scroll">
              <table class="hw-table">
                <thead>
                  <tr>
                    <th class="col-nick">昵称</th>
                    <th class="sortable" @click="toggleSort('registered_at')">
                      报名时间 <i>{{ sortMark('registered_at') }}</i>
                    </th>
                    <th class="sortable" @click="toggleSort('last_progress_at')">
                      最新进展更新时间 <i>{{ sortMark('last_progress_at') }}</i>
                    </th>
                    <th class="sortable num" @click="toggleSort('progress_count')">
                      进展更新次数 <i>{{ sortMark('progress_count') }}</i>
                    </th>
                    <th class="sortable" @click="toggleSort('last_acceptance_at')">
                      最新提交验收时间 <i>{{ sortMark('last_acceptance_at') }}</i>
                    </th>
                    <th class="sortable" @click="toggleSort('acceptance_passed_at')">
                      验收通过时间 <i>{{ sortMark('acceptance_passed_at') }}</i>
                    </th>
                    <th>进度</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-if="!sortedTaskDynamics.length">
                    <td colspan="7" class="empty">暂无报名动态</td>
                  </tr>
                  <tr v-for="row in sortedTaskDynamics" :key="row.application_id">
                    <td>
                      <div class="nick-cell">
                        <span class="avatar" :data-letter="row.avatar_letter">{{
                          row.avatar_letter
                        }}</span>
                        <span class="nick">{{ row.nickname }}</span>
                      </div>
                    </td>
                    <td>{{ formatHwTime(row.registered_at) }}</td>
                    <td>{{ formatHwTime(row.last_progress_at) }}</td>
                    <td class="num">{{ row.progress_count }}</td>
                    <td>{{ formatHwTime(row.last_acceptance_at) }}</td>
                    <td>{{ formatHwTime(row.acceptance_passed_at) }}</td>
                    <td>
                      <span class="pill" :class="row.progress_tone">{{ row.progress_label }}</span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>

          <!-- 结果公示 -->
          <section v-else-if="sideTab === 'result'" class="panel result-empty">
            <div class="empty-art" aria-hidden="true" />
            <p>榜单将在评议完成后公示，敬请期待！</p>
          </section>

          <!-- 我的项目 -->
          <section v-else class="panel task-panel">
            <header class="task-meta">
              <div>
                <h1>{{ app.project_title || `申请 #${app.id}` }}</h1>
                <p class="muted">申请 #{{ app.id }}</p>
              </div>
            </header>

            <nav class="stage-bar" aria-label="任务阶段">
              <div class="stage" :class="{ done: phase > 1, on: phase === 1 }">
                <span class="stage-num">1</span>
                <div>
                  <strong>申请审核</strong>
                  <p>导师 → 社区 → 组委会</p>
                </div>
              </div>
              <span class="stage-line" :class="{ on: phase > 1 }" />
              <div class="stage" :class="{ done: phase > 2, on: phase === 2 }">
                <span class="stage-num">2</span>
                <div>
                  <strong>任务开发</strong>
                  <p>更新进展 / 提交验收</p>
                </div>
              </div>
              <span class="stage-line" :class="{ on: phase > 2 }" />
              <div
                class="stage"
                :class="{ done: app.status === 'completed', on: phase === 3 }"
              >
                <span class="stage-num">3</span>
                <div>
                  <strong>结项验收</strong>
                  <p>导师 / 组委会结项审</p>
                </div>
              </div>
            </nav>

            <div class="dev-card">
              <div class="dev-head">
                <div>
                  <h2 v-if="phase === 1">1. 申请审核</h2>
                  <h2 v-else-if="phase === 2">2. 任务开发</h2>
                  <h2 v-else>3. 结项验收</h2>
                  <p class="muted">
                    <template v-if="phase === 1">请完善材料并提交审核</template>
                    <template v-else>请根据任务书和任务指南开展任务</template>
                  </p>
                </div>
                <div class="dev-actions">
                  <template v-if="phase >= 2 || inTaskDev">
                    <RouterLink
                      class="btn"
                      :class="canGoFinal ? 'primary' : 'disabled'"
                      :to="canGoFinal ? `/student/applications/${app.id}/final` : ''"
                      :aria-disabled="!canGoFinal"
                      @click="(e) => !canGoFinal && e.preventDefault()"
                    >
                      提交验收
                    </RouterLink>
                    <RouterLink
                      class="btn outline"
                      :to="`/student/applications/${app.id}/progress`"
                    >
                      更新进展
                    </RouterLink>
                    <button
                      v-if="canWithdraw"
                      class="btn outline"
                      type="button"
                      :disabled="busy"
                      @click="withdrawApp"
                    >
                      放弃任务
                    </button>
                  </template>
                  <button
                    v-if="canSubmit"
                    class="btn primary"
                    type="button"
                    :disabled="busy"
                    @click="submitApp"
                  >
                    提交审核
                  </button>
                  <RouterLink
                    v-if="canReapply && app.project_id"
                    class="btn outline"
                    :to="`/projects/${app.project_id}`"
                  >
                    再次申请
                  </RouterLink>
                </div>
              </div>

              <p v-if="acceptancePending" class="hint-warn">
                当前有验收在审核中（验收中），暂不可再次「提交验收」；可继续「更新进展」。未通过后可再交。
              </p>

              <div class="materials">
                <span class="lab">申请材料</span>
                <button
                  v-if="pdfs.resume"
                  type="button"
                  class="file-pill"
                  @click="openPreview(pdfs.resume!, `简历 · ${fileLabel(pdfs.resume!)}`)"
                >
                  简历 · {{ fileLabel(pdfs.resume) }}
                </button>
                <button
                  v-if="pdfs.design"
                  type="button"
                  class="file-pill design"
                  @click="openPreview(pdfs.design!, `设计 · ${fileLabel(pdfs.design!)}`)"
                >
                  设计 · {{ fileLabel(pdfs.design) }}
                </button>
                <span v-if="!pdfs.resume && !pdfs.design" class="muted">暂无 PDF</span>
                <div class="mini-pipe">
                  <span
                    v-for="(st, i) in reviewPipe"
                    :key="st.key"
                    class="mini-step"
                    :class="st.state"
                  >
                    {{ st.label }}
                    <template v-if="i < reviewPipe.length - 1"> → </template>
                  </span>
                </div>
              </div>

              <h3 class="mine-h">我的申请动态</h3>
              <div class="dyn-scroll">
                <table class="dyn-table">
                  <thead>
                    <tr>
                      <th>操作时间</th>
                      <th>提交类型</th>
                      <th>附件</th>
                      <th>说明</th>
                      <th>状态</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-if="!personalDynamics.length">
                      <td colspan="5" class="empty">暂无动态</td>
                    </tr>
                    <tr v-for="row in personalDynamics" :key="'t-' + row.key">
                      <td class="time">{{ formatDateTime(row.at) || '—' }}</td>
                      <td class="type">{{ row.type }}</td>
                      <td class="attach">
                        <a
                          v-if="attachMeta(row.attach)"
                          :href="attachMeta(row.attach)!.url"
                          target="_blank"
                          rel="noopener"
                        >{{ attachMeta(row.attach)!.name }}</a>
                        <span v-else>—</span>
                      </td>
                      <td class="body">
                        <EllipsisTip :text="row.body || '—'" />
                      </td>
                      <td class="status-cell">
                        <span
                          v-if="row.statusTone !== 'empty'"
                          class="st"
                          :class="row.statusTone"
                        >{{ row.statusText }}</span>
                        <span v-else class="st-empty">—</span>
                        <div
                          v-if="row.teacherNote"
                          class="note-card"
                          :class="row.statusTone === 'ok' ? 'ok' : 'fail'"
                        >
                          <div class="note-head">
                            <span class="note-ico" aria-hidden="true">
                              <template v-if="row.statusTone === 'ok'">✓</template>
                              <template v-else>×</template>
                            </span>
                            <strong>{{
                              row.statusTone === 'ok' ? '已通过' : '未通过'
                            }}</strong>
                          </div>
                          <EllipsisTip :text="row.teacherNote" />
                        </div>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </section>
        </div>
      </div>

      <p v-if="actionMsg" class="success-msg">{{ actionMsg }}</p>
      <p v-if="actionErr" class="error">{{ actionErr }}</p>
    </template>
    <p v-else class="muted">加载中…</p>
  </div>
</template>

<style scoped>
.ascend-page {
  max-width: none;
  width: 100%;
  padding-left: clamp(0.75rem, 2vw, 1.5rem);
  padding-right: clamp(0.75rem, 2vw, 1.5rem);
}
.ospp-back {
  margin: 0 0 0.85rem;
}
.ospp-back a {
  color: #1890ff;
  text-decoration: none;
  font-size: 0.92rem;
}
.ospp-back a:hover {
  text-decoration: underline;
}
.guide-links {
  margin-top: 1.25rem;
}
.guide-links a {
  color: #1890ff;
  font-weight: 600;
  text-decoration: none;
}
.guide-links a:hover {
  text-decoration: underline;
}

.ascend-shell {
  display: grid;
  grid-template-columns: 148px minmax(0, 1fr);
  min-height: 560px;
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  overflow: hidden;
  width: 100%;
}
.ascend-nav {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  padding: 1rem 0.65rem;
  border-right: 1px solid #f1f5f9;
  background: #fafafa;
}
.ascend-nav button {
  text-align: left;
  border: none;
  background: transparent;
  padding: 0.65rem 0.75rem;
  border-radius: 10px;
  font: inherit;
  font-size: 0.92rem;
  color: #374151;
  cursor: pointer;
}
.ascend-nav button.on {
  background: #e5e7eb;
  font-weight: 700;
  color: #111;
}
.ascend-main {
  padding: 1.15rem 1.25rem 1.35rem;
  min-width: 0;
}
.panel h2 {
  margin: 0 0 0.35rem;
  font-size: 1.2rem;
  font-weight: 700;
}
.feed-sub {
  margin: 0 0 1rem;
  font-size: 0.88rem;
}
.panel ol {
  margin: 0 0 1.25rem;
  padding-left: 1.2rem;
  line-height: 1.65;
  color: #374151;
}
.muted {
  color: #6b7280;
}

.task-meta h1 {
  margin: 0 0 0.35rem;
  font-size: 1.35rem;
}
.task-meta p {
  margin: 0 0 1rem;
  display: flex;
  gap: 0.45rem;
  align-items: center;
  color: #64748b;
  font-size: 0.9rem;
}

.stage-bar {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 1.15rem;
  overflow-x: auto;
}
.stage {
  display: flex;
  align-items: center;
  gap: 0.55rem;
  flex: 0 0 auto;
  opacity: 0.4;
}
.stage.on,
.stage.done {
  opacity: 1;
}
.stage-num {
  width: 1.85rem;
  height: 1.85rem;
  border-radius: 999px;
  display: grid;
  place-items: center;
  font-weight: 700;
  background: #e5e7eb;
  color: #6b7280;
}
.stage.on .stage-num {
  background: #111;
  color: #fff;
}
.stage.done .stage-num {
  background: #16a34a;
  color: #fff;
}
.stage strong {
  display: block;
  font-size: 0.92rem;
}
.stage p {
  margin: 0.1rem 0 0;
  font-size: 0.72rem;
  color: #9ca3af;
}
.stage-line {
  flex: 1 1 1.5rem;
  height: 2px;
  min-width: 1.25rem;
  background: #e5e7eb;
}
.stage-line.on {
  background: #16a34a;
}

.dev-card {
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 1rem 1.1rem 1.15rem;
}
.dev-head {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
  align-items: flex-start;
  margin-bottom: 0.75rem;
}
.dev-head h2 {
  margin: 0 0 0.2rem;
  font-size: 1.1rem;
}
.dev-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
}
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0.42rem 1rem;
  border-radius: 999px;
  font-size: 0.86rem;
  font-weight: 600;
  cursor: pointer;
  text-decoration: none;
  border: 1px solid transparent;
  font: inherit;
  background: #fff;
  color: #111;
}
.btn.primary {
  background: #111;
  color: #fff;
}
.btn.outline {
  border-color: #d1d5db;
}
.btn.disabled {
  background: #e5e7eb;
  color: #9ca3af;
  pointer-events: none;
  cursor: not-allowed;
}
.hint-warn {
  margin: 0 0 0.75rem;
  padding: 0.55rem 0.7rem;
  border-radius: 8px;
  background: #fff7ed;
  color: #c2410c;
  font-size: 0.82rem;
}

.materials {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
  align-items: center;
  margin-bottom: 0.85rem;
  padding-bottom: 0.85rem;
  border-bottom: 1px solid #f3f4f6;
}
.materials .lab {
  font-size: 0.8rem;
  font-weight: 700;
  color: #6b7280;
}
.file-pill {
  border: 1px solid #bfdbfe;
  background: #eff6ff;
  color: #1d4ed8;
  border-radius: 999px;
  padding: 0.28rem 0.65rem;
  font-size: 0.78rem;
  font-weight: 600;
  cursor: pointer;
  font: inherit;
}
.file-pill.design {
  border-color: #bbf7d0;
  background: #f0fdf4;
  color: #166534;
}
.mini-pipe {
  margin-left: auto;
  font-size: 0.8rem;
  font-weight: 600;
  color: #9ca3af;
}
.mini-step.done {
  color: #16a34a;
}
.mini-step.current {
  color: #2563eb;
}
.mini-step.fail {
  color: #dc2626;
}

.mine-h {
  margin: 0 0 0.55rem;
  font-size: 0.95rem;
  font-weight: 700;
  color: #374151;
}

/* —— 昇腾任务动态表 —— */
.hw-scroll {
  max-height: min(62vh, 560px);
  overflow: auto;
  border: 1px solid #e8e8ef;
  border-radius: 8px;
}
.hw-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.86rem;
  min-width: 920px;
  table-layout: auto;
}
.hw-table th {
  position: sticky;
  top: 0;
  z-index: 1;
  text-align: left;
  padding: 0.7rem 0.85rem;
  background: #f0f0f8;
  color: #4b5563;
  font-weight: 700;
  border-bottom: 1px solid #e5e7eb;
  white-space: nowrap;
  font-size: 0.82rem;
}
.hw-table th.sortable {
  cursor: pointer;
  user-select: none;
}
.hw-table th.sortable i {
  font-style: normal;
  color: #9ca3af;
  margin-left: 0.15rem;
  font-size: 0.75rem;
}
.hw-table th.num,
.hw-table td.num {
  text-align: center;
}
.hw-table td {
  padding: 0.7rem 0.85rem;
  border-bottom: 1px solid #f0f0f5;
  vertical-align: middle;
  color: #374151;
  white-space: nowrap;
}
.hw-table .empty {
  text-align: center;
  color: #9ca3af;
  padding: 2rem;
  white-space: normal;
}
.col-nick {
  min-width: 6.5rem;
}
.nick-cell {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
.avatar {
  width: 1.65rem;
  height: 1.65rem;
  border-radius: 999px;
  display: grid;
  place-items: center;
  font-size: 0.72rem;
  font-weight: 700;
  color: #fff;
  background: hsl(210 55% 48%);
  flex: 0 0 auto;
}
.avatar[data-letter='A'],
.avatar[data-letter='H'],
.avatar[data-letter='S'] {
  background: hsl(200 60% 45%);
}
.avatar[data-letter='J'],
.avatar[data-letter='M'],
.avatar[data-letter='Y'] {
  background: hsl(160 45% 40%);
}
.avatar[data-letter='L'],
.avatar[data-letter='W'],
.avatar[data-letter='Z'] {
  background: hsl(25 70% 48%);
}
.nick {
  font-weight: 500;
}
.pill {
  display: inline-block;
  padding: 0.18rem 0.55rem;
  border-radius: 4px;
  font-size: 0.75rem;
  font-weight: 700;
  color: #fff;
  background: #94a3b8;
}
.pill.orange {
  background: #f59e0b;
}
.pill.blue {
  background: #3b82f6;
}
.pill.green {
  background: #16a34a;
}
.pill.red {
  background: #ef4444;
}
.pill.slate {
  background: #94a3b8;
}

/* —— 我的申请动态表 —— */
.dyn-scroll {
  max-height: 360px;
  overflow: auto;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
}
.dyn-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.86rem;
  min-width: 640px;
}
.dyn-table th {
  position: sticky;
  top: 0;
  z-index: 1;
  text-align: left;
  padding: 0.65rem 0.85rem;
  background: #f9fafb;
  color: #6b7280;
  font-weight: 600;
  border-bottom: 1px solid #e5e7eb;
  white-space: nowrap;
}
.dyn-table td {
  padding: 0.75rem 0.85rem;
  border-bottom: 1px solid #f3f4f6;
  vertical-align: top;
}
.dyn-table .time {
  white-space: nowrap;
  color: #6b7280;
  width: 9.5rem;
}
.dyn-table .type {
  white-space: nowrap;
  font-weight: 600;
  width: 7rem;
}
.dyn-table .attach {
  max-width: 11rem;
  word-break: break-all;
}
.dyn-table .attach a {
  color: #2563eb;
  font-weight: 500;
}
.dyn-table .body {
  line-height: 1.45;
  white-space: pre-wrap;
  word-break: break-word;
}
.dyn-table .empty {
  text-align: center;
  color: #9ca3af;
  padding: 1.5rem;
}
.status-cell .st {
  display: inline-block;
  padding: 0.15rem 0.5rem;
  border-radius: 999px;
  font-size: 0.75rem;
  font-weight: 700;
  background: #f3f4f6;
  color: #4b5563;
}
.status-cell .st.ok {
  background: #dcfce7;
  color: #166534;
}
.status-cell .st.fail {
  background: #fee2e2;
  color: #b91c1c;
}
.status-cell .st.pending {
  background: #ffedd5;
  color: #c2410c;
}
.status-cell .st.step {
  background: #e0e7ff;
  color: #3730a3;
}
.st-empty {
  color: #9ca3af;
}
.status-cell {
  position: relative;
  max-width: 14rem;
}
.note-card {
  position: relative;
  margin-top: 0.45rem;
  padding: 0.45rem 0.6rem 0.5rem;
  border-radius: 4px;
  border: 1px solid #fecaca;
  border-left: 3px solid #ef4444;
  background: #fff5f5;
  max-width: 13.5rem;
  cursor: default;
}
.note-card.ok {
  border-color: #bbf7d0;
  border-left-color: #22c55e;
  background: #f0fdf4;
}
.note-head {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  margin-bottom: 0.2rem;
}
.note-ico {
  width: 1rem;
  height: 1rem;
  border-radius: 999px;
  display: grid;
  place-items: center;
  font-size: 0.65rem;
  font-weight: 800;
  color: #fff;
  background: #ef4444;
  flex: 0 0 auto;
  line-height: 1;
}
.note-card.ok .note-ico {
  background: #16a34a;
}
.note-head strong {
  font-size: 0.82rem;
  font-weight: 700;
  color: #111;
}
.note-preview {
  margin: 0;
}
.note-card :deep(.ellipsis) {
  max-width: 12rem;
  color: #b91c1c;
  font-size: 0.78rem;
}
.note-card.ok :deep(.ellipsis) {
  color: #166534;
}

.result-empty {
  min-height: 360px;
  display: grid;
  place-content: center;
  text-align: center;
  color: #9ca3af;
}
.empty-art {
  width: 120px;
  height: 80px;
  margin: 0 auto 1rem;
  border: 2px dashed #d1d5db;
  border-radius: 12px;
  background: linear-gradient(180deg, #f8fafc, #fff);
}

@media (max-width: 840px) {
  .ascend-shell {
    grid-template-columns: 1fr;
  }
  .ascend-nav {
    flex-direction: row;
    flex-wrap: wrap;
    border-right: none;
    border-bottom: 1px solid #f1f5f9;
  }
}
</style>
