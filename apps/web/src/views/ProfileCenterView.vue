<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import api from '@/api/client'
import type { ApplicationOut, CommunityMemberOut, CommunityOut, ProjectOut, UserOut } from '@/api/types'
import ToastFeedback from '@/components/ToastFeedback.vue'
import { useAuthStore } from '@/stores/auth'
import { BIND_PROVIDERS, type BindField } from '@/utils/bindProviders'
import { projectStatusLabel, stageLabel, statusLabel, statusTone } from '@/utils/statusLabel'

type Tab = 'home' | 'notices' | 'profile' | 'applications' | 'bindings' | 'password'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

const tab = computed<Tab>(() => {
  const t = String(route.query.tab || 'home')
  const orgOnlyNow = auth.isCommunityAdmin && !auth.isMentor && !auth.canApplyProjects
  if (orgOnlyNow) return 'home'
  if (!auth.canApplyProjects && (t === 'applications' || t === 'bindings')) return 'home'
  if (['notices', 'profile', 'applications', 'bindings', 'password', 'home'].includes(t)) {
    return t as Tab
  }
  return 'home'
})

watch(
  () => [route.query.tab, auth.canApplyProjects] as const,
  ([t, can]) => {
    if (t === 'applications' && !can) {
      router.replace({ path: '/me', query: { tab: 'home' } })
    }
  },
)

const saving = ref(false)
const msg = ref('')
const err = ref('')
const toast = ref<InstanceType<typeof ToastFeedback> | null>(null)

const form = ref({
  display_name: '',
  school: '',
  member_no: '',
  bio: '',
  phone: '',
  major: '',
  grade: '',
  degree: '',
  city: '',
  homepage_url: '',
  contact_email: '',
})

const apps = ref<ApplicationOut[]>([])
const appsLoading = ref(false)
const appsError = ref('')

const notices = ref<{ id: number; title: string; published_at?: string | null }[]>([])
const noticesLoading = ref(false)

const bindMsg = ref('')
const bindErr = ref('')

const pwd = ref({ old_password: '', new_password: '', confirm: '' })
const pwdLevel = computed(() => {
  const s = pwd.value.new_password
  if (!s) return 0
  let n = 1
  if (s.length >= 8) n += 1
  if (/[A-Za-z]/.test(s) && /\d/.test(s)) n += 1
  return Math.min(3, n)
})
const pwdHint = computed(() => {
  if (!pwd.value.new_password) return '未输入'
  return ['偏弱', '一般', '较好'][pwdLevel.value - 1] || '偏弱'
})
const mentorOnly = computed(() => auth.isMentor && !auth.canApplyProjects)
const orgOnly = computed(() => auth.isCommunityAdmin && !auth.isMentor && !auth.canApplyProjects)
const orgCommunity = ref<CommunityOut | null>(null)
const orgMentors = ref<CommunityMemberOut[]>([])
const orgProjects = ref<ProjectOut[]>([])
const mentorOrgs = ref<string[]>([])
const ownedProjects = ref<ProjectOut[]>([])
const mentorInbox = ref<ApplicationOut[]>([])
const communityCatalog = ref<CommunityOut[]>([])

const avatarText = computed(() => (auth.displayName || '?').slice(0, 2))

const boundCount = computed(() => {
  const u = auth.user
  if (!u) return 0
  return BIND_PROVIDERS.filter((p) => !!(u[p.field as keyof UserOut] as string | null | undefined))
    .length
})

const roleTags = computed(() => {
  const tags: string[] = []
  if (auth.canApplyProjects) tags.push('学生实习')
  if (auth.isMentor) tags.push('导师')
  if (auth.isCommunityAdmin) tags.push('社区管理')
  if (auth.hasRole('committee')) tags.push('组委会')
  return tags.length ? tags : ['平台用户']
})

const activeApps = computed(() =>
  apps.value.filter((a) => !['completed', 'withdrawn', 'rejected'].includes(a.status)),
)
const completedApps = computed(() => apps.value.filter((a) => a.status === 'completed'))
const recentApps = computed(() => apps.value.slice(0, 4))

const profileCompleteness = computed(() => {
  const f = form.value
  const checks = [
    f.display_name,
    f.school,
    f.major,
    f.contact_email || auth.user?.email,
    f.bio,
    boundCount.value > 0,
  ]
  return Math.round((checks.filter(Boolean).length / checks.length) * 100)
})

const nextSteps = computed(() => {
  const steps: { done: boolean; text: string; action: () => void; label: string }[] = [
    {
      done: profileCompleteness.value >= 70,
      text: '完善个人资料（学校 / 专业 / 简介）',
      action: () => setTab('profile'),
      label: '去完善',
    },
    {
      done: boundCount.value > 0,
      text: '绑定至少一个代码托管平台',
      action: () => setTab('bindings'),
      label: '去绑定',
    },
  ]
  if (auth.canApplyProjects) {
    steps.push({
      done: apps.value.length > 0,
      text: '领取并申请一个开源实习任务',
      action: () => router.push('/projects'),
      label: '去领取',
    })
  }
  return steps
})

function syncForm(u: UserOut | null) {
  if (!u) return
  form.value = {
    display_name: u.display_name || '',
    school: u.school || '',
    member_no: u.member_no || '',
    bio: u.bio || '',
    phone: u.phone || '',
    major: u.major || '',
    grade: u.grade || '',
    degree: u.degree || '',
    city: u.city || '',
    homepage_url: u.homepage_url || '',
    contact_email: u.contact_email || u.email || '',
  }
}

function boundOf(field: BindField) {
  return (auth.user?.[field] as string | null | undefined) || ''
}

