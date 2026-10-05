<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AuthShell from '@/components/AuthShell.vue'
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
    const user = await auth.login(email.value.trim(), password.value, 'ops')
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
  <AuthShell
    variant="committee"
    kicker="组委会通道"
    title="平台运维入口"
    :show-home="false"
    lead="此地址不对公开站点展示，登录后进入组委会工作台。"
    :points="['仅组委会账号可进入', '用于社区准入、结项名单与平台设置']"
  >
    <template #head>
      <h2>组委会登录</h2>
      <p>请使用组委会账号登录。</p>
    </template>

    <form @submit.prevent="onSubmit">
      <div class="field-block">
        <span class="block-label">账号登录</span>
        <label class="field">
          <span>邮箱</span>
          <input v-model="email" type="email" required autocomplete="username" placeholder="committee@…" />
        </label>
        <label class="field">
          <span>密码</span>
          <input v-model="password" type="password" required autocomplete="current-password" placeholder="请输入密码" />
        </label>
      </div>
      <p v-if="error" class="error">{{ error }}</p>
      <button class="submit-btn" type="submit" :disabled="auth.loading">
        {{ auth.loading ? '登录中…' : '登录' }}
      </button>
    </form>
  </AuthShell>
</template>
