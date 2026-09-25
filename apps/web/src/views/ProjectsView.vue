<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import api from '@/api/client'
import type { ApplicationOut, CommunityOut, ProjectOut } from '@/api/types'
import { useAuthStore } from '@/stores/auth'
import { nodeLabel, statusLabel, statusTone } from '@/utils/statusLabel'
import { difficultyLabel } from '@/utils/projectBrief'
import { clearTrail, seedTrail } from '@/utils/crumbTrail'
import { CS_DIRECTIONS, childrenOf, placeDirection } from '@/utils/csDirections'

type Mode = 'orgs' | 'tasks' | 'mine'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const mode = ref<Mode>('orgs')

function setMode(next: Mode) {
  mode.value = next
  router.replace({ query: { ...route.query, tab: next } })
  if (next === 'mine') void loadMine()
}

const communities = ref<CommunityOut[]>([])
const projects = ref<ProjectOut[]>([])
const myApps = ref<ApplicationOut[]>([])
const error = ref('')
const loading = ref(true)
const mineLoading = ref(false)
const mineError = ref('')
const mineLoaded = ref(false)

const orgQuery = ref('')
const taskQuery = ref('')
const mineQuery = ref('')
const difficulty = ref('all')
const dirParent = ref('all')
const dirChild = ref('all')
const pageSize = 8
const orgPage = ref(1)
const taskPage = ref(1)
const minePage = ref(1)

const tones = ['tone-a', 'tone-b', 'tone-c', 'tone-d', 'tone-e']
const brokenLogos = ref<Record<number, boolean>>({})

function markLogoBroken(id: number) {
  brokenLogos.value = { ...brokenLogos.value, [id]: true }
}

function showLogo(c: CommunityOut) {
  return Boolean(c.logo_url) && !brokenLogos.value[c.id]
}

/** 正在申请 / 开发中（不含已结项、已放弃） */
const ACTIVE_STATUSES = new Set([
  'draft',
  'submitted',
  'mentor_review',
  'rejected',
  'community_review',
  'committee_review',
  'selected',
  'in_progress',
  'final_submitted',
  'mentor_final_review',
  'committee_final_review',
  'final_rejected',
])

function toneOf(id: number) {
  return tones[id % tones.length]
}

function initialOf(name: string) {
  const s = (name || '?').trim()
  return s.slice(0, 1)
}

const filteredOrgs = computed(() => {
  const q = orgQuery.value.trim().toLowerCase()
  return communities.value.filter((c) => {
    // 隐藏自动化冒烟组织，避免冲淡演示案例
    if ((c.slug || '').startsWith('smoke-')) return false
    if (!q) return true
    const hay = `${c.name} ${c.description || ''} ${c.slug}`.toLowerCase()
    return hay.includes(q)
  })
})

const communityMap = computed(() => {
  const m = new Map<number, CommunityOut>()
  for (const c of communities.value) m.set(c.id, c)
  return m
})

function communityOf(id: number) {
  return communityMap.value.get(id)
}

function placedOf(p: ProjectOut) {
  return placeDirection(communityOf(p.community_id)?.slug, p.title)
}

function takenStudents(p: ProjectOut): string[] {
  return (p.assignees || [])
    .map((a) => (a.student_name || '').trim())
    .filter(Boolean)
}

const filteredTasks = computed(() => {
  const q = taskQuery.value.trim().toLowerCase()
  return projects.value.filter((p) => {
    if (difficulty.value !== 'all' && (p.difficulty || '') !== difficulty.value) return false
    const placed = placedOf(p)
    if (dirParent.value !== 'all' && placed.parentId !== dirParent.value) return false
    if (dirChild.value !== 'all' && placed.childId !== dirChild.value) return false
    if (!q) return true
    const org = communityMap.value.get(p.community_id)
    const hay = `${p.title} ${p.summary || ''} ${org?.name || ''} ${placed.parent} ${placed.child}`.toLowerCase()
    return hay.includes(q)
  })
})

function pageCount(total: number) {
  return Math.max(1, Math.ceil(total / pageSize))
}

function clampPage(page: number, total: number) {
  return Math.min(Math.max(1, page), pageCount(total))
}

