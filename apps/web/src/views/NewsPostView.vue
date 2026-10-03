<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import api from '@/api/client'

type Block = { id?: string; type?: 'text' | 'image' | 'video' | 'table'; text?: string; url?: string; rows?: string[][] }
type Item = {
  id?: string
  date: string
  title: string
  summary?: string
  body: string
  href?: string
  kind?: 'news' | 'general' | 'selection' | 'final'
  blocks?: Block[]
}

const route = useRoute()
const item = ref<Item | null>(null)
const missing = ref(false)

const kindName = computed(() => {
  const name: Record<string, string> = { news: '最新动态', general: '公告', selection: '中选公示', final: '结项公示' }
  return name[item.value?.kind || 'news'] || '最新动态'
})

const blocks = computed(() => {
  const current = item.value
  if (!current) return []
  if (current.blocks?.length) return current.blocks
  return [{ type: 'text' as const, text: current.body || current.summary || '' }]
})

onMounted(async () => {
  const id = String(route.params.id || '')
  try {
    const { data } = await api.get<Item[]>('/site/news')
    const hit = data.find((row) => row.id === id || row.title === decodeURIComponent(id))
    if (!hit) missing.value = true
    else item.value = { ...hit, body: hit.body || hit.summary || '' }
  } catch {
    missing.value = true
  }
})
</script>

<template>
  <div class="page wide post">
    <RouterLink class="back" to="/news">← 最新动态</RouterLink>
    <p v-if="missing" class="muted">这条动态不存在，或还没有发布。</p>
    <article v-else-if="item" class="sheet">
      <p class="muted">{{ kindName }}<template v-if="item.date"> · {{ item.date }}</template></p>
      <h1>{{ item.title }}</h1>
      <template v-for="(block, i) in blocks" :key="block.id || i">
        <p v-if="!block.type || block.type === 'text'">{{ block.text }}</p>
        <img v-else-if="block.type === 'image' && block.url" :src="block.url" alt="" />
        <table v-else-if="block.type === 'table'">
          <tr v-for="(row, ri) in block.rows" :key="ri"><td v-for="(cell, ci) in row" :key="ci">{{ cell }}</td></tr>
        </table>
        <video v-else-if="block.url" :src="block.url" controls />
      </template>
      <p v-if="item.href"><a :href="item.href" target="_blank" rel="noopener">前往相关页面 →</a></p>
    </article>
  </div>
</template>

<style scoped>
.post { width: 100%; }
.sheet { width: 100%; }
.back { color: #1677ff; text-decoration: none; font-size: 0.92rem; }
h1 { margin: 0.4rem 0 1rem; color: #1e3a5f; font-size: 1.8rem; line-height: 1.35; }
p { line-height: 1.85; white-space: pre-wrap; }
img, video { display: block; width: 100%; max-height: 420px; object-fit: contain; border-radius: 12px; margin: 12px 0; background: #f7f9fc; }
table { width: 100%; border-collapse: collapse; margin: 12px 0; }
td { border: 1px solid #d0d7e2; padding: 8px 10px; }
</style>
