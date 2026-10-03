<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
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

const kinds = [
  { id: 'all', label: '全部' },
  { id: 'news', label: '最新动态' },
  { id: 'general', label: '公告' },
  { id: 'selection', label: '中选公示' },
  { id: 'final', label: '结项公示' },
] as const

const kind = ref<(typeof kinds)[number]['id']>('all')
const kindName: Record<string, string> = {
  news: '最新动态',
  general: '公告',
  selection: '中选公示',
  final: '结项公示',
}

const fallback: Item[] = [
  {
    id: 'n-task3',
    date: '2026-03',
    title: '开源实习管理系统进入任务3联调',
    body: '完成 JWT 鉴权、社区/项目/三级审核与企业级流水，前端按华科官网风格改版。',
  },
  {
    id: 'n-flow',
    date: '2026-03',
    title: '实习全流程上线',
    body: '社区报名 → 项目发布 → 学生申请 → 三级审核 → 中选公示 → 结项审核，支持分社区申请字段。',
  },
  {
    id: 'n-club',
    date: '持续更新',
    title: '俱乐部动态请见官网',
    body: '新闻、百科、翻译团队与镜像站服务以俱乐部门户为准。',
    href: 'https://hust.openatom.club/',
  },
]

const items = ref<Item[]>(fallback)
const shown = computed(() => (kind.value === 'all' ? items.value : items.value.filter((item) => (item.kind || 'news') === kind.value)))
const page = ref(1)
const pageSize = 6
const pageCount = computed(() => Math.max(1, Math.ceil(shown.value.length / pageSize)))
const pageItems = computed(() => shown.value.slice((page.value - 1) * pageSize, page.value * pageSize))

watch(kind, () => {
  page.value = 1
})
watch(pageCount, (count) => {
  if (page.value > count) page.value = count
})

onMounted(async () => {
  try {
    const { data } = await api.get<Item[]>('/site/news')
    if (data.length) items.value = data.map((item) => ({ ...item, body: item.body || item.summary || '' }))
  } catch {
    /* 未发布时用现有动态 */
  }
})
</script>

<template>
  <div class="page wide news-page">
    <h1 class="page-title">最新动态</h1>
    <p class="page-desc">按类型查看。点开标题，进入这一条自己的页面。</p>
    <div class="kinds">
      <button v-for="item in kinds" :key="item.id" type="button" :class="{ on: kind === item.id }" @click="kind = item.id">{{ item.label }}</button>
    </div>
    <p v-if="!shown.length" class="empty">这一类还没有发布。</p>
    <div v-else class="news-scroll">
      <div class="news-grid">
        <article v-for="n in pageItems" :key="n.id || n.title" class="card">
          <p class="muted meta"><span>{{ kindName[n.kind || 'news'] }}</span>{{ n.date }}</p>
          <h3>
            <RouterLink class="title" :to="`/news/${n.id || encodeURIComponent(n.title)}`">{{ n.title }}</RouterLink>
          </h3>
          <p class="muted">{{ n.summary || n.body }}</p>
        </article>
      </div>
    </div>
    <div class="pager">
      <span>共 {{ shown.length }} 条 · 第 {{ page }} / {{ pageCount }} 页</span>
      <button type="button" :disabled="page <= 1" @click="page -= 1">上一页</button>
      <button type="button" :disabled="page >= pageCount" @click="page += 1">下一页</button>
    </div>
  </div>
</template>

<style scoped>
.news-page { width: 100%; }
.kinds { display: flex; flex-wrap: wrap; gap: 8px; margin: 0 0 14px; }
.kinds button { border: 1px solid #d0d7e2; background: #fff; color: #1e3a5f; border-radius: 999px; padding: 6px 14px; font: inherit; cursor: pointer; }
.kinds button.on { background: #1677ff; border-color: #1677ff; color: #fff; }
.empty { margin: 24px 0; color: #64748b; }
.meta { display: flex; gap: 10px; margin: 0 0 0.35rem; }
.meta span { color: #1677ff; }
.news-scroll { max-height: calc(100vh - 230px); overflow-y: scroll; padding-right: 6px; }
.news-scroll::-webkit-scrollbar { width: 10px; }
.news-scroll::-webkit-scrollbar-thumb { background: #c5d0e0; border-radius: 8px; }
.news-scroll::-webkit-scrollbar-track { background: #f4f7fb; }
.news-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.title { font-weight: 700; font-size: 1.15rem; color: #1e3a5f; text-decoration: none; }
.pager { display: flex; justify-content: flex-end; align-items: center; gap: 8px; margin-top: 12px; color: #64748b; }
.pager button { border: 1px solid #d9d9d9; background: #fff; border-radius: 6px; padding: 4px 10px; font: inherit; cursor: pointer; }
.pager button:disabled { color: #cbd5e1; cursor: default; }
@media (max-width: 800px) { .news-grid { grid-template-columns: 1fr; } }
</style>