const orgPageCount = computed(() => pageCount(filteredOrgs.value.length))
const taskPageCount = computed(() => pageCount(filteredTasks.value.length))
const minePageCount = computed(() => pageCount(myActiveApps.value.length))

const pagedOrgs = computed(() => {
  const page = clampPage(orgPage.value, filteredOrgs.value.length)
  const start = (page - 1) * pageSize
  return filteredOrgs.value.slice(start, start + pageSize)
})
const pagedTasks = computed(() => {
  const page = clampPage(taskPage.value, filteredTasks.value.length)
  const start = (page - 1) * pageSize
  return filteredTasks.value.slice(start, start + pageSize)
})
const pagedMine = computed(() => {
  const page = clampPage(minePage.value, myActiveApps.value.length)
  const start = (page - 1) * pageSize
  return myActiveApps.value.slice(start, start + pageSize)
})

const subDirections = computed(() => childrenOf(dirParent.value))

const difficultyOptions = [
  { id: 'all', label: '难度不限' },
  { id: 'easy', label: '基础' },
  { id: 'medium', label: '进阶' },
  { id: 'hard', label: '挑战' },
]

function setParent(id: string) {
  dirParent.value = id
  dirChild.value = 'all'
  taskPage.value = 1
}

function setChild(id: string) {
  dirChild.value = id
  taskPage.value = 1
}

const myActiveApps = computed(() => {
  const q = mineQuery.value.trim().toLowerCase()
  return myApps.value
    .filter((a) => ACTIVE_STATUSES.has(a.status))
    .filter((a) => {
      if (!q) return true
      const hay = `${a.project_title || ''} ${a.id} ${statusLabel(a.status)}`.toLowerCase()
      return hay.includes(q)
    })
    .sort((a, b) => b.id - a.id)
})

function phaseHint(status: string) {
  if (['draft', 'submitted', 'mentor_review', 'rejected'].includes(status)) return '申请审核中'
  if (['community_review', 'committee_review'].includes(status)) return '名额已预留'
  if (['selected', 'in_progress', 'final_rejected'].includes(status)) return '任务开发中'
  if (['final_submitted', 'mentor_final_review', 'committee_final_review'].includes(status))
    return '结项验收中'
  return ''
}

async function loadMine() {
  if (!auth.isLoggedIn) {
    myApps.value = []
    mineLoaded.value = true
    return
  }
  if (!auth.canApplyProjects) {
    myApps.value = []
    mineLoaded.value = true
    mineError.value = '组织侧账号请到工作台查看负责项目'
    return
  }
  mineLoading.value = true
  mineError.value = ''
  try {
    const { data } = await api.get<ApplicationOut[]>('/applications/mine')
    myApps.value = data
    mineLoaded.value = true
  } catch (e: unknown) {
    mineError.value = e instanceof Error ? e.message : '加载失败'
  } finally {
    mineLoading.value = false
  }
}

function goLogin() {
  router.push({ name: 'login', query: { redirect: '/projects?tab=mine', role: 'student' } })
}

onMounted(async () => {
  clearTrail()
  const tab = String(route.query.tab || '')
  if (tab === 'tasks' || tab === 'orgs' || tab === 'mine') mode.value = tab
  try {
    const [cRes, pRes] = await Promise.all([
      api.get<CommunityOut[]>('/communities', { params: { status: 'approved' } }),
      api.get<ProjectOut[]>('/projects', { params: { status: 'published' } }),
    ])
    communities.value = cRes.data
    projects.value = pRes.data
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : '加载失败'
  } finally {
    loading.value = false
  }
  if (mode.value === 'mine') await loadMine()
})

function seedFromBrowse(community?: CommunityOut | null) {
  if (community) {
    seedTrail([
      { label: '查看项目', to: '/projects' },
      { label: community.name, to: `/communities/${community.slug}` },
    ])
  } else {
    seedTrail([{ label: '查看项目', to: '/projects' }])
  }
}

function seedFromMine() {
  seedTrail([
    { label: '查看项目', to: '/projects' },
    { label: '我的项目', to: '/projects?tab=mine' },
  ])
}

watch([orgQuery, filteredOrgs], () => {
  if (orgPage.value > orgPageCount.value) orgPage.value = orgPageCount.value
})
watch([taskQuery, difficulty, dirParent, dirChild], () => {
  taskPage.value = 1
})
watch([mineQuery], () => {
  minePage.value = 1
})

