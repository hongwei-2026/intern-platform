<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import CommunityDesk from '@/views/community/PendingReviewsView.vue'
import CommunityFinalSubmitView from '@/views/org/CommunityFinalSubmitView.vue'
import api, { withFileAuth } from '@/api/client'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import ToastFeedback from '@/components/ToastFeedback.vue'
import LogoUploadField from '@/components/LogoUploadField.vue'
import CommunityIntroEditor from '@/components/CommunityIntroEditor.vue'
import CommunityIntroView from '@/components/CommunityIntroView.vue'
import type { ApplicationOut, CommunityIntroBody, CommunityMemberOut, CommunityOut, ProjectOut } from '@/api/types'
import { useAuthStore } from '@/stores/auth'
import { projectStatusLabel, statusLabel, statusTone } from '@/utils/statusLabel'

type Tab = 'home' | 'mentors' | 'projects' | 'liaison' | 'selection' | 'finals' | 'rewards'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const toast = ref<InstanceType<typeof ToastFeedback> | null>(null)
const unpublishOpen = ref(false)
const unpublishTarget = ref<ProjectOut | null>(null)

const tab = ref<Tab>(readOrgTab(route.query.tab))

function readOrgTab(value: unknown): Tab {
  const name = String(value || 'home')
  return (
    ['home', 'mentors', 'projects', 'liaison', 'selection', 'finals', 'rewards'] as string[]
  ).includes(name)
    ? (name as Tab)
    : 'home'
}

function openTab(next: Tab) {
  tab.value = next
  const query = next === 'home' ? {} : { tab: next }
  void router.replace({ path: '/org', query })
}

watch(
  () => route.query.tab,
  (value) => {
    tab.value = readOrgTab(value)
    if (tab.value === 'selection') void loadSelectionQueue().catch(() => undefined)
    if (tab.value === 'finals') void loadFinalQueue().catch(() => undefined)
    if (tab.value === 'rewards') void loadRewards().catch(() => undefined)
  },
)
const myCommunity = ref<CommunityOut | null>(null)
const mentors = ref<CommunityMemberOut[]>([])
const orgProjects = ref<ProjectOut[]>([])
const selectionQueue = ref<ApplicationOut[]>([])
const finalQueue = ref<ApplicationOut[]>([])
const selectionBusy = ref(false)
const selectionNote = ref('')
const selectionTarget = ref<ApplicationOut | null>(null)
const selectionDecision = ref<'approve' | 'reject' | null>(null)
const selectionOpen = ref(false)
type RewardItem = {
  application_id: number
  project_title: string
  student_name?: string | null
  body: string
  attachment_url?: string | null
  attachment_name?: string | null
  created_at?: string | null
  decision?: string
  decision_note?: string | null
}
const rewards = ref<RewardItem[]>([])
const rewardYears = ref<number[]>([])
const rewardYear = ref(String(new Date().getFullYear()))
const rewardQuery = ref('')
const rewardStatus = ref('pending')
const rejectId = ref<number | null>(null)
const rejectNote = ref('')
const busy = ref(false)
const showInvite = ref(false)

const previewId = ref<number | null>(null)
const previewOffline = ref(false)
const editForm = ref({
  mentor_id: '' as string | number,
  title: '',
  summary: '',
  description: '',
  tech_stack: '',
  difficulty: 'medium',
  quota: 1,
  repo_url: '',
})

const projectForm = ref({
  mentor_id: '' as string | number,
  title: '',
  summary: '',
  description: '',
  tech_stack: '',
  difficulty: 'medium',
  quota: 1,
  repo_url: '',
})

const homeForm = ref({
  name: '',
  description: '',
  homepage_url: '',
  gitea_org_url: '',
  mirror_doc_url: '',
  logo_url: '',
  tags: [] as string[],
  intro_body: { blocks: [] } as CommunityIntroBody,
})

const isCommittee = computed(() => auth.hasRole('committee'))
const isCommunityAdmin = computed(() => auth.hasRole('community_admin'))
const rewardYearChoices = computed(() => {
  const years = new Set(rewardYears.value)
  years.add(new Date().getFullYear())
  return [...years].sort((a, b) => b - a)
})

/** 右侧预览：去掉空段落，强制随 intro 变化刷新 */
const previewIntro = computed(() => {
  const blocks = homeForm.value.intro_body?.blocks || []
  return {
    blocks: blocks.filter((b) => {
      if (b.type === 'paragraph' || b.type === 'heading') return !!(b.text && b.text.trim())
      if (b.type === 'image' || b.type === 'video') return !!(b.url && String(b.url).trim())
      return true
    }),
  }
})
const previewIntroKey = computed(() =>
  (homeForm.value.intro_body?.blocks || [])
    .map((b) => `${b.type}:${b.url || ''}:${(b.text || '').slice(0, 24)}`)
    .join('|'),
)

function mentorName(project: ProjectOut) {
  const hit = mentors.value.find((m) => m.user_id === project.mentor_id)
  return hit ? hit.display_name || hit.email : `导师 #${project.mentor_id}`
}

function syncHomeForm(c: CommunityOut) {
  homeForm.value = {
    name: c.name || '',
    description: c.description || '',
    homepage_url: c.homepage_url || '',
    gitea_org_url: c.gitea_org_url || '',
    mirror_doc_url: c.mirror_doc_url || '',
    logo_url: c.logo_url || '',
    tags: [...(c.tags || [])],
    intro_body: c.intro_body?.blocks?.length
      ? { blocks: c.intro_body.blocks.map((b) => ({ ...b })) }
      : { blocks: [] },
  }
}

