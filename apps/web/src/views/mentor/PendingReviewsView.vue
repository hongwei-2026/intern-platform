<script setup lang="ts">
import { ref } from 'vue'
import { RouterLink } from 'vue-router'
import api from '@/api/client'
import type { ApplicationOut, ReviewResponse } from '@/api/types'
import ReviewTimeline from '@/components/ReviewTimeline.vue'

const applicationId = ref('')
const app = ref<ApplicationOut | null>(null)
const comment = ref('')
const error = ref('')
const msg = ref('')
const busy = ref(false)

async function loadApp() {
  error.value = ''
  msg.value = ''
  app.value = null
  const id = Number(applicationId.value)
  if (!id) {
    error.value = '请输入申请 ID'
    return
  }
  try {
    const { data } = await api.get<ApplicationOut>(`/applications/${id}`)
    app.value = data
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : '加载失败'
  }
}

async function decide(decision: 'approve' | 'reject') {
  if (!app.value) return
  busy.value = true
  error.value = ''
  msg.value = ''
  try {
    const { data } = await api.post<ReviewResponse>(
      `/applications/${app.value.id}/reviews`,
      {
        decision,
        comment: comment.value || null,
        version: app.value.version,
      },
    )
    msg.value = `${decision === 'approve' ? '已通过' : '已拒绝'}：${data.from_status} → ${data.to_status}`
    await loadApp()
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : '审核失败'
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="page">
    <h1 class="page-title">导师 · 待审申请</h1>
    <p class="muted">
      后端暂无待审列表接口。请输入申请 ID 加载详情后进行通过/拒绝。
      <RouterLink to="/mentor/projects">我的项目</RouterLink>
    </p>

    <form class="form" @submit.prevent="loadApp">
      <label>
        申请 ID
        <input v-model="applicationId" type="number" min="1" required />
      </label>
      <button class="btn" type="submit">加载</button>
    </form>

    <p v-if="error" class="error">{{ error }}</p>
    <p v-if="msg" class="success-msg">{{ msg }}</p>

    <template v-if="app">
      <div class="card" style="margin-top: 1rem">
        <h3>申请 #{{ app.id }}</h3>
        <p class="muted">项目 {{ app.project_id }} · 学生 {{ app.student_id }}</p>
        <p v-if="app.statement" style="white-space: pre-wrap">{{ app.statement }}</p>
      </div>
      <ReviewTimeline :application="app" />
      <form class="form" @submit.prevent>
        <label>
          审核意见
          <textarea v-model="comment" />
        </label>
        <div class="btn-row">
          <button class="btn success" type="button" :disabled="busy" @click="decide('approve')">
            通过
          </button>
          <button class="btn danger" type="button" :disabled="busy" @click="decide('reject')">
            拒绝
          </button>
        </div>
      </form>
    </template>
  </div>
</template>