watch(
  () => route.query.tab,
  (tab) => {
    if (tab === 'tasks' || tab === 'orgs' || tab === 'mine') {
      mode.value = tab
      if (tab === 'mine') void loadMine()
    }
  },
)
</script>

<template>
  <div class="browse-page">
    <header class="browse-hero">
      <h1>查看项目</h1>
      <p>先选社区了解方向，再领取该社区任务。</p>
    </header>

    <div class="browse-tabs" role="tablist">
      <button
        type="button"
        role="tab"
        class="browse-tab"
        :class="{ active: mode === 'orgs' }"
        :aria-selected="mode === 'orgs'"
        @click="setMode('orgs')"
      >
        社区列表
      </button>
      <button
        type="button"
        role="tab"
        class="browse-tab"
        :class="{ active: mode === 'tasks' }"
        :aria-selected="mode === 'tasks'"
        @click="setMode('tasks')"
      >
        全部任务
      </button>
      <button
        type="button"
        role="tab"
        class="browse-tab"
        :class="{ active: mode === 'mine' }"
        :aria-selected="mode === 'mine'"
        @click="setMode('mine')"
      >
        我的项目
      </button>
    </div>

    <p v-if="loading" class="muted browse-status">加载中…</p>
    <p v-else-if="error" class="error browse-status">{{ error }}</p>

    <template v-else-if="mode === 'orgs'">
      <div class="browse-toolbar">
        <div class="browse-search">
          <input v-model="orgQuery" type="search" placeholder="请输入组织名称" />
          <button class="btn sm" type="button">查找组织</button>
        </div>
        <div class="browse-meta">
          <span>共 {{ filteredOrgs.length }} 个组织</span>
          <span class="muted">*按通过审核顺序排序</span>
        </div>
      </div>

      <div v-if="!filteredOrgs.length" class="card muted">暂无匹配的组织。</div>
      <div v-else class="org-grid">
        <RouterLink
          v-for="c in pagedOrgs"
          :key="c.id"
          class="org-card"
          :to="`/communities/${c.slug}`"
          @click="seedFromBrowse()"
        >
          <div class="org-logo" :class="toneOf(c.id)">
            <img
              v-if="showLogo(c)"
              :src="c.logo_url!"
              :alt="c.name"
              @error="markLogoBroken(c.id)"
            />
            <span v-else>{{ initialOf(c.name) }}</span>
          </div>
          <div class="org-body">
            <h3>{{ c.name }}</h3>
            <p>{{ c.description || '暂无简介，进入后可查看任务详情。' }}</p>
            <div class="org-tags">
              <span class="org-tag">{{ placeDirection(c.slug).parent }}</span>
              <span class="org-tag">{{ placeDirection(c.slug).child }}</span>
            </div>
          </div>
        </RouterLink>
      </div>
      <div v-if="filteredOrgs.length > pageSize" class="pager">
        <button type="button" :disabled="orgPage <= 1" @click="orgPage -= 1">上一页</button>
        <span>{{ clampPage(orgPage, filteredOrgs.length) }} / {{ orgPageCount }}</span>
        <button type="button" :disabled="orgPage >= orgPageCount" @click="orgPage += 1">下一页</button>
      </div>
    </template>

    <template v-else-if="mode === 'tasks'">
      <div class="browse-toolbar">
        <div class="browse-search">
          <input v-model="taskQuery" type="search" placeholder="搜索任务 / 社区名称" />
          <button class="btn sm" type="button">搜索任务</button>
        </div>
        <div class="browse-filters dir-filters">
          <button
            type="button"
            class="chip"
            :class="{ on: dirParent === 'all' }"
            @click="setParent('all')"
          >
            全部方向
          </button>
          <button
            v-for="d in CS_DIRECTIONS"
            :key="d.id"
            type="button"
            class="chip"
            :class="{ on: dirParent === d.id }"
            @click="setParent(d.id)"
          >
            {{ d.label }}
          </button>
        </div>
        <div v-if="dirParent !== 'all'" class="browse-filters dir-filters sub">
          <button
            type="button"
            class="chip"
            :class="{ on: dirChild === 'all' }"
            @click="setChild('all')"
          >
            该方向全部
          </button>
          <button
            v-for="c in subDirections"
            :key="c.id"
            type="button"
            class="chip"
            :class="{ on: dirChild === c.id }"
            @click="setChild(c.id)"
          >
            {{ c.label }}
          </button>
        </div>
        <div class="browse-filters">
          <button
            v-for="d in difficultyOptions"
            :key="d.id"
            type="button"
            class="chip"
            :class="{ on: difficulty === d.id }"
            @click="difficulty = d.id"
          >
            {{ d.label }}
          </button>
        </div>
        <div class="browse-meta">
          <span>共 {{ filteredTasks.length }} 个任务</span>
          <span class="muted">按计算机方向筛选；中选同学直接列在项目里</span>
        </div>
      </div>

      <div v-if="!filteredTasks.length" class="card muted">暂无已发布任务。</div>
      <div v-else class="task-scroll">
        <table class="task-table">
          <thead>
            <tr>
              <th>项目</th>
              <th>方向</th>
              <th>社区</th>
              <th>难度</th>
              <th>中选学生</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="p in pagedTasks" :key="p.id">
              <td class="col-title">
                <RouterLink
                  :to="`/projects/${p.id}`"
                  @click="seedFromBrowse(communityOf(p.community_id))"
                  >{{ p.title }}</RouterLink
                >
                <p>{{ p.summary || '暂无摘要' }}</p>
              </td>
              <td>
                <span class="dir-main">{{ placedOf(p).parent }}</span>
                <span class="dir-sub">{{ placedOf(p).child }}</span>
              </td>
              <td>
                <RouterLink
                  v-if="communityOf(p.community_id)"
                  class="task-org"
                  :to="`/communities/${communityOf(p.community_id)?.slug}`"
                  @click="seedFromBrowse()"
                >
                  {{ communityOf(p.community_id)?.name }}
                </RouterLink>
              </td>
              <td>{{ difficultyLabel(p.difficulty) }}</td>
              <td class="col-people">
                <template v-if="takenStudents(p).length">
                  <span v-for="name in takenStudents(p)" :key="name" class="person">{{ name }}</span>
                  <small>{{ p.seats_taken || takenStudents(p).length }}/{{ p.quota }}</small>
                </template>
                <span v-else class="muted">待遴选 · 名额 {{ p.quota }}</span>
              </td>
              <td>
                <RouterLink
                  class="btn sm"
                  :to="`/projects/${p.id}`"
                  @click="seedFromBrowse(communityOf(p.community_id))"
                  >查看</RouterLink
                >
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-if="filteredTasks.length > pageSize" class="pager">
        <button type="button" :disabled="taskPage <= 1" @click="taskPage -= 1">上一页</button>
        <span>{{ clampPage(taskPage, filteredTasks.length) }} / {{ taskPageCount }}</span>
        <button type="button" :disabled="taskPage >= taskPageCount" @click="taskPage += 1">下一页</button>
      </div>
    </template>

    <template v-else>
      <div class="browse-toolbar">
        <div class="browse-search">
          <input v-model="mineQuery" type="search" placeholder="搜索我的项目名称 / 状态" />
          <button class="btn sm" type="button">搜索</button>
        </div>
        <div class="browse-meta">
          <span>共 {{ myActiveApps.length }} 个进行中</span>
          <span class="muted">申请审核与开发中的项目</span>
        </div>
      </div>

      <div v-if="!auth.isLoggedIn" class="card mine-empty">
        <p>登录后可查看正在申请或开发中的项目。</p>
        <button class="btn sm" type="button" @click="goLogin">去登录</button>
      </div>
      <p v-else-if="mineLoading" class="muted browse-status">加载中…</p>
      <p v-else-if="mineError" class="error browse-status">{{ mineError }}</p>
      <div v-else-if="!myActiveApps.length" class="card mine-empty">
        <p>暂无进行中的项目。</p>
        <button class="btn sm" type="button" @click="setMode('tasks')">去领取任务</button>
      </div>
      <div v-else class="mine-list">
        <article v-for="a in pagedMine" :key="a.id" class="mine-card">
          <div class="mine-main">
            <h3>
              <RouterLink
                :to="`/student/applications/${a.id}?tab=task`"
                @click="seedFromMine"
                >{{ a.project_title || `项目 #${a.project_id}` }}</RouterLink
              >
            </h3>
            <p class="mine-meta">
              申请 #{{ a.id }}
              <template v-if="phaseHint(a.status)"> · {{ phaseHint(a.status) }}</template>
              <template v-if="nodeLabel(a.current_node)">
                · {{ nodeLabel(a.current_node) }}
              </template>
            </p>
          </div>
          <span class="badge" :class="statusTone(a.status)">{{ statusLabel(a.status) }}</span>
          <div class="mine-actions">
            <RouterLink
              class="btn sm"
              :to="`/student/applications/${a.id}?tab=task`"
              @click="seedFromMine"
            >
              进入我的项目
            </RouterLink>
            <RouterLink
              class="btn sm secondary"
              :to="`/projects/${a.project_id}`"
              @click="seedFromMine"
            >
              任务介绍
            </RouterLink>
          </div>
        </article>
      </div>
      <div v-if="myActiveApps.length > pageSize" class="pager">
        <button type="button" :disabled="minePage <= 1" @click="minePage -= 1">上一页</button>
        <span>{{ clampPage(minePage, myActiveApps.length) }} / {{ minePageCount }}</span>
        <button type="button" :disabled="minePage >= minePageCount" @click="minePage += 1">下一页</button>
      </div>
    </template>
  </div>
