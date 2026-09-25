<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import api from '@/api/client'
import type { ApplicationOut, MessageOut, ProjectOut, ReviewResponse } from '@/api/types'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import PdfPreviewModal from '@/components/PdfPreviewModal.vue'
import ReviewTimeline from '@/components/ReviewTimeline.vue'
import EllipsisTip from '@/components/EllipsisTip.vue'
import ToastFeedback from '@/components/ToastFeedback.vue'
import { useAuthStore } from '@/stores/auth'
import { formatDateTime, nodeLabel, statusLabel, statusTone } from '@/utils/statusLabel'

const auth = useAuthStore()
const route = useRoute()
const reviewId = computed(() => Number(route.params.id) || 0)
const toast = ref<InstanceType<typeof ToastFeedback> | null>(null)

const inbox = ref<ApplicationOut[]>([])
const projects = ref<ProjectOut[]>([])
const loading = ref(true)
const error = ref('')
const busy = ref(false)
const activeId = ref<number | null>(null)
const comment = ref('')
const feedbackText = ref('')
const detail = ref<ApplicationOut | null>(null)
const detailLoading = ref(false)
const logs = ref<MessageOut[]>([])

const confirmOpen = ref(false)
const pendingDecision = ref<'approve' | 'reject' | null>(null)

const previewOpen = ref(false)
const previewUrl = ref('')
const previewTitle = ref('')

const active = computed(() => detail.value || inbox.value.find((a) => a.id === activeId.value) || null)
const myProjects = computed(() => projects.value)
const progressLogs = computed(() => logs.value.filter((m) => m.kind === 'progress'))
const midtermLogs = computed(() => logs.value.filter((m) => m.kind === 'midterm'))
const acceptanceLogs = computed(() => logs.value.filter((m) => m.kind === 'acceptance'))
const feedbackLogs = computed(() => logs.value.filter((m) => m.kind === 'feedback'))
const studentLogs = computed(() =>
  [...progressLogs.value, ...midtermLogs.value, ...acceptanceLogs.value].sort((a, b) =>
    String(b.created_at || '').localeCompare(String(a.created_at || '')),
  ),
)

/** 申请审核 / 开发指导 / 结项审核 */
const mentorPhase = computed(() => {
  const s = active.value?.status || ''
  if (['mentor_review', 'submitted'].includes(s)) return 'app_review'
  // 导师通过、名额预留后即进入开发指导（与学生端任务开发对齐）
  if (
    [
      'community_review',
      'committee_review',
      'selected',
      'in_progress',
      'final_rejected',
    ].includes(s)
  ) {
    return 'dev'
  }
  if (['final_submitted', 'mentor_final_review'].includes(s)) return 'final'
  return 'other'
})

const queueReview = computed(() => inbox.value.filter((a) => ['mentor_review', 'submitted'].includes(a.status)))
const queueDev = computed(() =>
  inbox.value.filter((a) =>
    ['community_review', 'committee_review', 'selected', 'in_progress', 'final_rejected'].includes(
      a.status,
    ),
  ),
)
const queueFinal = computed(() =>
  inbox.value.filter((a) => ['final_submitted', 'mentor_final_review'].includes(a.status)),
)

const queueTab = ref<'review' | 'dev' | 'final'>('review')
const visibleQueue = computed(() => {
  if (queueTab.value === 'dev') return queueDev.value
  if (queueTab.value === 'final') return queueFinal.value
  return queueReview.value
})

type PdfLinks = { resume?: string; design?: string }

const pdfs = computed<PdfLinks>(() => {
  const app = active.value
  if (!app) return {}
  const out: PdfLinks = {}
  if (app.resume_pdf) out.resume = app.resume_pdf
  if (app.design_pdf) out.design = app.design_pdf
  if (app.extra_fields) {
    try {
      const obj = typeof app.extra_fields === 'string' ? JSON.parse(app.extra_fields) : app.extra_fields
      if (!out.resume && obj?.resume_pdf) out.resume = String(obj.resume_pdf)
      if (!out.design && obj?.design_pdf) out.design = String(obj.design_pdf)
    } catch {
      /* ignore */
    }
  }
  if (!out.resume && app.attachment_url) out.resume = app.attachment_url
  return out
})

