<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { getStoredToken, withFileAuth } from '@/api/client'
import * as pdfjs from 'pdfjs-dist'
import pdfWorker from 'pdfjs-dist/build/pdf.worker.min.mjs?url'

pdfjs.GlobalWorkerOptions.workerSrc = pdfWorker

const props = defineProps<{ url: string }>()

const canvasRef = ref<HTMLCanvasElement | null>(null)
const loading = ref(false)
const err = ref('')
const page = ref(1)
const pageCount = ref(0)
const scale = ref(1.2)
let doc: Awaited<ReturnType<typeof pdfjs.getDocument>['promise']> | null = null
let token = 0

async function destroy() {
  token += 1
  if (doc) {
    try {
      await doc.destroy()
    } catch {
      /* ignore */
    }
    doc = null
  }
  pageCount.value = 0
  page.value = 1
}

async function draw() {
  if (!doc || !canvasRef.value) return
  const mine = ++token
  const pdfPage = await doc.getPage(page.value)
  if (mine !== token) return
  const viewport = pdfPage.getViewport({ scale: scale.value })
  const canvas = canvasRef.value
  const ctx = canvas.getContext('2d')
  if (!ctx) return
  const ratio = window.devicePixelRatio || 1
  canvas.width = Math.floor(viewport.width * ratio)
  canvas.height = Math.floor(viewport.height * ratio)
  canvas.style.width = `${Math.floor(viewport.width)}px`
  canvas.style.height = `${Math.floor(viewport.height)}px`
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0)
  await pdfPage.render({ canvasContext: ctx, viewport }).promise
}

async function load(url: string) {
  await destroy()
  err.value = ''
  if (!url) return
  loading.value = true
  try {
    const headers: HeadersInit = {}
    const token = getStoredToken()
    if (token) headers.Authorization = `Bearer ${token}`
    const res = await fetch(withFileAuth(url), { credentials: 'same-origin', headers })
    if (!res.ok) throw new Error('文档加载失败')
    const data = await res.arrayBuffer()
    doc = await pdfjs.getDocument({ data }).promise
    pageCount.value = doc.numPages
    page.value = 1
    loading.value = false
    await draw()
  } catch (e: unknown) {
    err.value = e instanceof Error ? e.message : '文档加载失败'
    loading.value = false
  }
}

async function step(delta: number) {
  const next = page.value + delta
  if (next < 1 || next > pageCount.value) return
  page.value = next
  await draw()
}

async function zoom(delta: number) {
  scale.value = Math.min(2.2, Math.max(0.7, Number((scale.value + delta).toFixed(2))))
  await draw()
}

onMounted(() => load(props.url))
watch(
  () => props.url,
  (url) => load(url),
)
</script>

<template>
  <div class="reader">
    <div class="tools">
      <button type="button" :disabled="page <= 1" @click="step(-1)">上一页</button>
      <span>{{ pageCount ? `${page} / ${pageCount}` : '—' }}</span>
      <button type="button" :disabled="page >= pageCount" @click="step(1)">下一页</button>
      <button type="button" @click="zoom(-0.15)">缩小</button>
      <button type="button" @click="zoom(0.15)">放大</button>
    </div>
    <div class="stage">
      <p v-if="loading">正在打开文档…</p>
      <p v-else-if="err">{{ err }}</p>
      <canvas v-show="!loading && !err" ref="canvasRef" />
    </div>
  </div>
</template>

<style scoped>
.reader {
  display: flex;
  flex-direction: column;
  min-height: 0;
  height: 100%;
  background: #eef2f6;
}
.tools {
  display: flex;
  gap: 8px;
  align-items: center;
  padding: 8px 12px;
  background: #fff;
  border-bottom: 1px solid #e6e6e6;
  font-size: 13px;
}
.tools button {
  border: 1px solid #d9d9d9;
  background: #fff;
  border-radius: 6px;
  padding: 4px 8px;
  cursor: pointer;
  font: inherit;
}
.tools button:disabled { opacity: 0.4; cursor: default; }
.stage {
  flex: 1;
  overflow: auto;
  padding: 16px;
  display: flex;
  justify-content: center;
  align-items: flex-start;
}
canvas {
  background: #fff;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.12);
}
</style>