async function loadMentors() {
  if (!myCommunity.value) {
    mentors.value = []
    return
  }
  try {
    const { data } = await api.get<CommunityMemberOut[]>(
      `/communities/${myCommunity.value.id}/members`,
      { params: { role: 'mentor' } },
    )
    mentors.value = data
  } catch {
    mentors.value = []
  }
}

async function loadProjects() {
  if (!myCommunity.value) {
    orgProjects.value = []
    return
  }
  const cid = myCommunity.value.id
  const [d, p, off] = await Promise.all([
    api.get<ProjectOut[]>('/projects', { params: { community_id: cid, status: 'draft' } }),
    api.get<ProjectOut[]>('/projects', { params: { community_id: cid, status: 'published' } }),
    api.get<ProjectOut[]>('/projects', { params: { community_id: cid, status: 'offline' } }),
  ])
  const map = new Map<number, ProjectOut>()
  for (const row of [...d.data, ...p.data, ...off.data]) map.set(row.id, row)
  orgProjects.value = [...map.values()].sort((a, b) => b.id - a.id)
}

async function load() {
  try {
    const { data } = await api.get<CommunityOut[]>('/communities/admin-of')
    myCommunity.value = data[0] || null
    if (myCommunity.value) {
      syncHomeForm(myCommunity.value)
      await Promise.all([
        loadMentors(),
        loadProjects(),
        loadSelectionQueue(),
        loadFinalQueue(),
        loadRewards(),
      ])
    }
  } catch {
    myCommunity.value = null
  }
}

async function loadSelectionQueue() {
  const { data } = await api.get<ApplicationOut[]>('/applications/inbox')
  selectionQueue.value = data.filter((item) => item.status === 'community_review')
}

async function loadFinalQueue() {
  const { data } = await api.get<ApplicationOut[]>('/applications/inbox')
  finalQueue.value = data.filter((item) => item.status === 'community_final_review')
}

function askSelection(row: ApplicationOut, decision: 'approve' | 'reject') {
  selectionTarget.value = row
  selectionDecision.value = decision
  selectionNote.value = decision === 'approve' ? '社区审核通过' : ''
  selectionOpen.value = true
}

async function confirmSelection() {
  const row = selectionTarget.value
  const decision = selectionDecision.value
  if (!row || !decision) return
  if (decision === 'reject' && selectionNote.value.trim().length < 2) {
    toast.value?.show('退回请写明原因', 'err')
    selectionOpen.value = true
    return
  }
  selectionBusy.value = true
  try {
    await api.post(`/applications/${row.id}/reviews`, {
      decision,
      comment: selectionNote.value.trim() || '社区审核通过',
      version: row.version,
    })
    toast.value?.show(
      decision === 'approve' ? '已通过，组委会已自动接收中选' : '已退回该申请',
      decision === 'approve' ? 'ok' : 'err',
    )
    selectionNote.value = ''
    selectionTarget.value = null
    selectionDecision.value = null
    await loadSelectionQueue()
  } catch (e: unknown) {
    toast.value?.show(e instanceof Error ? e.message : '处理失败', 'err')
  } finally {
    selectionBusy.value = false
  }
}

async function loadRewards() {
  const year = rewardYear.value === 'all' ? undefined : Number(rewardYear.value)
  const { data } = await api.get<{ years: number[]; items: RewardItem[] }>('/applications/rewards/inbox', {
    params: { year, q: rewardQuery.value.trim(), status: rewardStatus.value },
  })
  rewardYears.value = data.years
  rewards.value = data.items
}

async function decideReward(id: number, decision: 'approved' | 'rejected') {
  if (decision === 'rejected' && !rejectNote.value.trim()) {
    toast.value?.show('驳回时请写下原因', 'err')
    return
  }
  busy.value = true
  try {
    await api.post(`/applications/${id}/reward-decision`, {
      decision,
      note: decision === 'rejected' ? rejectNote.value.trim() : null,
    })
    toast.value?.show(decision === 'approved' ? '已通过这份奖励申请' : '已驳回这份奖励申请', 'ok')
    rejectId.value = null
    rejectNote.value = ''
    await loadRewards()
  } catch (e: unknown) {
    toast.value?.show(e instanceof Error ? e.message : '处理失败', 'err')
  } finally {
    busy.value = false
  }
}

async function saveHome() {
  if (!myCommunity.value) return
  busy.value = true
  try {
    const { data } = await api.patch<CommunityOut>(`/communities/${myCommunity.value.id}`, {
      name: homeForm.value.name.trim(),
      description: homeForm.value.description || null,
      homepage_url: homeForm.value.homepage_url || null,
      gitea_org_url: homeForm.value.gitea_org_url || null,
      mirror_doc_url: homeForm.value.mirror_doc_url || null,
      logo_url: homeForm.value.logo_url || null,
      tags: homeForm.value.tags,
      intro_body: homeForm.value.intro_body,
    })
    myCommunity.value = data
    syncHomeForm(data)
    toast.value?.show('已发布到公开主页', 'ok')
  } catch (e: unknown) {
    toast.value?.show(e instanceof Error ? e.message : '保存失败', 'err')
  } finally {
    busy.value = false
  }
}

async function saveIntroOnly() {
  await saveHome()
}

async function copyInvite() {
  const code = myCommunity.value?.invite_code
  if (!code) return
  try {
    await navigator.clipboard.writeText(code)
    toast.value?.show('已复制，请私下发给导师', 'ok')
  } catch {
    toast.value?.show(code, 'ok')
  }
}

