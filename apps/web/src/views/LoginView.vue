<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter, RouterLink } from 'vue-router'
import AuthShell from '@/components/AuthShell.vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

type Portal = 'student' | 'mentor' | 'org'
const portal = ref<Portal | null>(null)
const email = ref('')
const password = ref('')
const error = ref('')

watch(
  () => route.query.role,
  (v) => {
    if (v === 'mentor' || v === 'org' || v === 'student') portal.value = v
    else portal.value = null
  },
  { immediate: true },
)

const choosing = computed(() => portal.value === null)

const shellVariant = computed(() => portal.value || 'student')

const brandTitle = computed(() => {
  if (choosing.value) return '欢迎回来'
  if (portal.value === 'mentor') return '导师工作台'
  if (portal.value === 'org') return '组织工作台'
  return '学生入口'
})

const brandLead = computed(() => {
  if (choosing.value) return '先选择身份，再进入对应登录页。账号体系统一，入口分开。'
  if (portal.value === 'mentor') return '管理课题、审核申请与结项材料。'
  if (portal.value === 'org') return '维护社区主页、邀请导师、创建并分配项目。'
  return '浏览项目、提交申请，跟踪三级审核与结项进度。'
})

const brandPoints = computed(() => {
  if (choosing.value) return ['学生可自助注册', '导师需邀请码，组织由组委会开通']
  if (portal.value === 'mentor') return ['使用社区发放的邀请码注册', '登录后进入导师工作台']
  if (portal.value === 'org') return ['组织账号由组委会开通', '登录后进入组织工作台']
  return ['没有账号可先注册', '邮箱 + 密码即可注册']
})

const formTitle = computed(() => {
  if (portal.value === 'mentor') return '导师登录'
  if (portal.value === 'org') return '组织登录'
  return '学生登录'
})

const formHint = computed(() => {
  if (portal.value === 'mentor') return '登录后进入导师工作台。新导师请使用邀请码注册。'
  if (portal.value === 'org') return '社区管理员入口。账号由组委会开通。'
  return '登录后可浏览项目、提交申请并跟踪审核进度。'
})

onMounted(() => {
  const notice = sessionStorage.getItem('intern_platform_auth_notice')
  if (!notice) return
  error.value = notice
  sessionStorage.removeItem('intern_platform_auth_notice')
})

function choosePortal(p: Portal) {
  portal.value = p
  error.value = ''
  router.replace({ query: { ...route.query, role: p } })
}

function backToChoose() {
  portal.value = null
  error.value = ''
  const q = { ...route.query } as Record<string, string | string[]>
  delete q.role
  router.replace({ query: q })
}

async function onSubmit() {
  error.value = ''
  try {
    await auth.login(email.value.trim(), password.value)
    if (auth.hasRole('mentor') && !auth.hasRole('community_admin')) {
      router.push('/mentor')
      return
    }
    const redirect = route.query.redirect as string | undefined
    if (redirect && redirect.startsWith('/') && !redirect.startsWith('//')) {
      if (redirect.startsWith('/org') && auth.hasRole('mentor') && !auth.hasRole('community_admin')) {
        router.push('/mentor')
        return
      }
      if (auth.isStaff && (redirect.includes('/student/') || redirect.includes('tab=applications'))) {
        router.push(auth.portalHome())
        return
      }
      router.push(redirect)
      return
    }
    router.push(auth.portalHome())
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : '登录失败'
  }
}
</script>

<template>
  <AuthShell
    :variant="shellVariant"
    :title="brandTitle"
    :lead="brandLead"
    :points="brandPoints"
  >
    <template #head>
      <h2>{{ choosing ? '选择账户类型' : formTitle }}</h2>
      <p>{{ choosing ? '请先选择身份，再进入对应登录页。' : formHint }}</p>
    </template>

    <div v-if="choosing">
      <div class="role-grid">
        <button type="button" class="role-card" @click="choosePortal('student')">
          <strong>学生</strong>
          <span>浏览项目、提交申请、跟踪审核与结项</span>
        </button>
        <button type="button" class="role-card" @click="choosePortal('mentor')">
          <strong>导师</strong>
          <span>管理课题、审核申请与结项材料</span>
        </button>
        <button type="button" class="role-card" @click="choosePortal('org')">
          <strong>组织</strong>
          <span>社区管理员维护主页、邀请导师、分配项目</span>
        </button>
      </div>
    </div>

    <form v-else @submit.prevent="onSubmit">
      <button type="button" class="back-choose" @click="backToChoose">← 重新选择账户类型</button>

      <div class="field-block">
        <span class="block-label">账号登录</span>
        <label class="field">
          <span>邮箱</span>
          <input
            v-model="email"
            type="email"
            required
            autocomplete="username"
            placeholder="name@hust.edu.cn"
          />
        </label>
        <label class="field">
          <span>密码</span>
          <input
            v-model="password"
            type="password"
            required
            autocomplete="current-password"
            placeholder="请输入密码"
          />
        </label>
      </div>

      <p v-if="error" class="error">{{ error }}</p>

      <div class="auth-actions">
        <button class="submit-btn" type="submit" :disabled="auth.loading">
          {{ auth.loading ? '登录中…' : '登录' }}
        </button>
        <RouterLink v-if="portal === 'student'" class="ghost-btn" to="/register">注册</RouterLink>
        <RouterLink v-else-if="portal === 'mentor'" class="ghost-btn" to="/register/mentor">邀请码注册</RouterLink>
      </div>
    </form>

    <template v-if="!choosing" #foot>
      <template v-if="portal === 'org'">组织账号由组委会开通，无需自行注册</template>
      <template v-else-if="portal === 'student'">
        还没有账号？
        <RouterLink to="/register">立即注册</RouterLink>
      </template>
      <template v-else>
        新导师？
        <RouterLink to="/register/mentor">使用邀请码注册</RouterLink>
      </template>
    </template>
  </AuthShell>
</template>
