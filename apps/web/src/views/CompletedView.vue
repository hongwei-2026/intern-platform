<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import api from '@/api/client'
import type { AnnouncementOut, ApplicationOut } from '@/api/types'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const list = ref<AnnouncementOut[]>([])
const mine = ref<ApplicationOut[]>([])
const error = ref('')
const loading = ref(true)
const period = ref<'recent' | 'earlier'>('recent')

const typeLabel: Record<string, string> = {
  selection: '中选公示',
  final: '结项公示',
  general: '公告',
}

type PubBlock = { id?: string; type?: string; text?: string; url?: string; rows?: string[][] }

function pubBlocks(body?: string | null): PubBlock[] | null {
  if (!body) return null
  try {
    const data = JSON.parse(body) as { blocks?: PubBlock[] }
    if (Array.isArray(data.blocks) && data.blocks.length) return data.blocks
  } catch {
    /* 旧公示是纯文字 */
  }
  return null
}

function yearOf(raw?: string | null) {
  if (!raw) return 0
  const y = Number(String(raw).slice(0, 4))
  return Number.isFinite(y) ? y : 0
}

const currentYear = new Date().getFullYear()

const filtered = computed(() =>
  list.value.filter((a) => {
    const y = yearOf(a.published_at)
    if (!y) return period.value === 'recent'
    return period.value === 'recent' ? y >= currentYear : y < currentYear
  }),
)

const myCompleted = computed(() => mine.value.filter((a) => a.status === 'completed'))

async function load() {
  loading.value = true
  error.value = ''
  try {
    const { data } = await api.get<AnnouncementOut[]>('/announcements')
    list.value = data
    if (auth.isLoggedIn && auth.canApplyProjects) {
      const { data: apps } = await api.get<ApplicationOut[]>('/applications/mine')
      mine.value = apps
    }
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : '加载失败'
  } finally {
    loading.value = false
  }
}

onMounted(load)
watch(() => auth.isLoggedIn, load)
</script>

<template>
  <div class="page">
    <h1 class="page-title">结项公示</h1>
    <p class="page-desc">
      导师同意结项后，组织把材料交给组委会。组委会在固定时间统一发布。发布后组织可关闭接取：项目仍可查看，但不能再报名。
    </p>

    <div class="tabs">
      <button type="button" :class="{ on: period === 'recent' }" @click="period = 'recent'">
        {{ currentYear }} 年
      </button>
      <button type="button" :class="{ on: period === 'earlier' }" @click="period = 'earlier'">
        往年结项
      </button>
    </div>

    <p v-if="loading" class="muted">加载中…</p>
    <p v-else-if="error" class="error">{{ error }}</p>
    <template v-else>
      <section v-if="auth.canApplyProjects" class="mine">
        <h2>我结项的项目</h2>
        <p v-if="!myCompleted.length" class="muted">你还没有已结项的项目。</p>
        <ul v-else>
          <li v-for="a in myCompleted" :key="a.id">
            <RouterLink :to="`/student/applications/${a.id}?tab=task`">
              {{ a.project_title || `项目 #${a.project_id}` }}
            </RouterLink>
            <span>申请 #{{ a.id }}</span>
          </li>
        </ul>
      </section>

      <div v-if="!filtered.length" class="card muted">这个时间段还没有公示。</div>
      <div v-else class="stack">
        <article v-for="a in filtered" :key="a.id" class="card">
          <h3>{{ a.title }}</h3>
          <p class="muted">
            <span class="badge slate">{{ typeLabel[a.type] || a.type }}</span>
            <span v-if="a.published_at" style="margin-left: 0.5rem">{{ a.published_at }}</span>
          </p>
          <div v-if="pubBlocks(a.body)" class="pub-body">
            <template v-for="(block, i) in pubBlocks(a.body)" :key="block.id || i">
              <p v-if="!block.type || block.type === 'text'">{{ block.text }}</p>
              <img v-else-if="block.type === 'image' && block.url" :src="block.url" alt="" />
              <table v-else-if="block.type === 'table'" class="pub-table">
                <tr v-for="(row, ri) in block.rows" :key="ri"><td v-for="(cell, ci) in row" :key="ci">{{ cell }}</td></tr>
              </table>
              <video v-else-if="block.url" :src="block.url" controls />
            </template>
          </div>
          <p v-else-if="a.body" style="white-space: pre-wrap; margin-top: 0.75rem">{{ a.body }}</p>
        </article>
      </div>
    </template>
  </div>
</template>

<style scoped>
.tabs { display: flex; gap: 8px; margin: 0 0 1rem; }
.tabs button {
  border: 1px solid #d9d9d9;
  background: #fff;
  border-radius: 999px;
  padding: 0.3rem 0.85rem;
  cursor: pointer;
  font: inherit;
}
.tabs button.on { background: #0b3d91; color: #fff; border-color: #0b3d91; }
.mine {
  background: #fff;
  border: 1px solid #e8ebf0;
  border-radius: 10px;
  padding: 1rem 1.1rem;
  margin-bottom: 1rem;
}
.mine h2 { margin: 0 0 0.6rem; font-size: 1rem; }
.mine ul { list-style: none; margin: 0; padding: 0; }
.mine li { display: flex; justify-content: space-between; gap: 1rem; padding: 0.4rem 0; }
.mine span { color: #8c8c8c; font-size: 0.85rem; }
.pub-table { width: 100%; border-collapse: collapse; margin: 0.75rem 0; }
.pub-table td { border: 1px solid #d0d7e2; padding: 6px 8px; }
.pub-body p { white-space: pre-wrap; margin: 0.75rem 0 0; }
.pub-body img, .pub-body video { display: block; width: min(100%, 720px); border-radius: 12px; margin: 0.75rem 0; }
</style>
