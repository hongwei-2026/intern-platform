<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'
import NotificationBell from '@/components/NotificationBell.vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

const isHome = computed(() => route.path === '/')
const isOpsLogin = computed(() => route.path.startsWith('/ops/login'))
const isCommitteeArea = computed(() => route.path.startsWith('/committee'))
const menuOpen = ref(false)
const menuRoot = ref<HTMLElement | null>(null)

function logout() {
  menuOpen.value = false
  const toOps = isOpsLogin.value || isCommitteeArea.value
  auth.logout()
  router.push(toOps ? '/ops/login' : '/')
}

function toggleMenu() {
  menuOpen.value = !menuOpen.value
}

function onDocClick(e: MouseEvent) {
  if (!menuOpen.value) return
  const el = menuRoot.value
  if (el && !el.contains(e.target as Node)) menuOpen.value = false
}

onMounted(() => document.addEventListener('click', onDocClick))
onUnmounted(() => document.removeEventListener('click', onDocClick))

watch(
  () => route.fullPath,
  () => {
    menuOpen.value = false
  },
)

const avatarText = computed(() => (auth.displayName || '?').slice(0, 1))
</script>

<template>
  <div class="site">
    <header class="topnav">
      <div class="topnav-inner">
        <RouterLink class="brand" :to="isCommitteeArea || isOpsLogin ? '/committee' : '/'">
          <span class="brand-mark" aria-hidden="true">
            <img src="/logos/penguin-blue.svg" alt="" />
          </span>
          <span class="brand-text">
            <strong>华科开源原子</strong>
            <span>{{ isCommitteeArea || isOpsLogin ? '组委会通道' : '开源实习管理系统' }}</span>
          </span>
        </RouterLink>

        <nav v-if="isCommitteeArea && auth.hasRole('committee')" class="topnav-links" aria-label="组委会导航">
          <RouterLink to="/committee">工作台</RouterLink>
          <RouterLink to="/committee/oauth">开通账号绑定</RouterLink>
        </nav>
        <nav v-else-if="!isOpsLogin && !isCommitteeArea" class="topnav-links" aria-label="主导航">
          <RouterLink
            v-if="auth.isLoggedIn && auth.isMentor"
            class="nav-workbench"
            to="/mentor"
          >导师工作台</RouterLink>
          <RouterLink
            v-if="auth.isLoggedIn && (auth.isCommunityAdmin || auth.hasRole('committee')) && !auth.isMentor"
            class="nav-workbench org"
            to="/org"
          >组织工作台</RouterLink>
          <RouterLink to="/">首页</RouterLink>
          <RouterLink v-if="!auth.isLoggedIn || auth.canApplyProjects" to="/projects">查看项目</RouterLink>
          <RouterLink to="/completed">结项公示</RouterLink>
          <RouterLink to="/news">最新动态</RouterLink>
          <RouterLink to="/guide">参与指南</RouterLink>
        </nav>

        <div class="nav-actions">
          <template v-if="auth.isLoggedIn && auth.hasRole('committee') && (isCommitteeArea || isOpsLogin)">
            <span class="user-chip-name" style="margin-right: 8px">{{ auth.displayName }}</span>
            <button class="btn sm secondary" type="button" @click="logout">退出</button>
          </template>
          <template v-else-if="auth.isLoggedIn && !isOpsLogin && !isCommitteeArea">
            <NotificationBell />
            <div ref="menuRoot" class="user-menu">
              <button
                class="user-chip"
                type="button"
                aria-haspopup="true"
                :aria-expanded="menuOpen"
                @click.stop="toggleMenu"
              >
                <span class="user-chip-avatar">{{ avatarText }}</span>
                <span class="user-chip-name">{{ auth.displayName }}</span>
                <span class="user-chip-caret">▾</span>
              </button>
              <div v-show="menuOpen" class="user-dropdown" role="menu">
                <RouterLink role="menuitem" to="/me" @click="menuOpen = false">个人中心</RouterLink>
                <RouterLink role="menuitem" to="/me?tab=bindings" @click="menuOpen = false">平台绑定</RouterLink>
                <RouterLink role="menuitem" to="/me?tab=password" @click="menuOpen = false">修改密码</RouterLink>
                <RouterLink
                  v-if="auth.canApplyProjects"
                  role="menuitem"
                  to="/me?tab=applications"
                  @click="menuOpen = false"
                >我的申请</RouterLink>
                <RouterLink
                  v-if="auth.isMentor"
                  role="menuitem"
                  to="/mentor"
                  @click="menuOpen = false"
                >导师工作台</RouterLink>
                <RouterLink
                  v-if="auth.isCommunityAdmin || auth.hasRole('committee')"
                  role="menuitem"
                  to="/org"
                  @click="menuOpen = false"
                >组织工作台</RouterLink>
                <button role="menuitem" type="button" class="user-dropdown-logout" @click="logout">退出登录</button>
              </div>
            </div>
          </template>
          <template v-else-if="!isOpsLogin && !isCommitteeArea">
            <RouterLink class="btn student sm" to="/login?role=student">学生登录</RouterLink>
            <RouterLink class="btn secondary sm" to="/login?role=mentor">导师登录</RouterLink>
            <RouterLink class="btn secondary sm" to="/login?role=org">组织登录</RouterLink>
          </template>
        </div>
      </div>
    </header>

    <main class="site-main" :class="{ 'is-home': isHome }">
      <RouterView />
    </main>

    <footer v-if="!isOpsLogin" class="site-footer">
      <div class="footer-inner">
        <div>
          <strong>华科开放原子开源俱乐部 · 开源实习</strong>
          <span>服务俱乐部多社区运营与开源贡献管理</span>
        </div>
        <div class="stack" style="gap: 0.35rem">
          <RouterLink to="/guide">参与指南</RouterLink>
          <RouterLink to="/news">最新动态</RouterLink>
          <a href="https://hust.openatom.club/" target="_blank" rel="noopener">俱乐部官网</a>
        </div>
      </div>
    </footer>
  </div>
</template>