</template>

<style scoped>
.mine-empty {
  text-align: center;
  padding: 2rem 1.25rem;
  display: grid;
  gap: 0.85rem;
  justify-items: center;
}
.mine-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}
.mine-card {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 0.55rem 1rem;
  align-items: center;
  padding: 1rem 1.15rem;
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
}
.mine-main {
  min-width: 0;
}
.mine-main h3 {
  margin: 0 0 0.25rem;
  font-size: 1.05rem;
}
.mine-main h3 a {
  color: inherit;
  text-decoration: none;
}
.mine-main h3 a:hover {
  color: #2563eb;
}
.mine-meta {
  margin: 0;
  font-size: 0.85rem;
  color: #6b7280;
}
.mine-actions {
  grid-column: 1 / -1;
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
}
.dir-filters {
  flex-wrap: wrap;
}
.task-scroll {
  max-height: min(68vh, 720px);
  overflow: auto;
  border: 1px solid #eee;
  border-radius: 10px;
  background: #fff;
}
.task-table {
  width: 100%;
  border-collapse: collapse;
  min-width: 860px;
}
.task-table th {
  position: sticky;
  top: 0;
  z-index: 1;
  background: #fafafa;
  text-align: left;
  font-size: 0.8rem;
  color: #8c8c8c;
  font-weight: 650;
  padding: 0.7rem 0.9rem;
  border-bottom: 1px solid #f0f0f0;
}
.task-table td {
  padding: 0.85rem 0.9rem;
  border-bottom: 1px solid #f5f5f5;
  vertical-align: top;
  font-size: 0.9rem;
}
.col-title a {
  color: #1a1a1a;
  font-weight: 700;
  text-decoration: none;
}
.col-title a:hover {
  color: #1677ff;
}
.col-title p {
  margin: 0.25rem 0 0;
  color: #8c8c8c;
  font-size: 0.8rem;
  line-height: 1.45;
}
.dir-main {
  display: block;
  color: #262626;
}
.dir-sub {
  display: block;
  margin-top: 0.15rem;
  color: #1677ff;
  font-size: 0.78rem;
}
.col-people .person {
  display: inline-block;
  margin: 0 0.35rem 0.2rem 0;
  padding: 0.05rem 0.4rem;
  border-radius: 999px;
  background: #f0f7ff;
  color: #0b3d91;
  font-size: 0.8rem;
}
.col-people small {
  display: block;
  margin-top: 0.2rem;
  color: #8c8c8c;
}
.pager {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 0.6rem;
  margin-top: 0.85rem;
  color: #595959;
  font-size: 0.86rem;
}
.pager button {
  border: 1px solid #d9d9d9;
  background: #fff;
  border-radius: 6px;
  padding: 0.28rem 0.7rem;
  font: inherit;
  cursor: pointer;
}
.pager button:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}
@media (min-width: 720px) {
  .mine-card {
    grid-template-columns: 1fr auto auto;
  }
  .mine-actions {
    grid-column: auto;
  }
}
</style>