async function loadOrgHome() {
  const { data: mine } = await api.get<CommunityOut[]>('/communities/admin-of')
  orgCommunity.value = mine[0] || null
  const community = orgCommunity.value
  if (!community) return
  const [members, drafts, published, closed] = await Promise.all([
    api.get<CommunityMemberOut[]>(`/communities/${community.id}/members`, { params: { role: 'mentor' } }),
    api.get<ProjectOut[]>('/projects', { params: { community_id: community.id, status: 'draft' } }),
    api.get<ProjectOut[]>('/projects', { params: { community_id: community.id, status: 'published' } }),
    api.get<ProjectOut[]>('/projects', { params: { community_id: community.id, status: 'closed' } }),
  ])
  orgMentors.value = members.data
  const seen = new Set<number>()
  orgProjects.value = [...published.data, ...drafts.data, ...closed.data].filter((p) => {
    if (seen.has(p.id)) return false
    seen.add(p.id)
    return true
  })
}

function mentorOf(project: ProjectOut) {
  return orgMentors.value.find((m) => m.user_id === project.mentor_id)?.display_name || '未指定'
}

function setTab(next: Tab) {
  router.replace({ path: '/me', query: { tab: next } })
}

async function loadApps() {
  if (!auth.canApplyProjects) {
    apps.value = []
    return
  }
  appsLoading.value = true
  appsError.value = ''
  try {
    const { data } = await api.get<ApplicationOut[]>('/applications/mine')
    apps.value = data
  } catch (e: unknown) {
    appsError.value = e instanceof Error ? e.message : '加载失败'
  } finally {
    appsLoading.value = false
  }
}

async function loadNotices() {
  noticesLoading.value = true
  try {
    const { data } = await api.get('/announcements')
    notices.value = (data as { id: number; title: string; published_at?: string | null }[]).slice(
      0,
      8,
    )
  } catch {
    notices.value = []
  } finally {
    noticesLoading.value = false
  }
}

async function saveProfile() {
  saving.value = true
  msg.value = ''
  err.value = ''
  try {
    const { data } = await api.patch<UserOut>('/auth/me', {
      display_name: form.value.display_name || null,
      school: form.value.school || null,
      bio: form.value.bio || null,
      phone: form.value.phone || null,
      major: form.value.major || null,
      grade: form.value.grade || null,
      degree: form.value.degree || null,
      city: form.value.city || null,
      homepage_url: form.value.homepage_url || null,
      contact_email: form.value.contact_email || null,
    })
    auth.user = data
    syncForm(data)
    msg.value = '资料已保存'
    toast.value?.show('个人资料保存成功', 'ok')
  } catch (e: unknown) {
    err.value = e instanceof Error ? e.message : '保存失败'
    toast.value?.show(err.value, 'err')
  } finally {
    saving.value = false
  }
}

async function changePassword() {
  msg.value = ''
  err.value = ''
  if (pwd.value.new_password.length < 6) {
    err.value = '新密码至少 6 位'
    return
  }
  if (pwd.value.new_password !== pwd.value.confirm) {
    err.value = '两次输入的新密码不一致'
    return
  }
  saving.value = true
  try {
    await api.post('/auth/me/password', {
      old_password: pwd.value.old_password,
      new_password: pwd.value.new_password,
    })
    pwd.value = { old_password: '', new_password: '', confirm: '' }
    msg.value = '密码已修改，请牢记新密码'
  } catch (e: unknown) {
    err.value = e instanceof Error ? e.message : '修改失败'
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  if (!auth.user) await auth.fetchMe()
  syncForm(auth.user)
  const jobs: Promise<unknown>[] = [loadNotices()]
  if (auth.canApplyProjects) jobs.push(loadApps())
  if (mentorOnly.value) {
    jobs.push(
      api.get<CommunityOut[]>('/communities', { params: { status: 'approved' } }).then(({ data }) => {
        communityCatalog.value = data
      }),
      api.get<ProjectOut[]>('/projects', { params: { owned: true } }).then(({ data }) => {
        ownedProjects.value = data
      }),
      api.get<ApplicationOut[]>('/mentor/inbox').then(({ data }) => {
        mentorInbox.value = data
      }),
    )
  }
  if (orgOnly.value) jobs.push(loadOrgHome())
  await Promise.all(jobs)
  if (mentorOnly.value) {
    const ids = new Set(
      (auth.user?.roles || [])
        .filter((r) => r.code === 'mentor' && r.community_id)
        .map((r) => r.community_id as number),
    )
    for (const p of ownedProjects.value) ids.add(p.community_id)
    mentorOrgs.value = communityCatalog.value.filter((c) => ids.has(c.id)).map((c) => c.name)
  }
  consumeBindResult()
})

watch(tab, async (t) => {
  msg.value = ''
  err.value = ''
  if (t === 'applications' || t === 'home') await loadApps()
  if (t === 'notices' || t === 'home') await loadNotices()
})

function consumeBindResult() {
  const bind = route.query.bind
  const okFlag = route.query.bind_ok
  if (!bind) return
  if (okFlag === '1') {
    bindMsg.value = `已完成 ${String(bind)} 授权绑定${route.query.login ? `：${route.query.login}` : ''}`
    bindErr.value = ''
    void auth.fetchMe()
  } else if (okFlag === '0') {
    bindErr.value = String(route.query.bind_err || '授权未完成')
    bindMsg.value = ''
  }
  const q = { ...route.query } as Record<string, string | string[]>
  delete q.bind
  delete q.bind_ok
  delete q.bind_err
  delete q.login
  router.replace({ path: '/me', query: { ...q, tab: orgOnly.value ? 'home' : 'bindings' } })
}
</script>

