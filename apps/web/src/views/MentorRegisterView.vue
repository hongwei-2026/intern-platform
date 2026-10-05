<script setup lang="ts">
import { ref } from 'vue'
import { useRouter, RouterLink } from 'vue-router'
import AuthShell from '@/components/AuthShell.vue'
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
  <AuthShell
    variant="mentor"
    title="导师通道"
    lead="用社区邀请码完成注册，自动加入对应社区并进入导师工作台。"
    :points="['邀请码由社区管理员私下发放', '不会出现在学生可见页面']"
  >
    <template #head>
      <h2>导师注册</h2>
      <p>请向社区管理员索取邀请码后再填写资料。</p>
    </template>

    <form @submit.prevent="onSubmit">
      <div class="field-block">
        <span class="block-label">1 · 邀请码</span>
        <label class="field">
          <span>导师邀请码</span>
          <input
            v-model="inviteCode"
            required
            minlength="4"
            placeholder="由社区管理员私下提供"
            style="text-transform: uppercase"
            autocomplete="off"
          />
        </label>
      </div>

      <div class="field-block">
        <span class="block-label">2 · 账号资料</span>
        <label class="field">
          <span>邮箱</span>
          <input v-model="email" type="email" required autocomplete="username" placeholder="name@hust.edu.cn" />
        </label>
        <label class="field">
          <span>显示名称</span>
          <input v-model="displayName" type="text" required placeholder="将展示给学生与组织" />
        </label>
        <label class="field">
          <span>密码</span>
          <input
            v-model="password"
            type="password"
            required
            minlength="6"
            autocomplete="new-password"
            placeholder="至少 6 位"
          />
        </label>
      </div>

      <p v-if="error" class="error">{{ error }}</p>
      <button class="submit-btn" type="submit" :disabled="auth.loading">
        {{ auth.loading ? '提交中…' : '注册并进入导师工作台' }}
      </button>
    </form>

    <template #foot>
      已有账号？
      <RouterLink to="/login?role=mentor">导师登录</RouterLink>
      <span class="sep">·</span>
      <RouterLink to="/register">学生注册</RouterLink>
    </template>
  </AuthShell>
</template>