function kindLabel(kind?: string | null) {
  if (kind === 'acceptance') return '提交验收'
  if (kind === 'midterm') return '中期反馈'
  return '更新进展'
}

function fileLabel(url: string) {
  try {
    const name = decodeURIComponent(url.split('/').pop() || '文件.pdf')
    return name.replace(/^[a-f0-9]+_/i, '')
  } catch {
    return '文件.pdf'
  }
}

function openPreview(url: string, title: string) {
  previewUrl.value = url
  previewTitle.value = title
  previewOpen.value = true
}

function previewResume() {
  const url = pdfs.value.resume
  if (!url) return
  openPreview(url, `简历 · ${fileLabel(url)}`)
}

function previewDesign() {
  const url = pdfs.value.design
  if (!url) return
  openPreview(url, `项目设计 · ${fileLabel(url)}`)
}

async function selectApp(id: number) {
  activeId.value = id
  comment.value = ''
  feedbackText.value = ''
  detailLoading.value = true
  logs.value = []
  try {
    const { data } = await api.get<ApplicationOut>(`/applications/${id}`)
    detail.value = data
    const idx = inbox.value.findIndex((a) => a.id === id)
    if (idx >= 0) inbox.value[idx] = { ...inbox.value[idx], ...data }
    try {
      const { data: msgs } = await api.get<MessageOut[]>(`/applications/${id}/messages`)
      logs.value = msgs
    } catch {
      logs.value = []
    }
  } catch {
    detail.value = inbox.value.find((a) => a.id === id) || null
  } finally {
    detailLoading.value = false
  }
}

async function sendFeedback() {
  const text =
    mentorPhase.value === 'app_review' ? comment.value.trim() : feedbackText.value.trim()
  if (!active.value || !text) {
    toast.value?.show('请先填写意见内容，再点「仅发留言」', 'err')
    return
  }
  const who = active.value.student_name || active.value.student_email || '学生'
  const appId = active.value.id
  busy.value = true
  try {
    await api.post(`/applications/${appId}/messages`, {
      body: text,
      kind: 'feedback',
    })
    if (mentorPhase.value === 'app_review') comment.value = ''
    else feedbackText.value = ''
    const { data: msgs } = await api.get<MessageOut[]>(`/applications/${appId}/messages`)
    logs.value = msgs
    toast.value?.show(`已发给「${who}」· 申请 #${appId}（学生在申请详情顶部可见）`, 'ok')
  } catch (e: unknown) {
    toast.value?.show(e instanceof Error ? e.message : '发送失败', 'err')
  } finally {
    busy.value = false
  }
}

async function cancelAssignment() {
  if (!active.value) return
  if (!window.confirm('确定取消该学生的任务接取？名额将释放，学生可再次申请。')) return
  busy.value = true
  try {
    await api.post(`/applications/${active.value.id}/cancel-assignment`)
    toast.value?.show('已取消接取', 'ok')
    await load()
  } catch (e: unknown) {
    toast.value?.show(e instanceof Error ? e.message : '取消失败', 'err')
  } finally {
    busy.value = false
  }
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const [box, mine] = await Promise.all([
      api.get<ApplicationOut[]>('/mentor/inbox'),
      api.get<ProjectOut[]>('/projects', { params: { owned: true } }),
    ])
    inbox.value = box.data
    projects.value = mine.data
    // 自动切到有数据的 tab
    if (queueTab.value === 'review' && !queueReview.value.length) {
      if (queueDev.value.length) queueTab.value = 'dev'
      else if (queueFinal.value.length) queueTab.value = 'final'
    }
    const pool = visibleQueue.value
    const keep =
      activeId.value && pool.some((a) => a.id === activeId.value)
        ? activeId.value
        : (pool[0]?.id ?? null)
    if (keep) await selectApp(keep)
    else {
      activeId.value = null
      detail.value = null
    }
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : '加载失败'
  } finally {
    loading.value = false
  }
}

