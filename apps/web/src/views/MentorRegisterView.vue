<script setup lang="ts">
import { ref } from 'vue'
import { useRouter, RouterLink } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()

const email = ref('')
const password = ref('')
const displayName = ref('')
const inviteCode = ref('')
const error = ref('')

async function onSubmit() {
  error.value = ''
  try {
    await auth.registerMentor({
      email: email.value.trim(),
      password: password.value,
      display_name: displayName.value.trim(),
      invite_code: inviteCode.value.trim().toUpperCase(),
    })
    router.push('/mentor')
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : '注册失败'
  }
}
</script>

<template>
  <div class="page narrow">
    <div class="auth-panel mentor-reg">
      <p class="kicker">导师通道</p>
      <h1 class="page-title" style="font-size: 1.35rem">导师注册</h1>
      <p class="page-desc">
        请向社区管理员索取<strong>导师邀请码</strong>（私下发放，不会出现在学生可见页面）。填写后自动加入对应社区。
      </p>
      <form class="form" @submit.prevent="onSubmit">
        <label>
          导师邀请码 <span class="req">*</span>
          <input
            v-model="inviteCode"
            required
            minlength="4"
            placeholder="由社区管理员私下提供"
            style="text-transform: uppercase"
            autocomplete="off"
          />
        </label>
        <label>
          邮箱 <span class="req">*</span>
          <input v-model="email" type="email" required autocomplete="username" />
        </label>
        <label>
          显示名称 <span class="req">*</span>
          <input v-model="displayName" type="text" required placeholder="将展示给学生与组织" />
        </label>
        <label>
          密码（至少 6 位） <span class="req">*</span>
          <input v-model="password" type="password" required minlength="6" autocomplete="new-password" />
        </label>
        <p v-if="error" class="error">{{ error }}</p>
        <button class="btn" type="submit" :disabled="auth.loading" style="width: 100%">
          {{ auth.loading ? '提交中…' : '注册并进入导师工作台' }}
        </button>
      </form>
      <p class="muted" style="margin-top: 1rem">
        已有账号？
        <RouterLink to="/login?role=mentor">导师登录</RouterLink>
        ·
        <RouterLink to="/register">学生注册</RouterLink>
      </p>
    </div>
  </div>
</template>

<style scoped>
.mentor-reg .kicker {
  margin: 0 0 0.35rem;
  font-size: 0.78rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  color: #1d4ed8;
}
.req {
  color: #dc2626;
}
</style>
