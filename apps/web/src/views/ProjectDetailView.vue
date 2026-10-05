<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, RouterLink, useRouter } from 'vue-router'
import api from '@/api/client'
import type { ApplicationOut, CommunityOut, ProjectOut } from '@/api/types'
import ToastFeedback from '@/components/ToastFeedback.vue'
import PdfPreviewModal from '@/components/PdfPreviewModal.vue'
import PageCrumb from '@/components/PageCrumb.vue'
import { useAuthStore } from '@/stores/auth'
import {
  difficultyLabel,
  langLabel,
  parseBrief,
  parseStack,
  projectCode,
} from '@/utils/projectBrief'
import { resolveCrumbs, seedTrail, getStoredTrail } from '@/utils/crumbTrail'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const project = ref<ProjectOut | null>(null)
const community = ref<CommunityOut | null>(null)
const myApp = ref<ApplicationOut | null>(null)
const activeTask = ref<ApplicationOut | null>(null)
const OPEN_TASK = [
  'submitted',
  'mentor_review',
  'community_review',
  'committee_review',
  'selected',
  'in_progress',
  'final_submitted',
  'mentor_final_review',
  'final_rejected',
]
const error = ref('')
const showTop = ref(false)
const toast = ref<InstanceType<typeof ToastFeedback> | null>(null)

const previewOpen = ref(false)
const previewUrl = ref('')
const previewTitle = ref('')

const brief = computed(() =>
  parseBrief(project.value?.description, project.value?.summary),
)

const langTags = computed(() => {
  if (brief.value.languages?.length) return brief.value.languages
  return parseStack(project.value?.tech_stack)
})

const domainTags = computed(() => brief.value.domains || [])

const heat = computed(() => brief.value.heat ?? 3)
const canApply = computed(() => auth.canApplyProjects)
const canReapply = computed(
  () =>
    !!myApp.value &&
    ['rejected', 'withdrawn', 'draft'].includes(myApp.value.status),
)
const isOwnMentorProject = computed(
  () =>
    !!project.value &&
    auth.isLoggedIn &&
    auth.isMentor &&
    project.value.mentor_id === auth.user?.id,
)
const assignees = computed(() => project.value?.assignees || [])
/** 公示中选：导师已通过后占名额的学生（不含审核中他人） */
const selectedStudents = computed(() => assignees.value)
const seatsTaken = computed(() => project.value?.seats_taken ?? assignees.value.length)
const seatsAvail = computed(() => {
  if (project.value?.seats_available != null) return project.value.seats_available
  return Math.max(0, (project.value?.quota || 0) - seatsTaken.value)
})
const seatsFull = computed(() => seatsAvail.value <= 0)
const canOpenApply = computed(
  () =>
    project.value?.status === 'published' &&
    (!myApp.value || canReapply.value) &&
    !seatsFull.value &&
    !activeTask.value,
)
const iAmSelected = computed(
  () =>
    !!myApp.value &&
    selectedStudents.value.some((a) => a.application_id === myApp.value!.id),
)

const crumbs = computed(() => {
  const id = String(route.params.id)
  const stored = getStoredTrail()
  // 等社区信息或已有路径后再固化，避免先写成「查看项目 › 任务介绍」丢社区级
  if (!community.value && stored.length === 0) {
    return [{ label: '任务介绍' }]
  }
  const fallback = community.value
    ? [
        { label: '查看项目', to: '/projects' },
        {
          label: community.value.name,
          to: `/communities/${community.value.slug}`,
        },
      ]
    : [{ label: '查看项目', to: '/projects' }]
  return resolveCrumbs({ label: '任务介绍', to: `/projects/${id}` }, fallback)
})

function seedMyProjectTrail() {
  const id = String(route.params.id)
  seedTrail([
    ...(community.value
      ? [
          {
            label: community.value.name,
            to: `/communities/${community.value.slug}`,
          },
        ]
      : [{ label: '查看项目', to: '/projects' }]),
    { label: '任务介绍', to: `/projects/${id}` },
  ])
}

