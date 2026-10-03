import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'home', component: () => import('@/views/HomeView.vue') },
    { path: '/login', name: 'login', component: () => import('@/views/LoginView.vue'), meta: { guest: true } },
    { path: '/register', name: 'register', component: () => import('@/views/RegisterView.vue'), meta: { guest: true } },
    {
      path: '/register/mentor',
      name: 'register-mentor',
      component: () => import('@/views/MentorRegisterView.vue'),
      meta: { guest: true },
    },
    { path: '/communities', name: 'communities', component: () => import('@/views/CommunitiesView.vue') },
    { path: '/communities/:slug', name: 'community-detail', component: () => import('@/views/CommunityDetailView.vue') },
    { path: '/projects', name: 'projects', component: () => import('@/views/ProjectsView.vue') },
    { path: '/projects/:id/apply', name: 'project-apply', component: () => import('@/views/ProjectApplyView.vue'), meta: { requiresAuth: true } },
    { path: '/projects/:id', name: 'project-detail', component: () => import('@/views/ProjectDetailView.vue') },
    { path: '/announcements', redirect: '/completed' },
    { path: '/guide', name: 'guide', component: () => import('@/views/GuideView.vue') },
    { path: '/news', name: 'news', component: () => import('@/views/NewsView.vue') },
    { path: '/news/:id', name: 'news-post', component: () => import('@/views/NewsPostView.vue') },
    { path: '/banner/:id', name: 'banner', component: () => import('@/views/BannerView.vue') },
    { path: '/completed', name: 'completed', component: () => import('@/views/CompletedView.vue') },
    {
      path: '/me',
      name: 'profile-center',
      component: () => import('@/views/ProfileCenterView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/me/bind/:provider',
      name: 'bind-authorize',
      component: () => import('@/views/BindAuthorizeView.vue'),
      meta: { requiresAuth: true },
    },
    {
      // 旧开发配置页入口：一律回到绑定详情
      path: '/me/oauth-setup',
      redirect: (to) => {
        const provider = String(to.query.provider || 'gitcode')
        return { path: `/me/bind/${provider}` }
      },
    },
    {
      path: '/me/oauth-consent',
      redirect: (to) => {
        const provider = String(to.query.provider || 'gitcode')
        return { path: `/me/bind/${provider}` }
      },
    },
    {
      path: '/student/applications',
      name: 'student-applications',
      redirect: { path: '/me', query: { tab: 'applications' } },
    },
    {
      path: '/student/applications/:id',
      name: 'student-application-detail',
      component: () => import('@/views/student/ApplicationDetailView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/student/applications/:id/progress',
      name: 'student-progress-update',
      component: () => import('@/views/student/ProgressUpdateView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/student/applications/:id/final',
      name: 'student-final-submit',
      component: () => import('@/views/student/FinalSubmitView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/student/applications/:id/reward',
      name: 'student-reward',
      component: () => import('@/views/student/RewardApplyView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/org',
      name: 'org-portal',
      component: () => import('@/views/org/OrgPortalView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/org/final/:id',
      name: 'org-final-submit',
      component: () => import('@/views/org/CommunityFinalSubmitView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/mentor/community',
      name: 'mentor-community',
      component: () => import('@/views/mentor/MentorCommunityView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/mentor',
      name: 'mentor-workbench',
      component: () => import('@/views/mentor/MentorDeskView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/mentor/a/:id',
      name: 'mentor-student',
      component: () => import('@/views/mentor/MentorDeskView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/mentor/review/:id',
      redirect: (to) => `/mentor/a/${to.params.id}`,
    },
    {
      path: '/mentor/projects',
      name: 'mentor-projects',
      component: () => import('@/views/mentor/MyProjectsView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/mentor/reviews',
      redirect: '/mentor',
    },
    {
      path: '/community/reviews',
      redirect: { path: '/org', query: { tab: 'liaison' } },
    },
    {
      // 隐藏入口：不对公开登录页展示、不进主导航
      path: '/ops/login',
      name: 'committee-login',
      component: () => import('@/views/committee/CommitteeLoginView.vue'),
      meta: { guest: true, committeePortal: true },
    },
    {
      path: '/committee',
      name: 'committee',
      component: () => import('@/views/committee/CommitteeWorkbenchView.vue'),
      meta: { requiresAuth: true, requiresCommittee: true },
    },
    {
      path: '/committee/oauth',
      name: 'committee-oauth',
      component: () => import('@/views/committee/OAuthAdminView.vue'),
      meta: { requiresAuth: true, requiresCommittee: true },
    },
  ],
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  auth.alignScope(to.path)
  if (auth.token && !auth.user) {
    const who = await auth.fetchMe()
    if (who === 'disabled' && to.name !== 'login' && to.name !== 'committee-login') {
      const role = to.path.startsWith('/mentor') ? 'mentor' : to.path.startsWith('/org') ? 'org' : 'student'
      return { name: 'login', query: { role } }
    }
  }
  if (to.meta.requiresAuth && !auth.isLoggedIn) {
    if (to.meta.requiresCommittee) {
      return { name: 'committee-login', query: { redirect: to.fullPath } }
    }
    const orgPaths = ['/org', '/community']
    const mentorPaths = ['/mentor']
    const asOrg = orgPaths.some((p) => to.path.startsWith(p))
    const asMentor = mentorPaths.some((p) => to.path.startsWith(p))
    return {
      name: 'login',
      query: {
        redirect: to.fullPath,
        ...(asMentor ? { role: 'mentor' } : asOrg ? { role: 'org' } : {}),
      },
    }
  }
  if (to.meta.requiresCommittee && !auth.hasRole('committee')) {
    return { name: 'committee-login', query: { redirect: to.fullPath } }
  }
  if (auth.isLoggedIn && to.path.startsWith('/mentor') && !auth.hasRole('mentor')) {
    return { path: auth.portalHome() }
  }
  if (
    auth.isLoggedIn &&
    (to.path.startsWith('/org') || to.path.startsWith('/community')) &&
    !auth.hasRole('community_admin') &&
    !auth.hasRole('committee')
  ) {
    return { path: auth.hasRole('mentor') ? '/mentor' : auth.portalHome() }
  }
  if (
    to.path === '/projects' &&
    auth.isLoggedIn &&
    auth.isMentor &&
    !auth.canApplyProjects
  ) {
    return { path: '/mentor/projects' }
  }
  // 纯导师禁止进入组织工作台
  if (
    to.path.startsWith('/org') &&
    auth.isLoggedIn &&
    auth.hasRole('mentor') &&
    !auth.hasRole('community_admin') &&
    !auth.hasRole('committee')
  ) {
    return { path: '/mentor' }
  }
  // 组织侧不进学生申请详情/列表
  if (
    auth.isLoggedIn &&
    auth.isStaff &&
    !auth.hasRole('committee') &&
    (to.path.startsWith('/student/') ||
      (to.path === '/me' && String(to.query.tab || '') === 'applications'))
  ) {
    return { path: auth.portalHome() }
  }
  if (to.meta.guest && auth.isLoggedIn) {
    if (to.meta.committeePortal) {
      if (auth.hasRole('committee')) return { path: '/committee' }
      return true
    }
    if (auth.hasRole('mentor') && !auth.hasRole('community_admin')) return { path: '/mentor' }
    if (auth.hasRole('community_admin')) return { path: '/org' }
    return { name: 'home' }
  }
  return true
})

export default router