<template>
  <div class="me-shell">
    <div class="me-layout">
      <aside class="me-side">
        <div class="me-side-user">
          <div class="me-side-av">{{ avatarText }}</div>
          <div class="me-side-meta">
            <strong>{{ auth.displayName }}</strong>
            <span>{{
              orgOnly
                ? orgCommunity?.name || '组织账号'
                : mentorOnly
                  ? mentorOrgs.join('、') || '所属组织'
                  : auth.user?.school || '完善学校信息'
            }}</span>
          </div>
        </div>

        <nav class="me-side-nav" aria-label="个人中心">
          <button type="button" :class="{ on: tab === 'home' }" @click="setTab('home')">
            <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
              <path
                fill="currentColor"
                d="M12 3l9 7h-2v9h-5v-5H10v5H5v-9H3l9-7z"
              />
            </svg>
            概览
          </button>
          <button v-if="!orgOnly" type="button" :class="{ on: tab === 'notices' }" @click="setTab('notices')">
            <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
              <path
                fill="currentColor"
                d="M12 22a2 2 0 0 0 2-2h-4a2 2 0 0 0 2 2zm6-6V11a6 6 0 1 0-12 0v5l-2 2v1h16v-1l-2-2z"
              />
            </svg>
            通知公告
          </button>
          <button v-if="!orgOnly" type="button" :class="{ on: tab === 'profile' }" @click="setTab('profile')">
            <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
              <path
                fill="currentColor"
                d="M12 12a4 4 0 1 0-4-4 4 4 0 0 0 4 4zm0 2c-4 0-8 2-8 4v2h16v-2c0-2-4-4-8-4z"
              />
            </svg>
            个人资料
          </button>
          <button
            v-if="auth.canApplyProjects"
            type="button"
            :class="{ on: tab === 'applications' }"
            @click="setTab('applications')"
          >
            <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
              <path
                fill="currentColor"
                d="M4 4h7v7H4V4zm9 0h7v7h-7V4zM4 13h7v7H4v-7zm9 0h7v7h-7v-7z"
              />
            </svg>
            我的项目
            <em v-if="activeApps.length" class="me-count">{{ activeApps.length }}</em>
          </button>
          <button v-if="!orgOnly && !mentorOnly" type="button" :class="{ on: tab === 'bindings' }" @click="setTab('bindings')">
            <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
              <path
                fill="currentColor"
                d="M17 7h-3V5h3a5 5 0 0 1 0 10h-3v-2h3a3 3 0 0 0 0-6zM10 19H7a5 5 0 0 1 0-10h3v2H7a3 3 0 0 0 0 6h3v2zm-1-6h6v2H9v-2z"
              />
            </svg>
            平台绑定
            <em v-if="boundCount" class="me-count">{{ boundCount }}</em>
          </button>
          <button v-if="!orgOnly" type="button" :class="{ on: tab === 'password' }" @click="setTab('password')">
            <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
              <path
                fill="currentColor"
                d="M12 1a5 5 0 0 0-5 5v3H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8a2 2 0 0 0-2-2h-1V6a5 5 0 0 0-5-5zm0 2a3 3 0 0 1 3 3v3H9V6a3 3 0 0 1 3-3z"
              />
            </svg>
            修改密码
          </button>

          <template v-if="auth.isMentor || auth.isCommunityAdmin">
            <p class="me-nav-label">工作台</p>
            <RouterLink v-if="auth.isMentor" to="/mentor">导师工作台</RouterLink>
            <RouterLink v-if="auth.isCommunityAdmin" to="/org">组织工作台</RouterLink>
          </template>
        </nav>
      </aside>

      <main class="me-content">
        <ToastFeedback ref="toast" />

        <template v-if="tab === 'home' && orgOnly">
          <section class="me-banner">
            <div class="me-banner-bg" aria-hidden="true" />
            <div class="me-banner-body">
              <div class="me-banner-av">
                <img v-if="orgCommunity?.logo_url" :src="orgCommunity.logo_url" alt="" />
                <template v-else>{{ (orgCommunity?.name || '组').slice(0, 1) }}</template>
              </div>
              <div class="me-banner-info">
                <h1>{{ orgCommunity?.name || '组织账号' }}</h1>
                <div class="me-chips">
                  <span>社区管理员</span>
                  <span class="soft">{{ auth.user?.email }}</span>
                </div>
                <p>账号和密码都由组委会发放，不能在这里修改或删除。对外资料在组织工作台编辑并发布。</p>
              </div>
              <div class="me-banner-ops">
                <RouterLink v-if="orgCommunity" class="primary" :to="`/communities/${orgCommunity.slug}`">公开主页</RouterLink>
                <RouterLink class="ghost" to="/org">去编辑</RouterLink>
              </div>
            </div>
          </section>

          <section class="me-kpi">
            <button type="button">
              <strong>{{ orgMentors.length }}</strong>
              <span>旗下导师</span>
            </button>
            <button type="button">
              <strong>{{ orgProjects.length }}</strong>
              <span>项目</span>
            </button>
            <button type="button">
              <strong>{{ orgProjects.filter((p) => p.status === 'published').length }}</strong>
              <span>对外展示中</span>
            </button>
          </section>

          <section class="me-grid">
            <article class="card">
              <header><h2>组织信息</h2></header>
              <p v-if="!orgCommunity" class="empty">还没有绑定可管理的社区，请联系组委会。</p>
              <dl v-else class="org-facts">
                <div><dt>名称</dt><dd>{{ orgCommunity.name }}</dd></div>
                <div><dt>简介</dt><dd>{{ orgCommunity.description || '还没写简介' }}</dd></div>
                <div><dt>官网</dt><dd>{{ orgCommunity.homepage_url || '未填写' }}</dd></div>
                <div><dt>仓库</dt><dd>{{ orgCommunity.gitea_org_url || '未填写' }}</dd></div>
                <div>
                  <dt>标签</dt>
                  <dd>{{ orgCommunity.tags?.length ? orgCommunity.tags.join('、') : '未填写' }}</dd>
                </div>
              </dl>
            </article>

            <article class="card">
              <header>
                <h2>旗下导师</h2>
                <RouterLink class="more" to="/org?tab=mentors">邀请</RouterLink>
              </header>
              <p v-if="!orgMentors.length" class="empty">还没有导师。到组织工作台用邀请码邀请。</p>
              <ul v-else class="rows">
                <li v-for="m in orgMentors" :key="m.user_id">
                  <div>
                    <strong>{{ m.display_name }}</strong>
                    <small>{{ m.email }}</small>
                  </div>
                </li>
              </ul>
            </article>

            <article class="card wide">
              <header>
                <h2>项目</h2>
                <RouterLink class="more" to="/org">管理</RouterLink>
              </header>
              <p v-if="!orgProjects.length" class="empty">还没有项目。创建和分配导师在组织工作台完成。</p>
              <div v-else class="mentor-proj">
                <article v-for="p in orgProjects" :key="p.id">
                  <div>
                    <strong>{{ p.title }}</strong>
                    <p>{{ p.summary || '暂无简介' }}</p>
                    <small>
                      导师 {{ mentorOf(p) }} · 名额 {{ p.seats_taken || 0 }}/{{ p.quota }} · {{ projectStatusLabel(p.status) }}
                    </small>
                  </div>
                  <div class="mentor-proj-links">
                    <RouterLink :to="`/projects/${p.id}`">查看任务</RouterLink>
                  </div>
                </article>
              </div>
            </article>
          </section>
        </template>

        <template v-else-if="tab === 'home'">
          <section class="me-banner">
            <div class="me-banner-bg" aria-hidden="true" />
            <div class="me-banner-body">
              <div class="me-banner-av">{{ avatarText }}</div>
              <div class="me-banner-info">
                <h1>{{ auth.displayName }}</h1>
                <div class="me-chips">
                  <span v-for="t in roleTags" :key="t">{{ t }}</span>
                  <span v-if="auth.user?.email" class="soft">{{ auth.user.email }}</span>
                </div>
                <p v-if="mentorOnly">
                  {{ auth.user?.email }} · {{ mentorOrgs.join('、') || '尚未分配组织' }}
                </p>
                <p v-else>{{ form.bio || '在这里管理实习申请、开源账号绑定与个人资料。' }}</p>
                <div v-if="!mentorOnly" class="me-progress">
                  <span>资料完整度</span>
                  <div class="bar"><i :style="{ width: profileCompleteness + '%' }" /></div>
                  <b>{{ profileCompleteness }}%</b>
                </div>
              </div>
              <div class="me-banner-ops">
                <button v-if="!mentorOnly" type="button" class="primary" @click="setTab('profile')">编辑资料</button>
                <RouterLink v-if="mentorOnly" class="ghost" to="/mentor/projects">我的项目</RouterLink>
                <RouterLink v-else class="ghost" to="/projects">去看项目</RouterLink>
              </div>
            </div>
          </section>

          <section class="me-kpi">
            <button type="button" @click="auth.canApplyProjects && setTab('applications')">
              <strong>{{ activeApps.length }}</strong>
              <span>进行中项目</span>
            </button>
            <button type="button" @click="auth.canApplyProjects && setTab('applications')">
              <strong>{{ completedApps.length }}</strong>
              <span>已结项</span>
            </button>
            <button v-if="!mentorOnly" type="button" @click="setTab('bindings')">
              <strong>{{ boundCount }}/{{ BIND_PROVIDERS.length }}</strong>
              <span>平台绑定</span>
            </button>
            <button v-else type="button">
              <strong>{{ ownedProjects.length }}</strong>
              <span>负责项目</span>
            </button>
            <button type="button" @click="setTab('notices')">
              <strong>{{ notices.length }}</strong>
              <span>近期公告</span>
            </button>
          </section>

          <section class="me-grid">
            <article class="card">
              <header>
                <h2>最近项目</h2>
                <button
                  v-if="auth.canApplyProjects"
                  type="button"
                  class="more"
                  @click="setTab('applications')"
                >
                  全部
                </button>
              </header>
              <p v-if="mentorOnly && !ownedProjects.length" class="empty">还没有分配给你的项目。</p>
              <ul v-else-if="mentorOnly" class="rows">
                <li v-for="p in ownedProjects" :key="p.id">
                  <RouterLink :to="`/projects/${p.id}`">
                    <strong>{{ p.title }}</strong>
                    <small>{{ mentorOrgs[0] || '所属组织' }}</small>
                  </RouterLink>
                  <span class="badge" :class="statusTone(p.status)">{{ projectStatusLabel(p.status) }}</span>
                </li>
              </ul>
              <p v-else-if="!auth.canApplyProjects" class="empty">组织侧账号请使用右侧工作台入口。</p>
              <p v-else-if="appsLoading" class="empty">加载中…</p>
              <p v-else-if="!recentApps.length" class="empty">
                暂无申请。
                <RouterLink to="/projects">去社区领取任务 ›</RouterLink>
              </p>
              <ul v-else class="rows">
                <li v-for="a in recentApps" :key="a.id">
                  <RouterLink :to="`/student/applications/${a.id}?tab=task`">
                    <strong>{{ a.project_title || `项目 #${a.project_id}` }}</strong>
                    <small>{{ stageLabel(a.status, a.current_node) || '—' }}</small>
                  </RouterLink>
                  <span class="badge" :class="statusTone(a.status)">{{ statusLabel(a.status) }}</span>
                </li>
              </ul>
            </article>

            <article v-if="mentorOnly" class="card">
              <header>
                <h2>名下学生</h2>
                <RouterLink class="more" to="/mentor">去处理</RouterLink>
              </header>
              <p v-if="!mentorInbox.length" class="empty">还没有学生申请你的项目。</p>
              <ul v-else class="rows">
                <li v-for="a in mentorInbox" :key="'m-' + a.id">
                  <RouterLink :to="`/mentor/a/${a.id}`">
                    <strong>{{ a.student_name || a.student_email || `同学 #${a.student_id}` }}</strong>
                    <small>{{ a.project_title || '负责项目' }}</small>
                  </RouterLink>
                  <span class="badge" :class="statusTone(a.status)">{{ statusLabel(a.status) }}</span>
                </li>
              </ul>
            </article>

            <article v-if="mentorOnly" class="card wide">
              <header>
                <h2>项目一览</h2>
                <RouterLink class="more" to="/mentor/projects">管理</RouterLink>
              </header>
              <div v-if="!ownedProjects.length" class="empty">还没有分配给你的项目。</div>
              <div v-else class="mentor-proj">
                <article v-for="p in ownedProjects" :key="'p-' + p.id">
                  <div>
                    <strong>{{ p.title }}</strong>
                    <p>{{ p.summary || '暂无简介' }}</p>
                    <small>
                      {{ mentorOrgs.join('、') || '所属组织' }}
                      · 名额 {{ p.seats_taken || 0 }}/{{ p.quota }}
                      · {{ projectStatusLabel(p.status) }}
                    </small>
                  </div>
                  <div class="mentor-proj-links">
                    <RouterLink :to="`/projects/${p.id}`">任务书</RouterLink>
                    <RouterLink to="/mentor">审核学生</RouterLink>
                  </div>
                </article>
              </div>
            </article>

            <article v-if="mentorOnly" class="card">
              <header>
                <h2>近期公告</h2>
                <button type="button" class="more" @click="setTab('notices')">全部</button>
              </header>
              <p v-if="!notices.length" class="empty">暂无公告。结项结果发布后会出现在结项公示。</p>
              <ul v-else class="rows">
                <li v-for="n in notices.slice(0, 4)" :key="n.id">
                  <RouterLink to="/completed">
                    <strong>{{ n.title }}</strong>
                    <small>{{ n.published_at || '近期' }}</small>
                  </RouterLink>
                </li>
              </ul>
            </article>

            <article v-if="!mentorOnly" class="card">
              <header>
                <h2>下一步</h2>
              </header>
              <ul class="todo">
                <li v-for="(s, i) in nextSteps" :key="i" :class="{ done: s.done }">
                  <span class="mark">{{ s.done ? '✓' : i + 1 }}</span>
                  <span class="txt">{{ s.text }}</span>
                  <button v-if="!s.done" type="button" @click="s.action">{{ s.label }}</button>
                  <em v-else>已完成</em>
                </li>
              </ul>
            </article>

            <article v-if="!mentorOnly" class="card wide">
              <header>
                <h2>开源账号绑定</h2>
                <button type="button" class="more" @click="setTab('bindings')">管理</button>
              </header>
              <div class="bind-grid">
                <div v-for="p in BIND_PROVIDERS" :key="p.key" class="bind-chip">
                  <span class="logo" :style="{ background: p.color }">{{ p.mark }}</span>
                  <div>
                    <strong>{{ p.name }}</strong>
                    <small v-if="boundOf(p.field)" class="ok">@{{ boundOf(p.field) }}</small>
                    <small v-else class="no">未绑定</small>
                  </div>
                </div>
              </div>
            </article>
          </section>
        </template>

        <!-- 其它页：干净内容区，不再重复大头图 -->
        <template v-else>
          <p v-if="msg && tab !== 'profile'" class="success-msg">{{ msg }}</p>
          <p v-if="err && tab !== 'profile'" class="error">{{ err }}</p>

          <template v-if="tab === 'notices'">
            <div class="page-head">
              <h1>通知公告</h1>
              <p>俱乐部与组委会发布的活动、节点提醒。</p>
            </div>
            <p v-if="noticesLoading" class="muted">加载中…</p>
            <div v-else-if="!notices.length" class="empty-box">
              <p>暂无通知。</p>
              <RouterLink class="btn sm" to="/announcements">查看公示</RouterLink>
            </div>
            <div v-else class="list">
              <RouterLink v-for="n in notices" :key="n.id" class="list-item" to="/announcements">
                <div>
                  <strong>{{ n.title }}</strong>
                  <span>{{ n.published_at || '近期发布' }}</span>
                </div>
                <em class="badge">公告</em>
              </RouterLink>
            </div>
          </template>

          <template v-else-if="tab === 'profile'">
            <div class="page-head">
              <h1>个人资料</h1>
              <p>完整度 {{ profileCompleteness }}% · 便于导师审核与结项核验</p>
            </div>
            <p v-if="msg" class="success-msg">{{ msg }}</p>
            <p v-if="err" class="error">{{ err }}</p>
            <form class="form wide me-form" @submit.prevent="saveProfile">
              <div class="form-grid-2">
                <label>
                  显示名称 <span class="req">*</span>
                  <input v-model="form.display_name" required />
                </label>
                <label>
                  登录邮箱
                  <input :value="auth.user?.email || ''" disabled />
                </label>
                <label>
                  通知邮箱 <span class="req">*</span>
                  <input v-model="form.contact_email" type="email" required />
                </label>
                <label>
                  手机号
                  <input v-model="form.phone" placeholder="选填" />
                </label>
                <label>
                  学校 / 单位
                  <input v-model="form.school" />
                </label>
                <label>
                  学院 / 专业
                  <input v-model="form.major" />
                </label>
                <label>
                  年级 / 入学年份
                  <input v-model="form.grade" />
                </label>
                <label>
                  学历
                  <input v-model="form.degree" placeholder="本科 / 硕士 / 博士" />
                </label>
                <label>
                  学号 / 工号
                  <input v-model="form.member_no" disabled title="学号/工号不可手填修改" />
                </label>
                <label>
                  所在城市
                  <input v-model="form.city" />
                </label>
              </div>
              <label>
                个人主页 / 博客
                <input v-model="form.homepage_url" placeholder="https://" />
              </label>
              <label>
                个人简介
                <textarea v-model="form.bio" rows="4" placeholder="技术方向、开源经历、可投入时间" />
              </label>
              <button class="btn" type="submit" :disabled="saving">
                {{ saving ? '保存中…' : '保存资料' }}
              </button>
            </form>
          </template>

          <template v-else-if="tab === 'applications'">
            <div class="page-head row">
              <div>
                <h1>我的项目</h1>
                <p>申请审核、开发与结项进度。</p>
              </div>
              <RouterLink class="btn secondary sm" to="/projects">去查看项目</RouterLink>
            </div>
            <p v-if="appsLoading" class="muted">加载中…</p>
            <p v-else-if="appsError" class="error">{{ appsError }}</p>
            <div v-else-if="!apps.length" class="empty-box">
              <p>还没有申请记录。</p>
              <RouterLink class="btn sm" to="/projects">浏览社区任务</RouterLink>
            </div>
            <div v-else class="list">
              <RouterLink
                v-for="a in apps"
                :key="a.id"
                class="list-item"
                :to="`/student/applications/${a.id}?tab=task`"
              >
                <div>
                  <strong>{{ a.project_title || `项目 #${a.project_id}` }}</strong>
                  <span>申请 #{{ a.id }} · {{ stageLabel(a.status, a.current_node) }}</span>
                </div>
                <em class="badge" :class="statusTone(a.status)">{{ statusLabel(a.status) }}</em>
              </RouterLink>
            </div>
          </template>

          <template v-else-if="tab === 'bindings'">
            <div class="page-head">
              <h1>平台绑定</h1>
              <p>已绑 {{ boundCount }} / {{ BIND_PROVIDERS.length }} · 用于结项 PR 核验</p>
            </div>
            <p v-if="bindMsg" class="success-msg">{{ bindMsg }}</p>
            <p v-if="bindErr" class="error">{{ bindErr }}</p>
            <div class="link-list">
              <article v-for="p in BIND_PROVIDERS" :key="p.key" class="link-row">
                <div class="link-row-main">
                  <span
                    class="link-row-mark"
                    :style="{
                      background: auth.user?.oauth_avatars?.[p.key]
                        ? `center / cover url(${auth.user.oauth_avatars[p.key]})`
                        : p.color,
                    }"
                  >
                    <template v-if="!auth.user?.oauth_avatars?.[p.key]">{{ p.mark }}</template>
                  </span>
                  <div class="link-row-text">
                    <strong>{{ p.name }}</strong>
                    <span>{{ p.desc }}</span>
                  </div>
                </div>
                <div class="link-row-side">
                  <span v-if="boundOf(p.field)" class="link-row-bound">@{{ boundOf(p.field) }}</span>
                  <span v-else class="link-row-empty">未绑定</span>
                  <RouterLink class="link-row-btn" :to="`/me/bind/${p.key}`">
                    {{ boundOf(p.field) ? '管理' : '去绑定' }}
                  </RouterLink>
                </div>
              </article>
            </div>
          </template>

          <template v-else>
            <div class="pwd-wrap">
              <div class="pwd-card">
                <div class="pwd-head">
                  <span class="pwd-lock" aria-hidden="true">锁</span>
                  <div>
                    <h1>修改密码</h1>
                    <p v-if="orgOnly">登录邮箱由组委会发放，不能更换。这里只改你自己的登录密码。</p>
                    <p v-else>修改成功后请使用新密码登录，旧密码会立即失效。</p>
                  </div>
                </div>
                <form class="form pwd-form" @submit.prevent="changePassword">
                  <label>
                    原密码 <span class="req">*</span>
                    <input
                      v-model="pwd.old_password"
                      type="password"
                      required
                      autocomplete="current-password"
                      placeholder="当前登录密码"
                    />
                  </label>
                  <label>
                    新密码 <span class="req">*</span>
                    <input
                      v-model="pwd.new_password"
                      type="password"
                      required
                      minlength="6"
                      autocomplete="new-password"
                      placeholder="至少 6 位"
                    />
                    <span class="pwd-meter" :data-level="pwdLevel">
                      <i /><i /><i />
                      <em>{{ pwdHint }}</em>
                    </span>
                  </label>
                  <label>
                    确认新密码 <span class="req">*</span>
                    <input
                      v-model="pwd.confirm"
                      type="password"
                      required
                      minlength="6"
                      autocomplete="new-password"
                      placeholder="再输入一次新密码"
                    />
                  </label>
                  <button class="btn pwd-submit" type="submit" :disabled="saving">
                    {{ saving ? '提交中…' : '确认修改密码' }}
                  </button>
                </form>
              </div>
              <aside class="pwd-aside">
                <h2>建议</h2>
                <ul>
                  <li>至少 6 位，建议同时包含字母和数字</li>
                  <li>不要使用姓名、学号或邮箱前缀</li>
                  <li>改完后用新密码重新登录</li>
                </ul>
              </aside>
            </div>
          </template>
        </template>
      </main>
    </div>
  </div>
