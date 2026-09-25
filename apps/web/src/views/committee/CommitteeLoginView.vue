<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

const email = ref('')
const password = ref('')
const error = ref('')

async function onSubmit() {
  error.value = ''
  try {
    const user = await auth.login(email.value.trim(), password.value)
    const roles = user.roles?.map((r) => r.code) ?? []
    if (!roles.includes('committee')) {
      auth.logout()
      error.value = '该账号无组委会权限'
      return
    }
    const redirect = (route.query.redirect as string) || '/committee'
    await router.replace(redirect.startsWith('/committee') ? redirect : '/committee')
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : '登录失败'
  }
}
</script>

<template>
  <div class="page narrow">
    <div class="auth-panel">
      <h1 class="page-title" style="font-size: 1.35rem">组委会登录</h1>
      <p class="page-desc">此地址不对公开站点展示，登录后进入组委会工作台。</p>

      <form class="form" @submit.prevent="onSubmit">
        <label>
          邮箱
          <input v-model="email" type="email" required autocomplete="username" placeholder="committee@…" />
        </label>
        <label>
          密码
          <input v-model="password" type="password" required autocomplete="current-password" />
        </label>
        <p v-if="error" class="error">{{ error }}</p>
        <button class="btn" type="submit" :disabled="auth.loading" style="width: 100%; border-radius: 999px">
          {{ auth.loading ? '登录中…' : '登录' }}
        </button>
      </form>
    </div>
  </div>
</template>