const lastActionNote = ref('')

function askDecide(decision: 'approve' | 'reject') {
  if (!active.value) return
  pendingDecision.value = decision
  confirmOpen.value = true
}

function switchTab(tab: 'review' | 'dev' | 'final') {
  queueTab.value = tab
  lastActionNote.value = ''
  const pool = visibleQueue.value
  const first = pool[0]?.id ?? null
  if (first) void selectApp(first)
  else {
    activeId.value = null
    detail.value = null
  }
}

async function runDecide() {
  const decision = pendingDecision.value
  if (!decision || !active.value) return
  if (decision === 'reject' && !comment.value.trim()) {
    confirmOpen.value = false
    toast.value?.show('拒绝时请填写审核意见，学生才能在任务动态里看到原因', 'err')
    return
  }
  const who = active.value.student_name || active.value.student_email || `申请 #${active.value.id}`
  const appId = active.value.id
  const proj = active.value.project_title || `项目 #${active.value.project_id}`
  busy.value = true
  try {
    const isFinal = ['mentor_final_review', 'committee_final_review', 'final_submitted'].includes(
      active.value.status,
    )
    const url = isFinal
      ? `/applications/${active.value.id}/final/reviews`
      : `/applications/${active.value.id}/reviews`
    const { data } = await api.post<ReviewResponse>(url, {
      decision,
      comment: comment.value || null,
      version: active.value.version,
    })
    const verb = decision === 'approve' ? '已通过' : '已拒绝'
    lastActionNote.value = `${verb}「${who}」· ${proj}（申请 #${appId}）：${statusLabel(data.from_status)} → ${statusLabel(data.to_status)}`
    toast.value?.show(lastActionNote.value, decision === 'approve' ? 'ok' : 'err')
    comment.value = ''
    await load()
    const next = active.value
    if (next && next.id !== appId) {
      toast.value?.show(
        `已切换到下一条待审：${next.student_name || next.student_email || `申请 #${next.id}`}`,
        'ok',
      )
    } else if (!next) {
      toast.value?.show('本分类队列已空', 'ok')
    }
  } catch (e: unknown) {
    toast.value?.show(e instanceof Error ? e.message : '审核失败', 'err')
  } finally {
    busy.value = false
    pendingDecision.value = null
  }
}

onMounted(async () => {
  await load()
  if (reviewId.value) await selectApp(reviewId.value)
})
</script>

