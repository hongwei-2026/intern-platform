<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter, RouterLink } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

type Portal = 'student' | 'mentor' | 'org'
const portal = ref<Portal>('student')
const email = ref('')
const password = ref('')
const error = ref('')

watch(
  () => route.query.role,
  (v) => {
    if (v === 'mentor' || v === 'org' || v === 'student') portal.value = v
    else portal.value = 'student'
  },
  { immediate: true },
)

const title = computed(() => {
  if (portal.value === 'mentor') return '导师登录'
  if (portal.value === 'org') return '组织登录'
  return '学生登录'
})

const hint = computed(() => {
  if (portal.value === 'mentor') return '登录后进入导师工作台。新导师请使用邀请码注册加入社区。'
  if (portal.value === 'org') return '社区管理员：维护主页、邀请导师、创建并分配项目。'
  return '学生登录后可浏览项目、提交申请并跟踪三级审核进度。'
})

onMounted(() => {
  const notice = sessionStorage.getItem('intern_platform_auth_notice')
  if (!notice) return
  error.value = notice
  sessionStorage.removeItem('intern_platform_auth_notice')
})

function setPortal(p: Portal) {
  portal.value = p
  router.replace({ query: { ...route.query, role: p } })
}

async function onSubmit() {
  error.value = ''
  try {
    await auth.login(email.value.trim(), password.value)
    // 导师账号一律进导师台，绝不落到组织工作台
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
      // 组织侧不应被带到学生申请相关页
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
  <div class="page narrow">
    <div class="auth-panel">
      <div class="auth-tabs triple">
        <button
          type="button"
          class="auth-tab student"
          :class="{ active: portal === 'student' }"
          @click="setPortal('student')"
        >
          学生
        </button>
        <button
          type="button"
          class="auth-tab mentor"
          :class="{ active: portal === 'mentor' }"
          @click="setPortal('mentor')"
        >
          导师
        </button>
        <button
          type="button"
          class="auth-tab org"
          :class="{ active: portal === 'org' }"
          @click="setPortal('org')"
        >
          组织
        </button>
      </div>

      <h1 class="page-title" style="font-size: 1.35rem">{{ title }}</h1>
      <p class="page-desc">{{ hint }}</p>

      <form class="form" @submit.prevent="onSubmit">
        <label>
          邮箱
          <input
            v-model="email"
            type="email"
            required
            autocomplete="username"
            placeholder="name@hust.edu.cn"
          />
        </label>
        <label>
          密码
          <input
            v-model="password"
            type="password"
            required
            autocomplete="current-password"
            placeholder="请输入密码"
          />
        </label>
        <p v-if="error" class="error">{{ error }}</p>
        <button
          class="btn"
          :class="portal === 'student' ? 'student' : 'org'"
          type="submit"
          :disabled="auth.loading"
          style="width: 100%; border-radius: 999px"
        >
          {{ auth.loading ? '登录中…' : '登录' }}
        </button>
      </form>

      <p class="muted" style="margin-top: 0.75rem">
        <template v-if="portal === 'mentor'">
          新导师？
          <RouterLink to="/register/mentor">使用邀请码注册</RouterLink>
        </template>
        <template v-else-if="portal === 'student'">
          <RouterLink to="/register">注册学生账号</RouterLink>
        </template>
        <template v-else>组织账号由组委会开通</template>
      </p>
    </div>
  </div>
</template>

<style scoped>
.auth-tabs.triple {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
}
.auth-tab.mentor.active {
  background: #ea580c;
  color: #fff;
}
</style>
