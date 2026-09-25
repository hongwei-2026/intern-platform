<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import api from '@/api/client'
import type { ApplicationOut } from '@/api/types'
import { nodeLabel, statusLabel, statusTone } from '@/utils/statusLabel'

const list = ref<ApplicationOut[]>([])
const error = ref('')
const loading = ref(true)

function statusHint(status: string) {
  if (status === 'community_review') return '导师已过，等社区'
  if (status === 'committee_review') return '等组委会终审'
  if (status === 'mentor_review' || status === 'submitted') return '等导师审设计'
  if (status === 'selected') return '已录取'
  if (status === 'in_progress') return '开发中'
  return ''
}

onMounted(async () => {
  try {
    const { data } = await api.get<ApplicationOut[]>('/applications/mine')
    list.value = data
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : '加载失败'
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="page apps-page">
    <header class="head">
      <div>
        <h1 class="page-title">我的申请</h1>
        <p class="muted">查看进度；未通过可回项目页再次申请。</p>
      </div>
      <RouterLink class="btn student sm" to="/projects">浏览项目</RouterLink>
    </header>

    <p v-if="loading" class="muted">加载中…</p>
    <p v-else-if="error" class="error">{{ error }}</p>
    <div v-else-if="!list.length" class="empty card">
      <p>还没有申请记录。</p>
      <RouterLink class="btn sm" to="/projects">去查看项目</RouterLink>
    </div>
    <div v-else class="app-list">
      <RouterLink
        v-for="a in list"
        :key="a.id"
        class="card app-row"
        :to="`/student/applications/${a.id}`"
      >
        <div class="app-main">
          <strong>{{ a.project_title || `项目 #${a.project_id}` }}</strong>
          <span class="muted"
            >申请 #{{ a.id }} · {{ statusHint(a.status) || nodeLabel(a.current_node) || '—' }}</span
          >
        </div>
        <span class="badge" :class="statusTone(a.status)">{{ statusLabel(a.status) }}</span>
        <span class="go">详情 →</span>
      </RouterLink>
    </div>
  </div>
</template>

<style scoped>
.apps-page {
  max-width: 920px;
}
.head {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
  margin-bottom: 1rem;
  align-items: flex-start;
}
.page-title {
  margin: 0;
}
.app-list {
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
}
.app-row {
  display: grid;
  grid-template-columns: 1fr auto auto;
  gap: 0.75rem 1rem;
  align-items: center;
  padding: 0.9rem 1.1rem;
  color: inherit;
  text-decoration: none;
}
.app-row:hover {
  border-color: #93c5fd;
  background: #f8fbff;
}
.app-main {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
  min-width: 0;
}
.app-main strong {
  font-size: 1rem;
}
.go {
  font-weight: 600;
  font-size: 0.85rem;
  color: #1d4ed8;
  white-space: nowrap;
}
.empty {
  text-align: center;
  padding: 2rem 1rem;
}
@media (max-width: 640px) {
  .app-row {
    grid-template-columns: 1fr auto;
  }
  .go {
    display: none;
  }
}
</style>