<template>
  <div class="page mentor-page wide">
    <ToastFeedback ref="toast" />
    <ConfirmDialog
      v-model:open="confirmOpen"
      :title="
        mentorPhase === 'final'
          ? pendingDecision === 'reject'
            ? '确认结项驳回？'
            : '确认结项通过？'
          : pendingDecision === 'reject'
            ? '确认拒绝申请？'
            : '确认通过设计文档？'
      "
      :message="
        active
          ? mentorPhase === 'final'
            ? `${pendingDecision === 'reject' ? '驳回' : '通过'}「${active.student_name || active.student_email}」的结项（申请 #${active.id}）。`
            : pendingDecision === 'reject'
              ? `拒绝「${active.student_name || active.student_email}」对「${active.project_title}」的申请 #${active.id}。仅发留言不会拒绝。`
              : `通过「${active.student_name || active.student_email}」对「${active.project_title}」的设计（申请 #${active.id}）。通过后名额立即预留并公示；社区/组委会确认后学生方可启动开发。仅发留言不会通过。`
          : ''
      "
      :confirm-text="
        mentorPhase === 'final'
          ? pendingDecision === 'reject'
            ? '确认驳回'
            : '确认结项通过'
          : pendingDecision === 'reject'
            ? '确认拒绝'
            : '确认通过设计'
      "
      :danger="pendingDecision === 'reject'"
      @confirm="runDecide"
    />
    <PdfPreviewModal v-model:open="previewOpen" :url="previewUrl" :title="previewTitle" />

    <header class="mentor-hero">
      <div>
        <p class="eyebrow">导师审核</p>
        <h1 class="page-title">{{ active?.project_title || '审核' }}</h1>
        <p class="page-desc">
          导师同意结项后，材料交给组织，再由组委会统一发布。这里只处理当前这一条。
        </p>
      </div>
      <div class="mentor-nav">
        <RouterLink class="btn secondary sm" to="/mentor">返回工作台</RouterLink>
      </div>
    </header>

    <p v-if="lastActionNote" class="last-action">{{ lastActionNote }}</p>

    <p v-if="error" class="error">{{ error }}</p>
    <p v-else-if="loading" class="muted">加载中…</p>

    <template v-else>
      <div class="mentor-layout single">
        <aside v-if="false" class="queue card">
          <h2>队列</h2>
          <div class="queue-tabs">
            <button
              type="button"
              :class="{ on: queueTab === 'review' }"
              @click="switchTab('review')"
            >
              申请审核 {{ queueReview.length }}
            </button>
            <button type="button" :class="{ on: queueTab === 'dev' }" @click="switchTab('dev')">
              开发中 {{ queueDev.length }}
            </button>
            <button
              type="button"
              :class="{ on: queueTab === 'final' }"
              @click="switchTab('final')"
            >
              结项 {{ queueFinal.length }}
            </button>
          </div>
          <p v-if="!visibleQueue.length" class="muted empty">本分类暂无条目。</p>
          <button
            v-for="a in visibleQueue"
            :key="a.id"
            type="button"
            class="queue-item"
            :class="{ active: a.id === activeId }"
            @click="selectApp(a.id)"
          >
            <div class="queue-top">
              <strong>{{ a.student_name || a.student_email || `申请人` }}</strong>
              <span class="badge" :class="statusTone(a.status)">{{ statusLabel(a.status) }}</span>
            </div>
            <p class="queue-proj">{{ a.project_title || `项目 #${a.project_id}` }}</p>
            <p class="queue-snip">{{ a.statement || '（未填写陈述）' }}</p>
          </button>
        </aside>

        <section class="review card">
          <template v-if="active">
            <header class="review-head">
              <div>
                <p class="reviewing-who">正在审核</p>
                <h2>{{ active.student_name || active.student_email || '申请人' }}</h2>
                <p class="muted">
                  {{ active.project_title || `项目 #${active.project_id}` }}
                  <template v-if="active.student_email"> · {{ active.student_email }}</template>
                  · <strong>申请 #{{ active.id }}</strong>
                </p>
              </div>
              <div class="review-tags">
                <span class="badge" :class="statusTone(active.status)">{{ statusLabel(active.status) }}</span>
                <span class="muted">{{ nodeLabel(active.current_node) }}</span>
              </div>
            </header>

            <p v-if="detailLoading" class="muted">刷新材料…</p>

            <div class="materials">
              <h3>申请材料</h3>
              <div v-if="active.statement" class="statement">{{ active.statement }}</div>
              <p v-else class="muted">学生未填写申请陈述（选填）</p>

              <div class="pdf-grid">
                <button
                  v-if="pdfs.resume"
                  type="button"
                  class="pdf-card"
                  @click="previewResume"
                >
                  <span class="pdf-tag">简历 PDF</span>
                  <strong>{{ fileLabel(pdfs.resume) }}</strong>
                  <span class="muted">点击站内预览</span>
                </button>
                <button
                  v-if="pdfs.design"
                  type="button"
                  class="pdf-card design"
                  @click="previewDesign"
                >
                  <span class="pdf-tag design">项目设计 PDF</span>
                  <strong>{{ fileLabel(pdfs.design) }}</strong>
                  <span class="muted">点击站内预览</span>
                </button>
                <div v-if="!pdfs.resume && !pdfs.design" class="pdf-empty">
                  该申请未上传简历或项目设计 PDF。
                </div>
              </div>
            </div>

            <div class="timeline-block">
              <h3>审核进度</h3>
              <ReviewTimeline :application="active" compact :preview-count="4" />
            </div>

            <div v-if="studentLogs.length" class="dev-logs">
              <h3>学生提交（进展 / 验收材料）</h3>
              <div class="feed-scroll">
                <table class="feed-table">
                  <thead>
                    <tr>
                      <th>时间</th>
                      <th>类型</th>
                      <th>说明</th>
                      <th>交付件</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="m in studentLogs" :key="m.id">
                      <td>{{ formatDateTime(m.created_at) }}</td>
                      <td>{{ kindLabel(m.kind) }}</td>
                      <td><EllipsisTip :text="m.body || '—'" /></td>
                      <td>
                        <a
                          v-if="m.attachment_url"
                          :href="m.attachment_url"
                          target="_blank"
                          rel="noopener"
                        >{{ m.attachment_name || fileLabel(m.attachment_url) }}</a>
                        <span v-else class="muted">—</span>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            <div
              v-if="mentorPhase === 'dev' && (progressLogs.length || midtermLogs.length || feedbackLogs.length)"
              class="dev-logs"
            >
              <h3>进展对话（开发期）</h3>
              <div v-if="progressLogs.length" class="log-group">
                <h4>学生进展</h4>
                <ul>
                  <li v-for="m in [...progressLogs].reverse().slice(0, 6)" :key="m.id">
                    <time>{{ formatDateTime(m.created_at) }}</time>
                    <p>{{ m.body }}</p>
                  </li>
                </ul>
              </div>
              <div v-if="midtermLogs.length" class="log-group">
                <h4>中期反馈</h4>
                <ul>
                  <li v-for="m in [...midtermLogs].reverse()" :key="m.id">
                    <time>{{ formatDateTime(m.created_at) }}</time>
                    <p>{{ m.body }}</p>
                  </li>
                </ul>
              </div>
              <div v-if="feedbackLogs.length" class="log-group">
                <h4>已发留言</h4>
                <ul>
                  <li v-for="m in [...feedbackLogs].reverse().slice(0, 4)" :key="m.id">
                    <time>{{ formatDateTime(m.created_at) }}</time>
                    <EllipsisTip :text="m.body" />
                  </li>
                </ul>
              </div>
            </div>

            <!-- 申请审核期：一个意见框 + 通过/拒绝/仅留言 -->
            <template v-if="mentorPhase === 'app_review'">
              <div v-if="feedbackLogs.length" class="dev-logs">
                <h3>已发留言</h3>
                <ul class="solo-log">
                  <li v-for="m in [...feedbackLogs].reverse().slice(0, 4)" :key="m.id">
                    <time>{{ formatDateTime(m.created_at) }}</time>
                    <p>{{ m.body }}</p>
                  </li>
                </ul>
              </div>
              <div class="decide-panel">
                <p class="phase-hint">
                  正在审：<strong>{{ active.student_name || active.student_email }}</strong>
                  · 申请 #{{ active.id }} · 阶段：审核设计文档（尚未录取）。
                  「仅发留言」不会通过；须点「通过设计」并确认。
                </p>
                <label class="form">
                  审核意见（可选）
                  <textarea
                    v-model="comment"
                    rows="3"
                    placeholder="给学生的说明：可随「通过/拒绝」一并记录，也可点「仅发留言」不改状态"
                  />
                </label>
                <div class="decide-actions">
                  <button class="btn success lg" type="button" :disabled="busy" @click="askDecide('approve')">
                    通过设计
                  </button>
                  <button class="btn danger lg" type="button" :disabled="busy" @click="askDecide('reject')">
                    拒绝申请
                  </button>
                  <button class="btn secondary" type="button" :disabled="busy" @click="sendFeedback">
                    仅发留言
                  </button>
                  <RouterLink class="btn secondary" :to="`/projects/${active.project_id}`">查看项目</RouterLink>
                </div>
              </div>
            </template>

            <!-- 开发期：进展留言 + 取消接取（不再出现申请通过/拒绝） -->
            <template v-else-if="mentorPhase === 'dev'">
              <div class="feedback-panel">
                <label class="form">
                  进展指导留言（不改变任务状态）
                  <textarea
                    v-model="feedbackText"
                    rows="2"
                    placeholder="针对进展/中期的建议，学生会在申请详情看到"
                  />
                </label>
                <button class="btn secondary" type="button" :disabled="busy" @click="sendFeedback">
                  发送留言
                </button>
              </div>
              <div class="decide-panel dev-actions">
                <p class="phase-hint">开发期操作：指导沟通或管理接取关系。结项请等学生提交验收后，在「结项」队列处理。</p>
                <div class="decide-actions">
                  <button class="btn danger lg" type="button" :disabled="busy" @click="cancelAssignment">
                    取消接取
                  </button>
                  <RouterLink class="btn secondary" :to="`/projects/${active.project_id}`">查看项目</RouterLink>
                </div>
              </div>
            </template>

            <!-- 结项审核 -->
            <template v-else-if="mentorPhase === 'final'">
              <div class="decide-panel">
                <label class="form">
                  结项意见（可选）
                  <textarea v-model="comment" rows="3" placeholder="结项通过/驳回说明" />
                </label>
                <div class="decide-actions">
                  <button class="btn success lg" type="button" :disabled="busy" @click="askDecide('approve')">
                    结项通过
                  </button>
                  <button class="btn danger lg" type="button" :disabled="busy" @click="askDecide('reject')">
                    结项驳回
                  </button>
                  <RouterLink class="btn secondary" :to="`/projects/${active.project_id}`">查看项目</RouterLink>
                </div>
              </div>
            </template>

            <p v-else class="muted">当前状态无需导师操作。</p>
          </template>
          <p v-else class="muted empty">从左侧选择一条申请进行审核。</p>
        </section>

        <aside class="side card">
          <h2>我负责的项目</h2>
          <p class="muted tip">导师侧以审核与结项对接为主；新建项目请走组织工作台。</p>
          <p v-if="!myProjects.length" class="muted">暂无指派给你的项目。</p>
          <ul v-else class="proj-list">
            <li v-for="p in myProjects.slice(0, 8)" :key="p.id">
              <RouterLink :to="`/projects/${p.id}`">{{ p.title }}</RouterLink>
            </li>
          </ul>
          <RouterLink class="more" to="/mentor/projects">查看全部 →</RouterLink>
        </aside>
      </div>
    </template>
  </div>