</template>

<style scoped>
.pwd-wrap {
  display: grid;
  grid-template-columns: minmax(0, 520px) 240px;
  gap: 16px;
  align-items: start;
}
.pwd-card,
.pwd-aside {
  background: #fff;
  border: 1px solid #e8ebf0;
  border-radius: 12px;
}
.pwd-card {
  padding: 22px 24px 26px;
}
.pwd-head {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  margin-bottom: 18px;
}
.pwd-head h1 {
  margin: 0 0 4px;
  font-size: 1.3rem;
}
.pwd-head p {
  margin: 0;
  color: #8c8c8c;
  font-size: 0.88rem;
}
.pwd-lock {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  background: #e8f1ff;
  color: #0b3d91;
  display: grid;
  place-items: center;
  font-size: 0.85rem;
  font-weight: 700;
  flex-shrink: 0;
}
.pwd-form {
  max-width: none;
}
.pwd-form label {
  display: block;
  margin-bottom: 14px;
  font-size: 0.9rem;
}
.pwd-form input {
  display: block;
  width: 100%;
  margin-top: 6px;
  box-sizing: border-box;
}
.pwd-meter {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 8px;
}
.pwd-meter i {
  width: 42px;
  height: 4px;
  border-radius: 99px;
  background: #e5e7eb;
}
.pwd-meter em {
  font-style: normal;
  font-size: 0.75rem;
  color: #8c8c8c;
}
.pwd-meter[data-level='1'] i:nth-child(1) { background: #f97316; }
.pwd-meter[data-level='2'] i:nth-child(-n + 2) { background: #eab308; }
.pwd-meter[data-level='3'] i { background: #16a34a; }
.pwd-submit {
  width: 100%;
  margin-top: 6px;
}
.pwd-aside {
  padding: 18px 16px;
}
.pwd-aside h2 {
  margin: 0 0 10px;
  font-size: 0.95rem;
}
.pwd-aside ul {
  margin: 0;
  padding-left: 1.1rem;
  color: #595959;
  font-size: 0.86rem;
  line-height: 1.7;
}
@media (max-width: 860px) {
  .pwd-wrap {
    grid-template-columns: 1fr;
  }
}
.me-shell {
  background: #f3f5f8;
  min-height: calc(100vh - var(--nav-h, 64px));
  padding: 24px 0 48px;
}
.me-layout {
  width: min(1280px, 96%);
  margin: 0 auto;
  display: grid;
  grid-template-columns: 220px minmax(0, 1fr);
  gap: 16px;
  align-items: start;
}
.me-side {
  position: sticky;
  top: calc(var(--nav-h, 64px) + 12px);
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.me-side-user {
  background: #fff;
  border: 1px solid #e8ebf0;
  border-radius: 10px;
  padding: 16px;
  display: flex;
  gap: 12px;
  align-items: center;
}
.me-side-av {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  background: #0b3d91;
  color: #fff;
  display: grid;
  place-items: center;
  font-weight: 700;
  flex-shrink: 0;
}
.me-side-meta strong {
  display: block;
  font-size: 0.95rem;
  color: #1a1a1a;
}
.me-side-meta span {
  display: block;
  margin-top: 2px;
  font-size: 0.75rem;
  color: #8c8c8c;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 120px;
}
.me-side-nav {
  background: #fff;
  border: 1px solid #e8ebf0;
  border-radius: 10px;
  padding: 8px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.me-side-nav button,
.me-side-nav a {
  display: flex;
  align-items: center;
  gap: 10px;
  border: 0;
  background: transparent;
  color: #4b5563;
  font: inherit;
  font-size: 0.92rem;
  padding: 11px 12px;
  border-radius: 8px;
  cursor: pointer;
  text-align: left;
  text-decoration: none !important;
}
.me-side-nav button.on {
  background: #e8f1ff;
  color: #0b3d91;
  font-weight: 650;
}
.me-side-nav button:hover,
.me-side-nav a:hover {
  background: #f5f7fa;
}
.me-side-nav svg {
  flex-shrink: 0;
  opacity: 0.85;
}
.me-count {
  margin-left: auto;
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  border-radius: 999px;
  background: #2563eb;
  color: #fff;
  font-size: 11px;
  font-style: normal;
  display: grid;
  place-items: center;
}
.me-nav-label {
  margin: 10px 12px 4px;
  font-size: 0.7rem;
  color: #bfbfbf;
  letter-spacing: 0.06em;
}

.me-content {
  min-width: 0;
}

.me-banner {
  position: relative;
  border-radius: 12px;
  overflow: hidden;
  margin-bottom: 14px;
  background: #0b3d91;
  color: #fff;
}
.me-banner-bg {
  position: absolute;
  inset: 0;
  background:
    radial-gradient(circle at 88% 18%, rgba(245, 197, 24, 0.28), transparent 42%),
    linear-gradient(115deg, #0b3d91 0%, #164a9e 45%, #0f2d66 100%);
  opacity: 1;
}
.me-banner-body {
  position: relative;
  display: flex;
  gap: 18px;
  align-items: flex-start;
  padding: 22px 22px 20px;
}
.me-banner-av {
  width: 76px;
  height: 76px;
  border-radius: 50%;
  border: 2px solid rgba(245, 197, 24, 0.65);
  background: rgba(255, 255, 255, 0.12);
  display: grid;
  place-items: center;
  font-size: 1.4rem;
  font-weight: 700;
  flex-shrink: 0;
}
.me-banner-info {
  flex: 1;
  min-width: 0;
}
.me-banner-info h1 {
  margin: 0 0 8px;
  font-size: 1.45rem;
}
.me-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 10px;
}
.me-chips span {
  padding: 2px 10px;
  border-radius: 999px;
  font-size: 0.72rem;
  background: rgba(255, 255, 255, 0.14);
  border: 1px solid rgba(255, 255, 255, 0.2);
}
.me-chips .soft {
  background: rgba(245, 197, 24, 0.16);
  border-color: rgba(245, 197, 24, 0.35);
  color: #ffe7a3;
}
.me-banner-info > p {
  margin: 0 0 12px;
  font-size: 0.88rem;
  line-height: 1.55;
  color: rgba(255, 255, 255, 0.84);
  max-width: 40rem;
}
.me-progress {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 0.78rem;
  color: rgba(255, 255, 255, 0.78);
}
.me-progress .bar {
  width: min(220px, 40vw);
  height: 6px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.2);
  overflow: hidden;
}
.me-progress .bar i {
  display: block;
  height: 100%;
  background: linear-gradient(90deg, #f5c518, #ffe08a);
}
.me-progress b {
  color: #ffe7a3;
  font-variant-numeric: tabular-nums;
}
.me-banner-ops {
  display: flex;
  flex-direction: column;
  gap: 8px;
  flex-shrink: 0;
}
.me-banner-ops .primary,
.me-banner-ops .ghost {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 108px;
  padding: 8px 14px;
  border-radius: 6px;
  font: inherit;
  font-size: 0.86rem;
  font-weight: 600;
  cursor: pointer;
  text-decoration: none !important;
  border: 0;
}
.me-banner-ops .primary {
  background: #fff;
  color: #0b3d91;
}
.me-banner-ops .ghost {
  background: transparent;
  color: #fff;
  border: 1px solid rgba(255, 255, 255, 0.4);
}

.me-kpi {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 14px;
}
.me-kpi button {
  background: #fff;
  border: 1px solid #e8ebf0;
  border-radius: 10px;
  padding: 16px 12px;
  text-align: center;
  cursor: pointer;
  font: inherit;
}
.me-kpi button:hover {
  border-color: #91caff;
  box-shadow: 0 4px 14px rgba(24, 144, 255, 0.08);
}
.me-kpi strong {
  display: block;
  font-size: 1.5rem;
  color: #0b3d91;
  line-height: 1.1;
}
.me-kpi span {
  display: block;
  margin-top: 6px;
  font-size: 0.8rem;
  color: #8c8c8c;
}

.me-grid {
  display: grid;
  grid-template-columns: 1.15fr 0.85fr;
  gap: 12px;
}
.mentor-proj {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.mentor-proj article {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
  padding: 12px;
  border: 1px solid #f0f0f0;
  border-radius: 8px;
  background: #fafafa;
}
.mentor-proj strong { display: block; margin-bottom: 4px; }
.mentor-proj p { margin: 0 0 6px; color: #595959; font-size: 0.88rem; }
.mentor-proj small { color: #8c8c8c; }
.mentor-proj-links { display: flex; flex-direction: column; gap: 6px; white-space: nowrap; }
.mentor-proj-links a { color: #0b3d91; font-size: 0.86rem; }
.card {
  background: #fff;
  border: 1px solid #e8ebf0;
  border-radius: 10px;
  padding: 16px 18px;
}
.card.wide {
  grid-column: 1 / -1;
}
.org-facts { margin: 0; }
.org-facts div { display: grid; grid-template-columns: 4.5rem minmax(0, 1fr); gap: 8px; padding: 8px 0; border-bottom: 1px solid #f0f0f0; }
.org-facts div:last-child { border-bottom: 0; }
.org-facts dt { color: #8c8c8c; }
.org-facts dd { margin: 0; }
.me-banner-av img { width: 100%; height: 100%; object-fit: cover; border-radius: inherit; }
.card header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.card h2 {
  margin: 0;
  font-size: 1rem;
}
.more {
  border: 0;
  background: none;
  color: #1890ff;
  font: inherit;
  font-size: 0.84rem;
  cursor: pointer;
}
.empty {
  margin: 8px 0;
  color: #8c8c8c;
  font-size: 0.9rem;
}
.rows {
  list-style: none;
  margin: 0;
  padding: 0;
}
.rows li {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 0;
  border-bottom: 1px solid #f0f0f0;
}
.rows li:last-child {
  border-bottom: 0;
}
.rows a {
  flex: 1;
  min-width: 0;
  text-decoration: none !important;
  color: inherit;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.rows strong {
  font-size: 0.92rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.rows small {
  color: #8c8c8c;
  font-size: 0.78rem;
}
.todo {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.todo li {
  display: grid;
  grid-template-columns: 24px 1fr auto;
  gap: 10px;
  align-items: center;
  font-size: 0.88rem;
}
.todo .mark {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  background: #e8f1ff;
  color: #0b3d91;
  font-size: 0.75rem;
  font-weight: 700;
}
.todo li.done .mark {
  background: #e8f8ef;
  color: #16a34a;
}
.todo li.done .txt {
  color: #8c8c8c;
  text-decoration: line-through;
}
.todo button {
  border: 1px solid #91caff;
  background: #f0f7ff;
  color: #1677ff;
  border-radius: 999px;
  padding: 3px 10px;
  font: inherit;
  font-size: 0.75rem;
  cursor: pointer;
}
.todo em {
  font-style: normal;
  font-size: 0.75rem;
  color: #52c41a;
}
.bind-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 10px;
}
.bind-chip {
  display: flex;
  gap: 10px;
  align-items: center;
  padding: 10px;
  border: 1px solid #f0f0f0;
  border-radius: 8px;
  background: #fafafa;
}
.bind-chip .logo {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  color: #fff;
  display: grid;
  place-items: center;
  font-size: 0.7rem;
  font-weight: 700;
  flex-shrink: 0;
}
.bind-chip strong {
  display: block;
  font-size: 0.86rem;
}
.bind-chip small {
  font-size: 0.75rem;
}
.bind-chip .ok {
  color: #1677ff;
}
.bind-chip .no {
  color: #bfbfbf;
}

.page-head {
  margin-bottom: 18px;
}
.page-head.row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}
.page-head h1 {
  margin: 0 0 6px;
  font-size: 1.35rem;
}
.page-head p {
  margin: 0;
  color: #8c8c8c;
  font-size: 0.9rem;
}
.me-form {
  max-width: 720px;
}
.me-form .req {
  color: #ff4d4f;
}
.empty-box {
  padding: 40px 16px;
  text-align: center;
  color: #8c8c8c;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  background: #fff;
  border: 1px dashed #d9d9d9;
  border-radius: 10px;
}
.list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.list-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
  background: #fff;
  border: 1px solid #e8ebf0;
  border-radius: 8px;
  text-decoration: none !important;
  color: inherit;
}
.list-item:hover {
  border-color: #91caff;
}
.list-item strong {
  display: block;
  margin-bottom: 4px;
}
.list-item span {
  font-size: 0.8rem;
  color: #8c8c8c;
}

@media (max-width: 980px) {
  .me-layout {
    grid-template-columns: 1fr;
  }
  .me-side {
    position: static;
  }
  .me-banner-body {
    flex-direction: column;
  }
  .me-banner-ops {
    flex-direction: row;
  }
  .me-kpi {
    grid-template-columns: repeat(2, 1fr);
  }
  .me-grid {
    grid-template-columns: 1fr;
  }
  .bind-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
