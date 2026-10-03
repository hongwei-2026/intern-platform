<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import api from '@/api/client'

type Slide = {
  id: string
  title?: string
  lead?: string
  image?: string
  jump?: 'page' | 'link'
  pageTitle?: string
  pageBody?: string
  link?: string
}

const route = useRoute()
const slide = ref<Slide | null>(null)
const missing = ref(false)

onMounted(async () => {
  try {
    const { data } = await api.get<Slide>(`/site/slides/${route.params.id}`)
    slide.value = data
  } catch {
    missing.value = true
  }
})
</script>

<template>
  <div class="page banner-page">
    <p v-if="missing" class="muted">这张首页大图已经下架，或还没有发布。</p>
    <article v-else-if="slide">
      <img v-if="slide.image" :src="slide.image" alt="" />
      <h1>{{ slide.pageTitle || slide.title || '活动' }}</h1>
      <p class="lead">{{ slide.lead }}</p>
      <div class="body">{{ slide.pageBody || '这次上新还没有填写正文。' }}</div>
      <p v-if="slide.link">
        <a v-if="slide.link.startsWith('http')" :href="slide.link" target="_blank" rel="noopener">继续查看</a>
        <RouterLink v-else :to="slide.link">继续查看</RouterLink>
      </p>
    </article>
  </div>
</template>

<style scoped>
.banner-page { width: min(880px, 94%); }
img { width: 100%; border-radius: 12px; max-height: 420px; object-fit: cover; }
h1 { margin: 1rem 0 0.4rem; color: #1e3a5f; }
.lead { color: #64748b; }
.body { white-space: pre-wrap; line-height: 1.8; }
</style>
