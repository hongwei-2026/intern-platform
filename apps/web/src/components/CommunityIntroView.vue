<script setup lang="ts">
import { computed } from 'vue'
import type { CommunityIntroBody, IntroBlock } from '@/api/types'

const props = defineProps<{
  body?: CommunityIntroBody | null
  fallback?: string | null
}>()

const blocks = computed(() => {
  const raw = props.body?.blocks ?? []
  return raw.filter((b) => {
    if (b.type === 'paragraph' || b.type === 'heading') return !!(b.text && b.text.trim())
    if (b.type === 'image' || b.type === 'video') return !!(b.url && String(b.url).trim())
    if (b.type === 'table') return !!(b.headers?.length || b.rows?.length)
    return true
  })
})

function mediaSrc(url: string) {
  const u = (url || '').trim()
  if (!u) return ''
  // 已是绝对地址或 blob
  if (/^(https?:|blob:|data:)/i.test(u)) return u
  // 站点相对路径
  return u.startsWith('/') ? u : `/${u}`
}

function embedSrc(url: string): string | null {
  const u = (url || '').trim()
  if (!u) return null
  const yt =
    u.match(/(?:youtube\.com\/watch\?v=|youtu\.be\/)([\w-]{6,})/) ||
    u.match(/youtube\.com\/embed\/([\w-]{6,})/)
  if (yt) return `https://www.youtube.com/embed/${yt[1]}`
  const bv = u.match(/bilibili\.com\/video\/(BV[\w]+)/i)
  if (bv) return `https://player.bilibili.com/player.html?bvid=${bv[1]}&high_quality=1`
  if (/player\.bilibili\.com|youtube\.com\/embed/.test(u)) return u
  return null
}

function isDirectVideo(url: string) {
  return /\.(mp4|webm|ogg)(\?|$)/i.test(url)
}

function videoMode(b: IntroBlock): 'iframe' | 'file' | 'link' | 'none' {
  if (!b.url) return 'none'
  if (embedSrc(b.url)) return 'iframe'
  if (isDirectVideo(b.url)) return 'file'
  return 'link'
}
</script>

<template>
  <div class="intro-view">
    <template v-if="blocks.length">
      <template v-for="(b, i) in blocks" :key="(b.id || i) + '-' + (b.url || b.text || '')">
        <h2 v-if="b.type === 'heading'" class="h">{{ b.text }}</h2>
        <p v-else-if="b.type === 'paragraph'" class="p">{{ b.text }}</p>
        <figure v-else-if="b.type === 'image'" class="fig">
          <img :src="mediaSrc(b.url || '')" :alt="b.caption || '介绍图片'" loading="lazy" />
          <figcaption v-if="b.caption">{{ b.caption }}</figcaption>
        </figure>
        <div v-else-if="b.type === 'video' && b.url" class="vid">
          <iframe
            v-if="videoMode(b) === 'iframe'"
            :src="embedSrc(b.url) || ''"
            allowfullscreen
            loading="lazy"
            referrerpolicy="no-referrer"
            title="社区介绍视频"
          />
          <video v-else-if="videoMode(b) === 'file'" :src="mediaSrc(b.url)" controls playsinline />
          <p v-else class="link-fallback">
            视频链接：
            <a :href="b.url" target="_blank" rel="noopener">{{ b.url }}</a>
          </p>
        </div>
        <div v-else-if="b.type === 'table'" class="tbl-wrap">
          <table>
            <thead v-if="b.headers?.length">
              <tr>
                <th v-for="(h, ci) in b.headers" :key="'h' + ci">{{ h }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(row, ri) in b.rows || []" :key="'r' + ri">
                <td v-for="(cell, ci) in row" :key="'c' + ci">{{ cell }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </template>
    </template>
    <p v-else-if="fallback" class="muted">{{ fallback }}</p>
    <p v-else class="muted">该社区暂未填写详细介绍。</p>
  </div>
</template>

<style scoped>
.intro-view {
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
  max-width: 100%;
}
.h {
  margin: 0;
  font-size: 1.15rem;
  color: #262626;
}
.p {
  margin: 0;
  color: #595959;
  font-size: 0.92rem;
  line-height: 1.75;
  white-space: pre-wrap;
}
.fig {
  margin: 0;
}
.fig img {
  width: 100%;
  max-width: 100%;
  max-height: 360px;
  border-radius: 8px;
  display: block;
  border: 1px solid #f0f0f0;
  background: #f5f5f5;
  object-fit: contain;
  min-height: 80px;
}
.fig figcaption {
  margin-top: 0.35rem;
  font-size: 0.8rem;
  color: #8c8c8c;
}
.vid iframe,
.vid video {
  width: 100%;
  aspect-ratio: 16 / 9;
  border: none;
  border-radius: 8px;
  background: #000;
}
.link-fallback {
  margin: 0;
  font-size: 0.86rem;
  word-break: break-all;
}
.link-fallback a {
  color: #1677ff;
}
.tbl-wrap {
  overflow: auto;
  border: 1px solid #f0f0f0;
  border-radius: 8px;
}
table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.86rem;
}
th,
td {
  padding: 0.5rem 0.65rem;
  border-bottom: 1px solid #f5f5f5;
  text-align: left;
}
th {
  background: #fafafa;
  color: #595959;
  font-weight: 600;
}
.muted {
  margin: 0;
  color: #bfbfbf;
  font-size: 0.86rem;
}
</style>
