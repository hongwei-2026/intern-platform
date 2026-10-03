<script setup lang="ts">
import { ref } from 'vue'
import { useRouter, RouterLink } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()

const email = ref('')
const password = ref('')
const displayName = ref('')
const school = ref('')
const error = ref('')

async function onSubmit() {
  error.value = ''
  try {
    await auth.register({
      email: email.value.trim(),
      password: password.value,
      display_name: displayName.value.trim(),
      school: school.value.trim() || undefined,
    })
    router.push('/me')
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : '注册失败'
  }
}
</script>

<template>
  <div class="page narrow">
    <div class="auth-panel">
      <h1 class="page-title" style="font-size: 1.35rem">注册学生账号</h1>
      <p class="page-desc">注册后为学生。导师请使用社区发放的邀请码注册，组织账号由组委会开通。</p>
      <form class="form" @submit.prevent="onSubmit">
        <label>
          邮箱
          <input v-model="email" type="email" required autocomplete="username" />
        </label>
        <label>
          显示名称
          <input v-model="displayName" type="text" required />
        </label>
        <label>
          学校（可选）
          <input v-model="school" type="text" placeholder="华中科技大学" />
        </label>
        <label>
          密码（至少 6 位）
          <input v-model="password" type="password" required minlength="6" autocomplete="new-password" />
        </label>
        <p v-if="error" class="error">{{ error }}</p>
        <button class="btn student" type="submit" :disabled="auth.loading" style="width: 100%">
          {{ auth.loading ? '提交中…' : '注册并登录' }}
        </button>
      </form>
      <p class="muted" style="margin-top: 1rem">
        已有账号？
        <RouterLink to="/login?role=student">学生登录</RouterLink>
        ·
        <RouterLink to="/login?role=org">组织登录</RouterLink>
      </p>
    </div>
  </div>
</template>