async function reassignMentor(projectId: number, mentorId: string) {
  const mid = Number(mentorId)
  if (!mid) return
  busy.value = true
  try {
    await api.patch(`/projects/${projectId}`, { mentor_id: mid })
    toast.value?.show('已改派', 'ok')
    await loadProjects()
  } catch (e: unknown) {
    toast.value?.show(e instanceof Error ? e.message : '改派失败', 'err')
  } finally {
    busy.value = false
  }
}

function onReassignChange(projectId: number, event: Event) {
  const el = event.target as HTMLSelectElement
  void reassignMentor(projectId, el.value)
}

async function createProject() {
  if (!myCommunity.value) return
  busy.value = true
  try {
    await api.post<ProjectOut>('/projects', {
      community_id: myCommunity.value.id,
      mentor_id: Number(projectForm.value.mentor_id),
      title: projectForm.value.title.trim(),
      summary: projectForm.value.summary || null,
      description: projectForm.value.description || null,
      tech_stack: projectForm.value.tech_stack
        ? projectForm.value.tech_stack.split(/[,，]/).map((s) => s.trim()).filter(Boolean)
        : null,
      difficulty: projectForm.value.difficulty || null,
      quota: Number(projectForm.value.quota) || 1,
      repo_url: projectForm.value.repo_url || null,
    })
    toast.value?.show('项目已发布，已通知负责导师', 'ok')
    projectForm.value = {
      ...projectForm.value,
      title: '',
      summary: '',
      description: '',
      mentor_id: '',
    }
    await loadProjects()
  } catch (e: unknown) {
    toast.value?.show(e instanceof Error ? e.message : '创建失败', 'err')
  } finally {
    busy.value = false
  }
}

async function savePreview() {
  if (!previewId.value) return
  busy.value = true
  try {
    await api.patch(`/projects/${previewId.value}`, {
      mentor_id: Number(editForm.value.mentor_id) || undefined,
      title: editForm.value.title.trim(),
      summary: editForm.value.summary || null,
      description: editForm.value.description || null,
      tech_stack: editForm.value.tech_stack
        ? editForm.value.tech_stack.split(/[,，]/).map((s) => s.trim()).filter(Boolean)
        : null,
      difficulty: editForm.value.difficulty || null,
      quota: Number(editForm.value.quota) || 1,
      repo_url: editForm.value.repo_url || null,
    })
    toast.value?.show(previewOffline.value ? '修改已保存。要上线再点重新发布' : '已保存', 'ok')
    await loadProjects()
  } catch (e: unknown) {
    toast.value?.show(e instanceof Error ? e.message : '保存失败', 'err')
  } finally {
    busy.value = false
  }
}

function projectFinished(project: ProjectOut) {
  return (project.assignees || []).some((item) =>
    ['completed', 'community_final_review', 'committee_final_review'].includes(item.status),
  )
}

function stackText(raw: ProjectOut['tech_stack']) {
  if (Array.isArray(raw)) return raw.join(', ')
  const text = String(raw || '').trim()
  if (text.startsWith('[')) {
    try {
      const parsed = JSON.parse(text)
      if (Array.isArray(parsed)) return parsed.map((item) => String(item)).join(', ')
    } catch {
      /* 按原文显示 */
    }
  }
  return text
}

function cancelPreview() {
  previewId.value = null
  previewOffline.value = false
}

function openPreview(p: ProjectOut) {
  if (p.status === 'offline' && projectFinished(p)) {
    toast.value?.show('已有学生结项，不能再改任务内容', 'err')
    return
  }
  previewId.value = p.id
  previewOffline.value = p.status === 'offline'
  editForm.value = {
    mentor_id: p.mentor_id,
    title: p.title,
    summary: p.summary || '',
    description: p.description || '',
    tech_stack: stackText(p.tech_stack),
    difficulty: p.difficulty || 'medium',
    quota: p.quota,
    repo_url: p.repo_url || '',
  }
}

async function publish(id: number) {
  busy.value = true
  try {
    await api.post(`/projects/${id}/publish`)
    toast.value?.show('已发布', 'ok')
    if (previewId.value === id) cancelPreview()
    await loadProjects()
  } catch (e: unknown) {
    toast.value?.show(e instanceof Error ? e.message : '发布失败', 'err')
  } finally {
    busy.value = false
  }
}

function askUnpublish(project: ProjectOut) {
  unpublishTarget.value = project
  unpublishOpen.value = true
}

async function confirmUnpublish() {
  const project = unpublishTarget.value
  unpublishOpen.value = false
  if (!project) return
  busy.value = true
  try {
    await api.post(`/projects/${project.id}/unpublish`)
    toast.value?.show('已下架', 'ok')
    await loadProjects()
  } catch (e: unknown) {
    toast.value?.show(e instanceof Error ? e.message : '下架失败', 'err')
  } finally {
    unpublishTarget.value = null
    busy.value = false
  }
}

onMounted(async () => {
  if (!auth.user) await auth.fetchMe()
  if (auth.hasRole('mentor') && !isCommunityAdmin.value && !isCommittee.value) {
    router.replace('/mentor')
    return
  }
  if (isCommittee.value && !isCommunityAdmin.value) {
    return
  }
  await load()
})
</script>