</template>

<style scoped>
.feed-scroll {
  max-height: 280px;
  overflow: auto;
  border: 1px solid #e8ebf0;
  border-radius: 8px;
}
.feed-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.86rem;
}
.feed-table th,
.feed-table td {
  text-align: left;
  padding: 0.55rem 0.7rem;
  border-bottom: 1px solid #f3f4f6;
  vertical-align: top;
}
.feed-table th {
  background: #fafafa;
  color: #6b7280;
  font-weight: 650;
  position: sticky;
  top: 0;
}
.mentor-page.wide {
  max-width: none;
  width: 100%;
  background: linear-gradient(180deg, #f3f6fb 0%, #fff 180px);
  margin: 0;
  padding-top: 1.25rem;
}
.mentor-hero {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
  align-items: flex-start;
  margin-bottom: 1.25rem;
}
.eyebrow {
  margin: 0 0 0.25rem;
  font-size: 0.8rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  color: #1e3a5f;
}
.page-desc {
  margin: 0.35rem 0 0;
  color: #64748b;
  max-width: 42rem;
}
.mentor-nav {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  align-items: center;
}
.reviewing-who {
  margin: 0 0 0.15rem;
  font-size: 0.75rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  color: #2563eb;
  text-transform: uppercase;
}
.last-action {
  margin: 0 0 1rem;
  padding: 0.65rem 0.9rem;
  border-radius: 10px;
  background: #ecfdf5;
  border: 1px solid #6ee7b7;
  color: #065f46;
  font-size: 0.9rem;
  font-weight: 600;
}
.pill {
  display: inline-flex;
  padding: 0.35rem 0.75rem;
  border-radius: 999px;
  background: #eef4fb;
  color: #1e3a5f;
  font-weight: 700;
  font-size: 0.85rem;
  border: 1px solid #c5d4ea;
}
.pill.soft {
  background: #f8fafc;
  font-weight: 600;
  color: #64748b;
}
.queue-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  margin: -0.25rem 0 0.85rem;
}
.queue-tabs button {
  border: 1px solid #e2e8f0;
  background: #fff;
  border-radius: 8px;
  padding: 0.35rem 0.55rem;
  font-size: 0.78rem;
  font-weight: 600;
  color: #64748b;
  cursor: pointer;
}
.queue-tabs button.on {
  border-color: #2563eb;
  background: #eff6ff;
  color: #1d4ed8;
}
.solo-log {
  list-style: none;
  margin: 0;
  padding: 0;
}
.solo-log li {
  padding: 0.4rem 0;
  border-top: 1px solid #eef2f7;
}
.solo-log time {
  display: block;
  font-size: 0.72rem;
  color: #94a3b8;
}
.solo-log p {
  margin: 0.15rem 0 0;
  font-size: 0.86rem;
  white-space: pre-wrap;
}
.phase-hint {
  margin: 0 0 0.75rem;
  font-size: 0.86rem;
  color: #64748b;
  line-height: 1.45;
}
.decide-panel.dev-actions {
  background: #fffbeb;
  border-color: #fde68a;
}
.mentor-layout {
  display: grid;
  grid-template-columns: minmax(240px, 0.85fr) minmax(0, 1.6fr) minmax(200px, 0.75fr);
  gap: 1rem;
  align-items: start;
}
.mentor-layout.single {
  grid-template-columns: minmax(0, 1.6fr) minmax(200px, 0.7fr);
}
@media (max-width: 1100px) {
  .mentor-layout {
    grid-template-columns: minmax(220px, 0.9fr) minmax(0, 1.4fr);
  }
  .side {
    grid-column: 1 / -1;
  }
}
@media (max-width: 720px) {
  .mentor-layout {
    grid-template-columns: 1fr;
  }
}
.queue h2,
.review h2,
.side h2 {
  margin: 0 0 0.85rem;
  font-size: 1.05rem;
}
.queue-item {
  display: block;
  width: 100%;
  text-align: left;
  border: 1px solid #e2e8f0;
  background: #f8fafc;
  border-radius: 12px;
  padding: 0.85rem 0.95rem;
  margin-bottom: 0.55rem;
  cursor: pointer;
}
.queue-item.active {
  border-color: #2563eb;
  background: #eff6ff;
  box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.12);
}
.queue-top {
  display: flex;
  justify-content: space-between;
  gap: 0.5rem;
}
.queue-proj {
  margin: 0.3rem 0 0;
  font-size: 0.85rem;
  color: #334155;
  font-weight: 600;
}
.queue-snip {
  margin: 0.25rem 0 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 0.8rem;
  color: #94a3b8;
}
.review-head {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
  padding-bottom: 1rem;
  border-bottom: 1px solid #f1f5f9;
  margin-bottom: 1rem;
}
.review-head h2 {
  margin: 0 0 0.25rem;
}
.review-tags {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 0.25rem;
}
.materials h3,
.timeline-block h3 {
  margin: 0 0 0.65rem;
  font-size: 0.95rem;
}
.statement {
  white-space: pre-wrap;
  background: #f8fafc;
  border-radius: 10px;
  padding: 0.85rem 1rem;
  margin: 0 0 0.85rem;
  line-height: 1.55;
  border: 1px solid #e2e8f0;
}
.pdf-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 0.75rem;
  margin-bottom: 1.25rem;
}
.pdf-card {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  padding: 1rem 1.05rem;
  border-radius: 12px;
  border: 1px solid #bfdbfe;
  background: linear-gradient(165deg, #eff6ff 0%, #fff 55%);
  text-align: left;
  cursor: pointer;
  color: inherit;
  font: inherit;
}
.pdf-card.design {
  border-color: #c4b5fd;
  background: linear-gradient(165deg, #f5f3ff 0%, #fff 55%);
}
.pdf-tag {
  align-self: flex-start;
  font-size: 0.72rem;
  font-weight: 700;
  color: #1d4ed8;
  background: #dbeafe;
  padding: 0.15rem 0.45rem;
  border-radius: 6px;
}
.pdf-tag.design {
  color: #6d28d9;
  background: #ede9fe;
}
.pdf-empty {
  grid-column: 1 / -1;
  padding: 0.9rem 1rem;
  border-radius: 10px;
  background: #fffbeb;
  border: 1px dashed #fbbf24;
  color: #92400e;
  font-size: 0.88rem;
}
.timeline-block {
  margin-bottom: 1.25rem;
}
.dev-logs {
  margin-bottom: 1rem;
  padding: 0.85rem 1rem;
  border-radius: 10px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
}
.dev-logs h3 {
  margin: 0 0 0.65rem;
  font-size: 0.95rem;
}
.log-group {
  margin-bottom: 0.75rem;
}
.log-group h4 {
  margin: 0 0 0.35rem;
  font-size: 0.8rem;
  color: #64748b;
}
.log-group ul {
  list-style: none;
  margin: 0;
  padding: 0;
  max-height: 140px;
  overflow-y: auto;
}
.log-group li {
  padding: 0.4rem 0;
  border-top: 1px solid #eef2f7;
}
.log-group time {
  display: block;
  font-size: 0.72rem;
  color: #94a3b8;
}
.log-group p {
  margin: 0.15rem 0 0;
  font-size: 0.86rem;
  white-space: pre-wrap;
  color: #334155;
}
.feedback-panel {
  margin-bottom: 1rem;
  padding: 0.85rem 1rem;
  border-radius: 10px;
  border: 1px dashed #bfdbfe;
  background: #f8fbff;
}
.feedback-panel .btn {
  margin-top: 0.5rem;
}
.decide-panel {
  position: sticky;
  bottom: 0.75rem;
  padding: 1rem;
  border-radius: 12px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  box-shadow: 0 -8px 24px rgba(15, 35, 70, 0.06);
  z-index: 2;
}
.decide-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.55rem;
  margin-top: 0.85rem;
}
.btn.lg {
  min-width: 7rem;
  padding: 0.65rem 1.15rem;
}
.empty {
  padding: 1.5rem 0.5rem;
  text-align: center;
}
.side .tip {
  font-size: 0.85rem;
  margin: -0.35rem 0 0.75rem;
}
.proj-list {
  list-style: none;
  padding: 0;
  margin: 0 0 0.75rem;
}
.proj-list li {
  padding: 0.45rem 0;
  border-bottom: 1px solid #f1f5f9;
}
.more {
  font-weight: 600;
  font-size: 0.9rem;
}
</style>
