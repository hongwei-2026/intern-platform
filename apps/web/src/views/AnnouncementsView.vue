<script setup lang="ts">
import { onMounted, ref } from 'vue'
import api from '@/api/client'
import type { AnnouncementOut } from '@/api/types'

const list = ref<AnnouncementOut[]>([])
const error = ref('')
const loading = ref(true)

const typeLabel: Record<string, string> = {
  selection: '中选公示',
  final: '结项公示',
  general: '公告',
}

onMounted(async () => {
  try {
    const { data } = await api.get<AnnouncementOut[]>('/announcements')
    list.value = data
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : '加载失败'
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="page">
    <h1 class="page-title">公示公告</h1>
    <p class="page-desc">中选与结项结果在此公开，流程对齐开源之夏公示环节。</p>

    <p v-if="loading" class="muted">加载中…</p>
    <p v-else-if="error" class="error">{{ error }}</p>
    <div v-else-if="!list.length" class="card muted">暂无公示。</div>
    <div v-else class="stack">
      <article v-for="a in list" :key="a.id" class="card">
        <h3>{{ a.title }}</h3>
        <p class="muted">
          <span class="badge slate">{{ typeLabel[a.type] || a.type }}</span>
          <span v-if="a.published_at" style="margin-left: 0.5rem">{{ a.published_at }}</span>
        </p>
        <p v-if="a.body" style="white-space: pre-wrap; margin-top: 0.75rem">{{ a.body }}</p>
      </article>
    </div>
  </div>
</template>
