<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import api from '@/api/client'

const index = ref(0)
let timer: number | undefined

const defaultSlides = [
  {
    id: 'intern',
    titleHtml: '华科开源原子<br />开源实习管理系统',
    lead:
      '华中科技大学开放原子开源俱乐部面向真实运营场景：社区报名、项目发布、学生申请、三级审核、中选与结项公示——让开源贡献可组织、可追溯。',
    meta: '活动流程全年可演示 · 企业级审核流水',
    image:
      'https://images.unsplash.com/photo-1500530855697-b586d89ba3ee?auto=format&fit=crop&w=1800&q=80',
    primary: { to: '/projects', label: '查看项目' },
    secondary: { to: '/guide', label: '参与指南' },
  },
  {
    id: 'process',
    titleHtml: '打通实习全链路<br />从申请到结项',
    lead:
      '完整流程可演示：组织报名与审核 → 发布项目 → 学生申请及审核 → 中选 → 项目开发 → 结项审核（导师 + 组委会）→ 结项公示。',
    meta: '统一登录入口 · 分角色进入 · 公示透明',
    image:
      'https://images.unsplash.com/photo-1522071820081-009f0129c71c?auto=format&fit=crop&w=1800&q=80',
    primary: { to: '/guide#sec-flow', label: '阅读完整指南' },
    secondary: { to: '/projects?tab=orgs', label: '按社区选择' },
  },
  {
    id: 'club',
    titleHtml: '连接俱乐部基础设施<br />镜像 · 代码仓 · 文档',
    lead:
      '不重复造轮子：项目仓库与结项合并请求对接校内代码仓，门户聚合镜像站与公开文档，成员加入仍遵循俱乐部协作与信息表流程。',
    meta: '薄集成 · 厚运营 · 可切换数据库',
    image:
      'https://images.unsplash.com/photo-1451187580459-43490279c0fa?auto=format&fit=crop&w=1800&q=80',
    primary: { to: '/guide#sec-faq', label: '注意事项 FAQ' },
    secondary: { to: '/news', label: '最新动态' },
  },
]

function go(i: number) {
  const n = slides.value.length
  index.value = ((i % n) + n) % n
}

function next() {
  go(index.value + 1)
}

function prev() {
  go(index.value - 1)
}

function start() {
  stop()
  timer = window.setInterval(next, 6000)
}

function stop() {
  if (timer !== undefined) {
    window.clearInterval(timer)
    timer = undefined
  }
}

type RemoteSlide = {
  id: string
  title?: string
  lead?: string
  meta?: string
  image?: string
  live?: boolean
  jump?: 'page' | 'link'
  link?: string
  pageTitle?: string
  pageBody?: string
  buttonLabel?: string
  primaryTo?: string
  primaryLabel?: string
  secondaryTo?: string
  secondaryLabel?: string
}

function fromRemote(item: RemoteSlide) {
  const jump = item.jump || (item.pageTitle || item.pageBody ? 'page' : 'link')
  const href = jump === 'page' ? `/banner/${item.id}` : item.link || item.primaryTo || '/projects'
  const secondaryTo = item.secondaryTo || ''
  return {
    id: item.id,
    titleHtml: (item.title || '').replace(/\n/g, '<br />'),
    lead: item.lead || '',
    meta: item.meta || '',
    image: item.image || defaultSlides[0].image,
    href,
    external: href.startsWith('http'),
    buttonLabel: item.buttonLabel || item.primaryLabel || (jump === 'page' ? '了解这次活动' : '前往'),
    primary: {
      to: href,
      label: item.buttonLabel || item.primaryLabel || (jump === 'page' ? '了解这次活动' : '前往'),
    },
    secondary: secondaryTo
      ? { to: secondaryTo, label: item.secondaryLabel || '了解更多', external: secondaryTo.startsWith('http') }
      : { to: '/guide', label: '了解更多', external: false },
  }
}

const slides = ref(
  defaultSlides.map((item) => ({
    ...item,
    href: item.primary.to,
    external: false,
    buttonLabel: item.primary.label,
    primary: item.primary,
    secondary: { ...item.secondary, external: false },
  })),
)

onMounted(async () => {
  start()
  try {
    const { data } = await api.get<RemoteSlide[]>('/site/slides')
    if (data.length) slides.value = data.map(fromRemote)
  } catch {
    /* 未配置时沿用现有首页 */
  }
})
onUnmounted(stop)
</script>

<style scoped>
.hero-hit {
  display: flex;
  align-items: center;
  width: 100%;
  height: 100%;
  color: inherit;
  text-decoration: none;
}
</style>

<template>
  <section class="hero-carousel" @mouseenter="stop" @mouseleave="start">
    <div
      v-for="(s, i) in slides"
      :key="s.id"
      class="hero-slide"
      :class="{ active: i === index }"
      :style="{ backgroundImage: `linear-gradient(105deg, rgba(8,12,20,.72) 0%, rgba(15,23,42,.35) 55%, rgba(15,23,42,.2) 100%), url(${s.image})` }"
    >
      <div class="hero-inner">
        <h1 v-if="s.titleHtml" v-html="s.titleHtml" />
        <p v-if="s.lead" class="hero-lead">{{ s.lead }}</p>
        <div v-if="s.meta" class="hero-meta">{{ s.meta }}</div>
        <div class="hero-cta">
          <a v-if="s.external" class="btn ghost" :href="s.primary.to" target="_blank" rel="noopener">{{ s.primary.label }}</a>
          <RouterLink v-else class="btn ghost" :to="s.primary.to">{{ s.primary.label }}</RouterLink>
          <a v-if="s.secondary?.external" class="btn ghost" :href="s.secondary.to" target="_blank" rel="noopener">{{ s.secondary.label }}</a>
          <RouterLink v-else-if="s.secondary" class="btn ghost" :to="s.secondary.to">{{ s.secondary.label }}</RouterLink>
        </div>
      </div>
    </div>

    <button class="hero-nav prev" type="button" aria-label="上一张" @click="prev">‹</button>
    <button class="hero-nav next" type="button" aria-label="下一张" @click="next">›</button>

    <div class="hero-dots" role="tablist">
      <button
        v-for="(s, i) in slides"
        :key="s.id"
        type="button"
        class="hero-dot"
        :class="{ active: i === index }"
        :aria-label="`切换到第 ${i + 1} 张`"
        @click="go(i)"
      />
    </div>
  </section>
</template>
