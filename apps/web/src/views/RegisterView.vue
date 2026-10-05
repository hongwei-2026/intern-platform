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
  <AuthShell
    variant="student"
    title="加入开源实习"
    lead="用真实仓库完成贡献，走完申请、审核与结项全链路。"
    :points="['邮箱注册后即可报名课题', '导师 / 组织入口另行开通']"
  >
    <template #head>
      <h2>注册学生账号</h2>
      <p>填写邮箱与密码即可注册。导师请用邀请码注册。</p>
    </template>

    <form @submit.prevent="onSubmit">
      <div class="field-block">
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
            minlength="6"
            autocomplete="new-password"
            placeholder="至少 6 位"
          />
        </label>
        <label class="field">
          <span>显示名称</span>
          <input v-model="displayName" type="text" required placeholder="怎么称呼你" />
        </label>
        <label class="field">
          <span>学校（可选）</span>
          <input v-model="school" type="text" placeholder="华中科技大学" />
        </label>
      </div>

      <p v-if="error" class="error">{{ error }}</p>
      <button class="submit-btn" type="submit" :disabled="auth.loading">
        {{ auth.loading ? '提交中…' : '注册并登录' }}
      </button>
    </form>

    <template #foot>
      已有账号？
      <RouterLink to="/login?role=student">去登录</RouterLink>
      <span class="sep">·</span>
      <RouterLink to="/register/mentor">导师邀请码注册</RouterLink>
    </template>
  </AuthShell>
</template>