/** 我的项目设计 PDF（申请书） */
const myDesignPdf = computed(() => {
  const a = myApp.value
  if (!a) return ''
  if (a.design_pdf) return a.design_pdf
  const raw = a.extra_fields
  if (!raw) return ''
  try {
    const obj = typeof raw === 'string' ? JSON.parse(raw) : raw
    return obj?.design_pdf ? String(obj.design_pdf) : ''
  } catch {
    return ''
  }
})

function openDesignPdf() {
  if (!myDesignPdf.value) {
    toast.value?.show('暂未找到已提交的设计方案 PDF', 'err')
    return
  }
  previewUrl.value = myDesignPdf.value
  previewTitle.value = '项目申请书 · 设计方案'
  previewOpen.value = true
}

function fileLabel(url: string) {
  try {
    return decodeURIComponent(url.split('/').pop() || '设计方案.pdf').replace(/^[a-f0-9]+_/i, '')
  } catch {
    return '设计方案.pdf'
  }
}

async function load() {
  error.value = ''
  community.value = null
  myApp.value = null
  activeTask.value = null
  const id = route.params.id
  try {
    const { data } = await api.get<ProjectOut>(`/projects/${id}`)
    project.value = data
    const { data: orgs } = await api.get<CommunityOut[]>('/communities', {
      params: { status: 'approved' },
    })
    community.value = orgs.find((c) => c.id === data.community_id) || null
    // 仅学生端加载「我的申请」；组织侧不混用申请能力
    if (auth.isLoggedIn && auth.canApplyProjects) {
      try {
        const { data: mine } = await api.get<ApplicationOut | null>(`/projects/${id}/my-application`)
        myApp.value = mine
      } catch {
        myApp.value = null
      }
      try {
        const { data: allMine } = await api.get<ApplicationOut[]>('/applications/mine')
        const currentId = Number(id)
        activeTask.value =
          allMine.find(
            (item) => item.project_id !== currentId && OPEN_TASK.includes(item.status),
          ) || null
      } catch {
        activeTask.value = null
      }
    }
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : '加载失败'
  }
}

function applyPath() {
  return `/projects/${route.params.id}/apply`
}

function openApply() {
  if (auth.isLoggedIn && !auth.canApplyProjects) {
    toast.value?.show('组织侧账号不能申请项目，请使用学生账号', 'err')
    return
  }
  if (!auth.isLoggedIn) {
    router.push({ name: 'login', query: { redirect: applyPath(), role: 'student' } })
    return
  }
  if (activeTask.value) {
    toast.value?.show(`你正在进行「${activeTask.value.project_title || '另一个任务'}」，结束前不能再接取`, 'err')
    return
  }
  if (seatsFull.value) {
    toast.value?.show('人选已满，不能再提交设计文档', 'err')
    return
  }
  if (myApp.value && !canReapply.value) {
    toast.value?.show('你已申请过该项目，可在申请详情查看进度', 'err')
    seedMyProjectTrail()
    router.push(`/student/applications/${myApp.value.id}?tab=task`)
    return
  }
  router.push(applyPath())
}

async function shareProject() {
  const url = window.location.href
  try {
    if (navigator.share) {
      await navigator.share({ title: project.value?.title || '开源实习任务', url })
      return
    }
  } catch {
    /* ignore */
  }
  try {
    await navigator.clipboard.writeText(url)
    window.alert('任务链接已复制')
  } catch {
    window.prompt('复制任务链接：', url)
  }
}

function onScroll() {
  showTop.value = window.scrollY > 420
}