<template>
  <div class="page wide org-console">
    <ToastFeedback ref="toast" />
    <ConfirmDialog
      :open="unpublishOpen"
      title="下架项目"
      :message="
        unpublishTarget
          ? `下架「${unpublishTarget.title}」后，学生在社区主页看不到它，也不能新申请。已有申请会保留。`
          : ''
      "
      confirm-text="下架"
      cancel-text="取消"
      danger
      @update:open="unpublishOpen = $event"
      @cancel="unpublishTarget = null"
      @confirm="confirmUnpublish"
    />
    <ConfirmDialog
      :open="selectionOpen"
      :title="selectionDecision === 'reject' ? '退回申请？' : '确认通过并报送组委会？'"
      :message="
        selectionTarget
          ? selectionDecision === 'reject'
            ? `退回「${selectionTarget.student_name || '学生'}」对「${selectionTarget.project_title}」的申请。`
            : `通过「${selectionTarget.student_name || '学生'}」后，组委会会自动接收中选，不必再点一次。`
          : ''
      "
      :confirm-text="selectionDecision === 'reject' ? '确认退回' : '确认通过'"
      cancel-text="取消"
      :danger="selectionDecision === 'reject'"
      @update:open="selectionOpen = $event"
      @cancel="selectionTarget = null; selectionDecision = null"
      @confirm="confirmSelection"
    >
      <label class="dlg-note">
        {{ selectionDecision === 'reject' ? '退回原因' : '审核说明（可选）' }}
        <textarea v-model="selectionNote" rows="3" maxlength="500" />
      </label>
    </ConfirmDialog>

    <header class="head">
      <div>
        <h1>{{ myCommunity?.name || '组织工作台' }}</h1>
        <p class="sub">改对外展示、导师和项目。已发布的主页从个人中心查看。</p>
      </div>
    </header>

    <section v-if="!myCommunity" class="panel">
      <p v-if="isCommittee" class="muted">
        组委会不挂在某一个组织名下。查看各社区和任务请用顶部「查看项目」，处理终审和停用仍回组委会工作台。
      </p>
      <p v-else class="muted">尚未绑定可管理的社区，请联系组委会开通。</p>
    </section>

    <template v-else>
      <nav class="tabs" aria-label="管理分区">
        <button type="button" :class="{ on: tab === 'home' }" @click="openTab('home')">社区主页</button>
        <button type="button" :class="{ on: tab === 'mentors' }" @click="openTab('mentors')">
          导师 <span>{{ mentors.length }}</span>
        </button>
        <button type="button" :class="{ on: tab === 'projects' }" @click="openTab('projects')">
          项目 <span>{{ orgProjects.length }}</span>
        </button>
        <button type="button" :class="{ on: tab === 'liaison' }" @click="openTab('liaison')">社区对接</button>
        <button type="button" :class="{ on: tab === 'selection' }" @click="openTab('selection')">
          选拔审核 <span>{{ selectionQueue.length }}</span>
        </button>
        <button type="button" :class="{ on: tab === 'rewards' }" @click="openTab('rewards')">
          奖励申请 <span>{{ rewards.length }}</span>
        </button>
        <button type="button" :class="{ on: tab === 'finals' }" @click="openTab('finals')">
          结项材料 <span>{{ finalQueue.length }}</span>
        </button>
      </nav>

      <!-- Tab: 主页 — 左编辑 / 右预览 -->
      <section v-if="tab === 'home'" class="panel home-panel">
        <div class="panel-bar">
          <div>
            <h2>对外展示</h2>
            <p class="bar-hint">左边改还没发布的草稿，右边看效果。发布后的主页从个人中心打开。</p>
          </div>
        </div>

        <div class="split">
          <!-- 左：创作区 -->
          <div class="pane edit-pane">
            <h3 class="pane-title">编辑</h3>

            <div class="block basic-block">
              <h4>基本信息</h4>
              <div class="basic-grid">
                <LogoUploadField v-model="homeForm.logo_url" class="basic-logo" />
                <label class="span-2">名称<input v-model="homeForm.name" required /></label>
                <label class="span-2"
                  >一句话简介<textarea
                    v-model="homeForm.description"
                    rows="2"
                    placeholder="列表与主页顶部展示"
                  /></label>
                <label>官网<input v-model="homeForm.homepage_url" type="url" placeholder="https://" /></label>
                <label>仓库 / Gitea<input v-model="homeForm.gitea_org_url" type="url" /></label>
                <label class="span-2">文档 / 镜像<input v-model="homeForm.mirror_doc_url" type="url" /></label>
              </div>
            </div>

            <div class="block create-block">
              <h4>创作介绍</h4>
              <CommunityIntroEditor
                v-model="homeForm.intro_body"
                v-model:tags="homeForm.tags"
                compact
                @publish="saveIntroOnly"
              />
            </div>
          </div>

          <!-- 右：预览区 -->
          <aside class="pane preview-pane">
            <h3 class="pane-title">
              <RouterLink class="preview-jump" :to="`/communities/${myCommunity.slug}`">预览页 ›</RouterLink>
            </h3>
            <div class="live">
              <header class="live-head">
                <div class="live-logo">
                  <img v-if="homeForm.logo_url" :src="homeForm.logo_url" alt="" />
                  <span v-else>{{ (homeForm.name || '?').slice(0, 1) }}</span>
                </div>
                <div>
                  <h4>{{ homeForm.name || '社区名称' }}</h4>
                  <a
                    v-if="homeForm.homepage_url"
                    class="live-link"
                    :href="homeForm.homepage_url"
                    target="_blank"
                    rel="noopener"
                  >官网主页：点击前往 ›</a>
                  <p v-else class="live-miss">暂未填写官网</p>
                </div>
              </header>
              <p class="live-desc">{{ homeForm.description || '一句话简介会出现在这里' }}</p>
              <div v-if="homeForm.tags.length" class="live-tags">
                <span v-for="t in homeForm.tags" :key="t">{{ t }}</span>
              </div>
              <div v-else class="live-miss">标签会出现在这里</div>
              <div class="live-intro">
                <CommunityIntroView
                  :key="previewIntroKey"
                  :body="previewIntro"
                  fallback="介绍正文、图片、视频会显示在这里"
                />
              </div>
            </div>
          </aside>
        </div>
        <div class="publish-bar">
          <button class="btn" type="button" :disabled="busy" @click="saveHome">
            {{ busy ? '发布中…' : '发布到公开主页' }}
          </button>
        </div>
      </section>

      <!-- Tab: 导师 -->
      <section v-else-if="tab === 'mentors'" class="panel">
        <h2>导师邀请</h2>
        <p class="hint">导师在登录页用邀请码自助注册。邀请码默认隐藏，勿公开给学生。</p>
        <div class="invite">
          <code>{{ showInvite ? myCommunity.invite_code || '—' : '••••••••' }}</code>
          <button class="btn sm secondary" type="button" @click="showInvite = !showInvite">
            {{ showInvite ? '隐藏' : '显示' }}
          </button>
          <button class="btn sm" type="button" @click="copyInvite">复制</button>
        </div>

        <h3 class="subh">已加入（{{ mentors.length }}）</h3>
        <div v-if="!mentors.length" class="empty">暂无导师</div>
        <div v-else class="scroll">
          <table>
            <thead>
              <tr>
                <th>姓名</th>
                <th>邮箱</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="m in mentors" :key="m.user_id">
                <td>{{ m.display_name }}</td>
                <td>{{ m.email }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <!-- Tab: 项目 -->
      <section v-else-if="tab === 'projects'" class="panel">
        <div class="project-card">
          <h2>新建项目</h2>
          <p class="bar-hint">填完就发布。修改已有项目不会占用这张表。</p>
          <form class="form proj" @submit.prevent="createProject">
            <label>
              导师
              <select v-model="projectForm.mentor_id" required>
                <option disabled value="">选择</option>
                <option v-for="m in mentors" :key="m.user_id" :value="m.user_id">
                  {{ m.display_name }}
                </option>
              </select>
            </label>
            <label>标题<input v-model="projectForm.title" required /></label>
            <label class="full">摘要<input v-model="projectForm.summary" /></label>
            <label class="full">详情<textarea v-model="projectForm.description" rows="3" /></label>
            <label>技术栈<input v-model="projectForm.tech_stack" placeholder="用逗号分开" /></label>
            <label>
              难度
              <select v-model="projectForm.difficulty">
                <option value="easy">基础</option>
                <option value="medium">进阶</option>
                <option value="hard">挑战</option>
              </select>
            </label>
            <label>名额<input v-model.number="projectForm.quota" type="number" min="1" /></label>
            <label>仓库<input v-model="projectForm.repo_url" type="url" /></label>
            <div class="full acts">
              <button class="btn" type="submit" :disabled="busy || !mentors.length">发布项目</button>
            </div>
          </form>
        </div>

        <div v-if="previewId" class="project-card edit">
          <div class="card-head">
            <div>
              <h2>{{ previewOffline ? '修改已下架的项目' : '调整项目' }}</h2>
              <p class="bar-hint">改的是「{{ editForm.title || '当前项目' }}」。新建请用上面那张表。</p>
            </div>
            <button class="btn sm secondary" type="button" @click="cancelPreview">收起</button>
          </div>
          <form class="form proj" @submit.prevent="savePreview">
            <label>
              导师
              <select v-model="editForm.mentor_id" required>
                <option v-for="m in mentors" :key="m.user_id" :value="m.user_id">
                  {{ m.display_name }}
                </option>
              </select>
            </label>
            <label>标题<input v-model="editForm.title" required /></label>
            <label class="full">摘要<input v-model="editForm.summary" /></label>
            <label class="full">详情<textarea v-model="editForm.description" rows="3" /></label>
            <label>技术栈<input v-model="editForm.tech_stack" placeholder="用逗号分开" /></label>
            <label>
              难度
              <select v-model="editForm.difficulty">
                <option value="easy">基础</option>
                <option value="medium">进阶</option>
                <option value="hard">挑战</option>
              </select>
            </label>
            <label>名额<input v-model.number="editForm.quota" type="number" min="1" /></label>
            <label>仓库<input v-model="editForm.repo_url" type="url" /></label>
            <div class="full acts">
              <button class="btn" type="submit" :disabled="busy">保存修改</button>
              <button class="btn secondary" type="button" :disabled="busy" @click="publish(previewId)">
                {{ previewOffline ? '重新发布' : '确认发布' }}
              </button>
            </div>
          </form>
        </div>

        <h3 class="subh">项目列表（{{ orgProjects.length }}）</h3>
        <div v-if="!orgProjects.length" class="empty">暂无项目</div>
        <div v-else class="scroll tall">
          <table>
            <thead>
              <tr>
                <th>项目</th>
                <th>状态</th>
                <th>导师</th>
                <th>改派</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="p in orgProjects" :key="p.id">
                <td>
                  <RouterLink :to="`/projects/${p.id}`">{{ p.title }}</RouterLink>
                </td>
                <td>
                  <span class="badge" :class="statusTone(p.status)">{{
                    projectStatusLabel(p.status)
                  }}</span>
                </td>
                <td>{{ mentorName(p) }}</td>
                <td>
                  <select
                    :value="p.mentor_id"
                    :disabled="busy"
                    @change="onReassignChange(p.id, $event)"
                  >
                    <option v-for="m in mentors" :key="m.user_id" :value="m.user_id">
                      {{ m.display_name }}
                    </option>
                  </select>
                </td>
                <td>
                  <button
                    v-if="p.status === 'draft'"
                    class="btn sm secondary"
                    type="button"
                    @click="openPreview(p)"
                  >
                    预览调整
                  </button>
                  <button
                    v-else-if="p.status === 'published' || p.status === 'closed'"
                    class="btn sm secondary"
                    type="button"
                    :disabled="busy"
                    @click="askUnpublish(p)"
                  >
                    下架
                  </button>
                  <button
                    v-else-if="p.status === 'offline' && !projectFinished(p)"
                    class="btn sm secondary"
                    type="button"
                    @click="openPreview(p)"
                  >
                    修改
                  </button>
                  <button
                    v-if="p.status === 'offline'"
                    class="btn sm"
                    type="button"
                    :disabled="busy"
                    @click="publish(p.id)"
                  >
                    重新发布
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section v-else-if="tab === 'liaison'" class="panel liaison-panel">
        <CommunityDesk />
      </section>

      <section v-else-if="tab === 'rewards'" class="panel">
        <div class="panel-bar">
          <div>
            <h2>学生奖励申请</h2>
            <p class="bar-hint">验收通过后，学生把关闭证明和联系方式交给本社区。通过或驳回只在社区和学生之间。</p>
          </div>
        </div>
        <div class="reward-tools">
          <input
            v-model="rewardQuery"
            type="search"
            placeholder="搜学生、项目或说明"
            @keyup.enter="loadRewards"
          />
          <button class="btn sm" type="button" @click="loadRewards">搜索</button>
          <label>
            年份
            <select v-model="rewardYear" @change="loadRewards">
              <option value="all">全部年份</option>
              <option v-for="year in rewardYearChoices" :key="year" :value="String(year)">{{ year }}</option>
            </select>
          </label>
          <label>
            状态
            <select v-model="rewardStatus" @change="loadRewards">
              <option value="pending">待处理</option>
              <option value="approved">已通过</option>
              <option value="rejected">已驳回</option>
              <option value="all">全部</option>
            </select>
          </label>
        </div>
        <p v-if="!rewards.length" class="muted">这一栏没有奖励申请。</p>
        <ul v-else class="final-list">
          <li v-for="item in rewards" :key="item.application_id">
            <div>
              <strong>{{ item.student_name || '学生' }}</strong>
              <span>{{ item.project_title }} · {{ item.created_at || '' }}</span>
              <p class="reward-body">{{ item.body }}</p>
              <a v-if="item.attachment_url" :href="withFileAuth(item.attachment_url)" download>{{ item.attachment_name || '证明材料.zip' }}</a>
              <p v-if="item.decision === 'rejected' && item.decision_note" class="reward-note">驳回原因：{{ item.decision_note }}</p>
            </div>
            <div v-if="item.decision === 'pending' || !item.decision" class="reward-actions">
              <button class="btn sm pass" type="button" :disabled="busy" @click="decideReward(item.application_id, 'approved')">通过</button>
              <button class="btn sm danger" type="button" :disabled="busy" @click="rejectId = item.application_id">驳回</button>
              <label v-if="rejectId === item.application_id" class="reject-box">
                驳回原因
                <textarea v-model="rejectNote" rows="3" placeholder="写明要改什么" />
                <button class="btn sm danger" type="button" :disabled="busy" @click="decideReward(item.application_id, 'rejected')">确认驳回</button>
              </label>
            </div>
            <strong v-else class="reward-state">{{ item.decision === 'approved' ? '已通过' : '已驳回' }}</strong>
          </li>
        </ul>
      </section>

      <section v-else-if="tab === 'selection'" class="panel">
        <div class="panel-bar">
          <div>
            <h2>选拔审核</h2>
            <p class="bar-hint">导师通过设计并预留名额后，在这里审核。社区通过后，组委会会自动接收中选，不必再点一次。</p>
          </div>
        </div>
        <p v-if="!selectionQueue.length" class="muted">现在没有待社区审核的申请。</p>
        <ul v-else class="final-list">
          <li v-for="item in selectionQueue" :key="item.id">
            <div>
              <strong>{{ item.student_name || '学生' }}</strong>
              <span>{{ item.project_title || `申请 #${item.id}` }} · {{ statusLabel(item.status) }}</span>
            </div>
            <div class="row-acts">
              <button
                class="btn sm pass"
                type="button"
                :disabled="selectionBusy"
                @click="askSelection(item, 'approve')"
              >
                通过
              </button>
              <button
                class="btn sm danger"
                type="button"
                :disabled="selectionBusy"
                @click="askSelection(item, 'reject')"
              >
                退回
              </button>
            </div>
          </li>
        </ul>
      </section>

      <section v-else-if="tab === 'finals'" class="panel">
        <div class="panel-bar">
          <div>
            <h2>提交结项材料</h2>
            <p class="bar-hint">导师通过学生的结项验收后，点「去提交」。填说明和材料并确认后，组委会会自动接收并计入结项名单，不必再等组委会点一次通过。</p>
          </div>
        </div>
        <p v-if="!finalQueue.length" class="muted">现在没有待提交的结项，提交按钮不能点。学生验收经导师通过后可以提交。</p>
        <ul v-else class="final-list">
          <li v-for="item in finalQueue" :key="item.id">
            <div>
              <strong>{{ item.student_name || '学生' }}</strong>
              <span>{{ item.project_title || `申请 #${item.id}` }}</span>
            </div>
          </li>
        </ul>
        <CommunityFinalSubmitView embedded :application-id="finalQueue[0]?.id ?? null" />
      </section>
    </template>
  </div>
</template>

<style scoped>
.org-console {
  max-width: none;
  margin: 0 auto;
  padding: 0.85rem 1.75rem 1.75rem;
  width: 100%;
  box-sizing: border-box;
}
.scroll td .btn + .btn { margin-left: 6px; }
.head {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
  align-items: flex-end;
  margin-bottom: 1.25rem;
}
.head h1 {
  margin: 0;
  font-size: 1.45rem;
  color: #262626;
}
.sub {
  margin: 0.25rem 0 0;
  color: #8c8c8c;
  font-size: 0.86rem;
}
.head-actions {
  display: flex;
  gap: 1rem;
  align-items: center;
}
.link {
  color: #1677ff;
  font-weight: 600;
  font-size: 0.9rem;
  text-decoration: none;
}
.link.muted {
  color: #8c8c8c;
  font-weight: 500;
}
.tabs {
  display: flex;
  gap: 0;
  margin-bottom: 0;
  border-bottom: 1px solid #f0f0f0;
}
.tabs button {
  border: none;
  background: transparent;
  padding: 0.7rem 1.1rem;
  font-size: 0.92rem;
  color: #8c8c8c;
  cursor: pointer;
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;
}
.tabs button.on {
  color: #1677ff;
  font-weight: 700;
  border-bottom-color: #1677ff;
}
.tabs span {
  margin-left: 0.25rem;
  font-size: 0.78rem;
  color: #bfbfbf;
}
.panel {
  background: #fff;
  border: 1px solid #d9d9d9;
  border-top: none;
  border-radius: 0 0 10px 10px;
  padding: 1.25rem 1.35rem 1.5rem;
}
.liaison-panel {
  padding: 0.85rem 0.9rem 1rem;
  background: #f3f6fb;
}
.panel-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}
.panel-bar h2 {
  margin: 0;
}
.bar-hint {
  margin: 0.2rem 0 0;
  font-size: 0.82rem;
  color: #8c8c8c;
}
.final-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 10px; }
.final-list li { display: flex; justify-content: space-between; align-items: center; gap: 16px; border: 1px solid #e5e7eb; border-radius: 10px; padding: 14px 16px; background: #fff; }
.final-list strong, .final-list span { display: block; }
.final-list span { color: #8c8c8c; font-size: 0.86rem; margin-top: 2px; }
.row-acts { display: flex; gap: 8px; flex-shrink: 0; }
.dlg-note { display: grid; gap: 0.4rem; margin: 0 0 1rem; color: #334155; font-size: 0.92rem; }
.dlg-note textarea {
  width: 100%;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  padding: 0.55rem 0.7rem;
  font: inherit;
  resize: vertical;
}
.reward-body { white-space: pre-wrap; margin: 0.35rem 0; color: #334155; }
.reward-tools { display: flex; flex-wrap: wrap; gap: 8px; align-items: end; margin-bottom: 12px; }
.reward-tools input, .reward-tools select { border: 1px solid #d0d7e2; border-radius: 8px; padding: 6px 8px; font: inherit; }
.reward-tools label { display: flex; flex-direction: column; gap: 4px; font-size: 0.82rem; color: #475569; }
.reward-actions { display: flex; flex-direction: column; align-items: stretch; gap: 8px; min-width: 148px; }
.reward-actions .pass { background: #1677ff; }
.reward-actions .danger, .reject-box .danger { background: #dc2626; }
.reject-box { display: flex; flex-direction: column; gap: 6px; }
.reject-box textarea { width: 220px; border: 1px solid #d0d7e2; border-radius: 8px; padding: 6px 8px; font: inherit; }
.reward-state { color: #1e3a5f; white-space: nowrap; }
.reward-note { color: #b45309; margin: 0.35rem 0 0; }
.preview-jump {
  color: #1677ff;
  font-weight: 600;
  text-decoration: none;
  white-space: nowrap;
}
.publish-bar {
  display: flex;
  justify-content: center;
  margin-top: 1rem;
  padding-top: 1rem;
  border-top: 1px solid #e5e7eb;
}
.hint {
  margin: 0 0 0.85rem;
  color: #8c8c8c;
  font-size: 0.88rem;
}
.panel h2 {
  margin: 0 0 0.65rem;
  font-size: 1rem;
}
.split {
  display: grid;
  grid-template-columns: minmax(0, 1.08fr) minmax(0, 0.92fr);
  gap: 1.15rem;
  align-items: start;
}
.pane {
  border: 1px solid #f0f0f0;
  border-radius: 10px;
  background: #fafafa;
  padding: 0.75rem 0.85rem 0.9rem;
  min-height: 0;
}
.edit-pane {
  background: #fff;
}
.preview-pane {
  position: sticky;
  top: 64px;
  max-height: calc(100vh - 80px);
  overflow: auto;
  background: #f7f9fc;
}
.pane-title {
  margin: 0 0 0.5rem;
  font-size: 0.86rem;
  font-weight: 700;
  color: #262626;
}
.pane-hint {
  margin: 0 0 0.45rem;
  font-size: 0.78rem;
  color: #8c8c8c;
}
.block {
  margin-bottom: 0.7rem;
  padding-bottom: 0.65rem;
  border-bottom: 1px solid #f5f5f5;
}
.block:last-child {
  border-bottom: none;
  margin-bottom: 0;
  padding-bottom: 0;
}
.block h4 {
  margin: 0 0 0.4rem;
  font-size: 0.8rem;
  color: #8c8c8c;
  font-weight: 700;
}
.basic-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.4rem 0.6rem;
  align-items: start;
}
.basic-grid label {
  display: flex;
  flex-direction: column;
  gap: 0.18rem;
  font-size: 0.76rem;
  color: #8c8c8c;
  font-weight: 600;
}
.basic-grid input,
.basic-grid textarea {
  font-weight: 500;
  color: #262626;
  font-size: 0.86rem;
  padding: 0.38rem 0.5rem;
  border: 1px solid #f0f0f0;
  border-radius: 6px;
  font-family: inherit;
}
.basic-grid .span-2 {
  grid-column: 1 / -1;
}
.basic-grid .basic-logo {
  grid-column: 1 / -1;
}
.basic-grid :deep(.prev) {
  width: 52px;
  height: 52px;
  font-size: 0.7rem;
}
.basic-grid :deep(.hint) {
  display: none;
}
.basic-grid :deep(.lbl) {
  font-size: 0.76rem;
}
.create-block {
  border-bottom: none;
}
.live {
  background: #fff;
  border-radius: 10px;
  border: 1px solid #eef2f7;
  padding: 0.85rem 0.9rem 1rem;
}
.live-head {
  display: grid;
  grid-template-columns: 48px 1fr;
  gap: 0.65rem;
  margin-bottom: 0.5rem;
}
.live-logo {
  width: 48px;
  height: 48px;
  border-radius: 8px;
  border: 1px solid #f0f0f0;
  display: grid;
  place-items: center;
  overflow: hidden;
  font-size: 1.1rem;
  font-weight: 700;
  color: #1677ff;
  background: #fafafa;
}
.live-logo img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.live-head h4 {
  margin: 0 0 0.2rem;
  font-size: 1.05rem;
  color: #262626;
}
.live-link {
  color: #1677ff;
  font-size: 0.78rem;
  font-weight: 600;
  text-decoration: none;
}
.live-miss {
  margin: 0;
  color: #d9d9d9;
  font-size: 0.78rem;
}
.live-desc {
  margin: 0 0 0.45rem;
  color: #595959;
  font-size: 0.86rem;
  line-height: 1.55;
}
.live-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 0.3rem;
  margin-bottom: 0.6rem;
}
.live-tags span {
  padding: 2px 8px;
  border-radius: 4px;
  background: #e6f4ff;
  color: #1677ff;
  font-size: 0.72rem;
  font-weight: 600;
}
.live-intro {
  border-top: 1px solid #f5f5f5;
  padding-top: 0.65rem;
}
.form.stack {
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
  max-width: none;
}
@media (max-width: 1100px) {
  .org-console {
    padding: 0.85rem 1rem 1.5rem;
  }
}
@media (max-width: 960px) {
  .split {
    grid-template-columns: 1fr;
  }
  .preview-pane {
    position: static;
    max-height: none;
  }
  .basic-grid {
    grid-template-columns: 1fr;
  }
}
.invite {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  align-items: center;
  padding: 0.75rem 0.9rem;
  background: #fafafa;
  border-radius: 8px;
  border: 1px solid #f0f0f0;
  margin-bottom: 1.25rem;
}
.invite code {
  flex: 1;
  min-width: 8rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  color: #262626;
}
.subh {
  margin: 0 0 0.55rem;
  font-size: 0.92rem;
  color: #595959;
}
.scroll {
  max-height: 280px;
  overflow: auto;
  border: 1px solid #f0f0f0;
  border-radius: 8px;
}
.scroll.tall {
  max-height: 320px;
}
table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.88rem;
}
th,
td {
  padding: 0.55rem 0.7rem;
  text-align: left;
  border-bottom: 1px solid #f5f5f5;
}
th {
  position: sticky;
  top: 0;
  background: #fafafa;
  color: #8c8c8c;
  font-weight: 600;
  font-size: 0.78rem;
}
td a {
  color: #1677ff;
  font-weight: 600;
  text-decoration: none;
}
table select {
  max-width: 8.5rem;
  font-size: 0.82rem;
}
.project-card {
  border: 1px solid #e8e8e8;
  border-radius: 12px;
  padding: 16px 16px 4px;
  margin-bottom: 16px;
  background: #fff;
}
.project-card.edit {
  border-color: #d6e4ff;
  background: #f8fbff;
}
.card-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}
.project-card h2 { margin: 0 0 4px; font-size: 1.05rem; }
.form.proj label {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 0.82rem;
  color: #595959;
}
.form.proj input,
.form.proj select,
.form.proj textarea {
  width: 100%;
  box-sizing: border-box;
  max-width: none;
  border: 1px solid #d9d9d9;
  border-radius: 8px;
  padding: 8px 10px;
  font: inherit;
  color: #1f2937;
  background: #fff;
}
.form.proj .acts { display: flex; gap: 8px; align-items: center; }
.form.proj {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.65rem 0.85rem;
  margin-bottom: 1.25rem;
  padding-bottom: 1.1rem;
  border-bottom: 1px solid #f0f0f0;
}
.form.proj .full {
  grid-column: 1 / -1;
}
.empty {
  color: #bfbfbf;
  font-size: 0.9rem;
  padding: 0.5rem 0;
}
.row {
  display: flex;
  gap: 0.4rem;
}
@media (max-width: 640px) {
  .form.proj,
  .preview {
    grid-template-columns: 1fr;
  }
}
</style>