function toTop() {
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

onMounted(() => {
  window.addEventListener('scroll', onScroll, { passive: true })
  load()
})
onUnmounted(() => window.removeEventListener('scroll', onScroll))
watch(() => route.params.id, load)
</script>

<template>
  <div class="ospp-page">
    <ToastFeedback ref="toast" />
    <PdfPreviewModal
      v-model:open="previewOpen"
      :url="previewUrl"
      :title="previewTitle || fileLabel(previewUrl)"
    />
    <div class="ospp-wrap">
      <PageCrumb :items="crumbs" />

      <p v-if="error" class="error">{{ error }}</p>
      <p v-else-if="!project" class="muted" style="text-align: center; padding: 4rem 0">加载中…</p>

      <template v-else>
        <!-- 头部：编号 + 标题（居中，对标 OSPP） -->
        <p class="ospp-id">项目编号：{{ projectCode(project.id) }}</p>
        <h1 class="ospp-title">{{ project.title }}</h1>

        <!-- 信息条：上值下标 -->
        <div class="ospp-info">
          <div class="ospp-info-cell">
            <div class="ospp-info-val">{{ difficultyLabel(project.difficulty) }}</div>
            <div class="ospp-info-lab">项目难度</div>
          </div>
          <div class="ospp-info-cell">
            <div class="ospp-info-val">{{ langLabel(brief.lang) }}</div>
            <div class="ospp-info-lab">支持语言</div>
          </div>
          <div class="ospp-info-cell">
            <div class="ospp-info-val ospp-heat" :title="`热度 ${heat}`">
              <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true">
                <path
                  fill="#ff7a45"
                  d="M12 23c-4.2 0-7-2.9-7-6.8 0-2.6 1.4-4.7 2.7-6.3.4-.5 1.3.1 1.1.7-.3 1.2-.2 2.1.4 2.1 1.1 0 1.7-2.8 1.7-4.4 0-2.8 1.7-5.3 3.7-7.1.5-.4 1.2.1 1 .7C14.8 5.5 15 9 17.2 11c1.6 1.5 2.8 3.4 2.8 5.2C20 20.1 17.1 23 12 23z"
                />
              </svg>
            </div>
            <div class="ospp-info-lab">项目热度</div>
          </div>
          <div class="ospp-info-cell">
            <div class="ospp-info-val">{{ project.mentor_name || brief.mentor_name || '社区导师' }}</div>
            <div class="ospp-info-lab">导师</div>
          </div>
          <div class="ospp-info-cell">
            <div class="ospp-info-val ospp-mail">
              <a v-if="project.mentor_email || brief.mentor_email" :href="`mailto:${project.mentor_email || brief.mentor_email}`">{{ project.mentor_email || brief.mentor_email }}</a>
              <span v-else>—</span>
            </div>
            <div class="ospp-info-lab">导师联系邮箱</div>
          </div>
        </div>

        <!-- 中选公示：居中，对标开源之夏；申请书直接预览设计 PDF -->
        <div v-if="selectedStudents.length" class="ospp-selected">
          <div class="ospp-selected-inner">
            <span class="ospp-selected-lab">中选学生：</span>
            <span class="ospp-selected-name">{{
              selectedStudents
                .map((a) => a.student_name || `学生 #${a.student_id}`)
                .join('、')
            }}</span>
            <button
              v-if="iAmSelected && myDesignPdf"
              type="button"
              class="ospp-selected-link"
              @click="openDesignPdf"
            >
              项目申请书 ›
            </button>
            <RouterLink
              v-else-if="iAmSelected && myApp"
              class="ospp-selected-link"
              :to="`/student/applications/${myApp.id}?tab=task`"
              @click="seedMyProjectTrail"
            >
              进入我的项目 ›
            </RouterLink>
          </div>
        </div>
        <div v-else-if="!seatsFull" class="ospp-selected empty">
          <div class="ospp-selected-inner">
            <span class="ospp-selected-lab">中选学生：</span>
            <span class="ospp-selected-pending">待遴选</span>
          </div>
        </div>

        <!-- 标签行 -->
        <div class="ospp-rows">
          <div v-if="domainTags.length" class="ospp-row">
            <span class="ospp-dot" aria-hidden="true">
              <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M12 3l7 4v5c0 4-3 7-7 9-4-2-7-5-7-9V7l7-4z" />
              </svg>
            </span>
            <span class="ospp-lab">技术领域</span>
            <div class="ospp-tags">
              <span v-for="t in domainTags" :key="t" class="ospp-tag">{{ t }}</span>
            </div>
          </div>
          <div class="ospp-row">
            <span class="ospp-dot" aria-hidden="true">
              <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M8 7l-4 5 4 5M16 7l4 5-4 5" />
              </svg>
            </span>
            <span class="ospp-lab">编程语言</span>
            <div class="ospp-tags">
              <span v-for="t in langTags" :key="t" class="ospp-tag">{{ t }}</span>
              <span v-if="!langTags.length" class="ospp-muted">未标注</span>
            </div>
          </div>
          <div class="ospp-row">
            <span class="ospp-dot" aria-hidden="true">
              <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M7 4h7l3 3v13H7V4z" />
                <path d="M14 4v3h3" />
              </svg>
            </span>
            <span class="ospp-lab">开源协议</span>
            <div class="ospp-tags">
              <span class="ospp-text">{{ brief.license || 'Apache-2.0' }} license</span>
            </div>
          </div>
          <div v-if="community" class="ospp-row">
            <span class="ospp-dot" aria-hidden="true">
              <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="8" />
                <path d="M12 8v8M8 12h8" />
              </svg>
            </span>
            <span class="ospp-lab">所属社区</span>
            <div class="ospp-tags">
              <RouterLink class="ospp-tag" :to="`/communities/${community.slug}`">{{ community.name }}</RouterLink>
            </div>
          </div>
        </div>

        <!-- 项目简述 -->
        <section class="ospp-brief">
          <h2 class="ospp-brief-title">
            <span class="ospp-dot lg" aria-hidden="true">
              <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M6 4h9l3 3v13H6V4z" />
                <path d="M9 11h6M9 15h4" />
              </svg>
            </span>
            项目简述
          </h2>
          <p v-if="project.summary" class="ospp-summary">{{ project.summary }}</p>
          <div
            v-for="(sec, idx) in brief.sections || []"
            :key="sec.title"
            class="ospp-sec"
          >
            <h3>（{{ idx + 1 }}）{{ sec.title }}</h3>
            <p v-if="sec.body">{{ sec.body }}</p>
            <ul v-if="sec.items?.length">
              <li v-for="(it, i) in sec.items" :key="i">{{ it }}</li>
            </ul>
          </div>
        </section>

        <!-- 产出 / 技术要求 -->
        <div class="ospp-cards">
          <div class="ospp-card">
            <h3>项目产出要求</h3>
            <ul>
              <li v-for="(it, i) in brief.outputs || []" :key="i">{{ it }}</li>
            </ul>
          </div>
          <div class="ospp-card">
            <h3>项目技术要求</h3>
            <ul>
              <li v-for="(it, i) in brief.tech_requirements || []" :key="i">{{ it }}</li>
            </ul>
          </div>
        </div>

        <!-- 仓库 / 周期 -->
        <div class="ospp-cards">
          <div class="ospp-card">
            <h3>项目成果仓库</h3>
            <ul>
              <li v-if="project.repo_url">
                <a :href="project.repo_url" target="_blank" rel="noopener">{{ project.repo_url }}</a>
              </li>
              <li v-else>暂未填写仓库地址</li>
            </ul>
          </div>
          <div class="ospp-card">
            <h3>开发周期 & 支持架构</h3>
            <ul>
              <li><strong>开发周期：</strong>{{ brief.cycle || '约 2–3 个月' }}</li>
              <li><strong>支持架构：</strong>{{ brief.arch || '不限' }}</li>
              <li><strong>名额：</strong>{{ project.quota }}</li>
            </ul>
          </div>
        </div>

        <!-- 底部操作：学生可申请；导师/组织侧不展示申请 -->
        <div class="ospp-btns">
          <template v-if="canApply">
            <template v-if="myApp && !canReapply">
              <RouterLink
                class="ospp-btn"
                :to="`/student/applications/${myApp.id}?tab=task`"
                @click="seedMyProjectTrail"
              >
                查看任务进度
              </RouterLink>
              <button
                v-if="myDesignPdf"
                class="ospp-btn ghost"
                type="button"
                @click="openDesignPdf"
              >
                查看申请书
              </button>
            </template>
            <button
              v-else-if="canOpenApply"
              class="ospp-btn"
              type="button"
              @click="openApply"
            >
              {{ canReapply ? '再次申请' : '申请接取' }}
            </button>
            <button
              v-else-if="activeTask"
              class="ospp-btn"
              type="button"
              disabled
              :title="`正在进行「${activeTask.project_title || '另一个任务'}」，结束前不能再接`"
            >
              手头任务未结束
            </button>
            <template v-else-if="myApp">
              <RouterLink
                class="ospp-btn"
                :to="`/student/applications/${myApp.id}?tab=task`"
                @click="seedMyProjectTrail"
              >
                进入我的项目
              </RouterLink>
              <button
                v-if="myDesignPdf"
                class="ospp-btn ghost"
                type="button"
                @click="openDesignPdf"
              >
                查看申请书
              </button>
            </template>
            <button
              v-else
              class="ospp-btn"
              type="button"
              disabled
              title="项目已被申请 / 名额已满"
            >
              项目已被申请
            </button>
          </template>
          <template v-else-if="auth.isStaff">
            <RouterLink v-if="auth.isMentor" class="ospp-btn" to="/mentor">导师工作台</RouterLink>
            <RouterLink
              v-if="isOwnMentorProject"
              class="ospp-btn ghost"
              to="/mentor/projects"
            >我负责的项目</RouterLink>
            <RouterLink
              v-if="auth.isCommunityAdmin"
              class="ospp-btn ghost"
              to="/org"
            >组织工作台</RouterLink>
            <span class="ospp-staff-hint">当前为组织侧账号，不可申请项目</span>
          </template>
          <template v-else>
            <button class="ospp-btn" type="button" @click="openApply">申请接取</button>
          </template>
          <button class="ospp-btn" type="button" @click="shareProject">项目分享</button>
        </div>
      </template>
    </div>

    <div class="ospp-fabs">
      <button class="ospp-fab" type="button" title="分享" @click="shareProject">
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="18" cy="5" r="2.2" />
          <circle cx="6" cy="12" r="2.2" />
          <circle cx="18" cy="19" r="2.2" />
          <path d="M8 11l8-5M8 13l8 5" />
        </svg>
      </button>
      <button v-show="showTop" class="ospp-fab" type="button" title="回到顶部" @click="toTop">
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M6 14l6-6 6 6" />
        </svg>
      </button>
    </div>
  </div>
</template>

<style scoped>
/* 开源之夏式中选公示条：内容居中 */
.ospp-selected {
  margin: 0.85rem 0 1.25rem;
  padding: 0.85rem 1.15rem;
  background: #f5f6f8;
  border-radius: 2px;
  text-align: center;
}
.ospp-selected-inner {
  display: inline-flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: center;
  gap: 0.35rem 0.75rem;
  font-size: 0.95rem;
  color: #1f2937;
}
.ospp-selected-lab {
  color: #4b5563;
}
.ospp-selected-name {
  font-weight: 700;
  color: #111827;
}
.ospp-selected-pending {
  color: #9ca3af;
}
.ospp-selected-link {
  border: none;
  background: none;
  padding: 0;
  color: #2563eb;
  font: inherit;
  font-weight: 600;
  text-decoration: none;
  cursor: pointer;
  white-space: nowrap;
}
.ospp-selected-link:hover {
  text-decoration: underline;
}
</style>
