<script setup lang="ts">
import { nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import * as pdfjs from 'pdfjs-dist'
import pdfWorker from 'pdfjs-dist/build/pdf.worker.min.mjs?url'

pdfjs.GlobalWorkerOptions.workerSrc = pdfWorker

const props = defineProps<{
  open: boolean
  url: string
  title?: string
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
}>()

const loading = ref(false)
const err = ref('')
const page = ref(1)
const pageCount = ref(0)
const scale = ref(1.15)
const canvasRef = ref<HTMLCanvasElement | null>(null)

let objectUrl = ''
let pdfDoc: Awaited<ReturnType<typeof pdfjs.getDocument>['promise']> | null = null
let renderToken = 0

function revoke() {
  if (objectUrl) {
    URL.revokeObjectURL(objectUrl)
    objectUrl = ''
  }
}

function close() {
  emit('update:open', false)
}

function onKey(e: KeyboardEvent) {
  if (!props.open) return
  if (e.key === 'Escape') close()
  if (e.key === 'ArrowLeft') void prevPage()
  if (e.key === 'ArrowRight') void nextPage()
}

async function destroyDoc() {
  renderToken += 1
  if (pdfDoc) {
    try {
      await pdfDoc.destroy()
    } catch {
      /* ignore */
    }
    pdfDoc = null
  }
  pageCount.value = 0
  page.value = 1
}

async function loadPdf(url: string) {
  await destroyDoc()
  revoke()
  err.value = ''
  if (!url) return
  loading.value = true
  try {
    const res = await fetch(url, { credentials: 'same-origin' })
    if (!res.ok) throw new Error(`加载失败（${res.status}）`)
    const buf = await res.arrayBuffer()
    const blob = new Blob([buf], { type: 'application/pdf' })
    objectUrl = URL.createObjectURL(blob)
    const task = pdfjs.getDocument({ data: buf })
    pdfDoc = await task.promise
    pageCount.value = pdfDoc.numPages
    page.value = 1
    loading.value = false
    await nextTick()
    await drawPage()
  } catch (e: unknown) {
    err.value = e instanceof Error ? e.message : '预览加载失败'
    loading.value = false
  }
}

async function drawPage() {
  if (!pdfDoc || !canvasRef.value) return
  const token = ++renderToken
  const pdfPage = await pdfDoc.getPage(page.value)
  if (token !== renderToken) return

  const viewport = pdfPage.getViewport({ scale: scale.value })
  const canvas = canvasRef.value
  const ctx = canvas.getContext('2d')
  if (!ctx) return

  const outputScale = window.devicePixelRatio || 1
  canvas.width = Math.floor(viewport.width * outputScale)
  canvas.height = Math.floor(viewport.height * outputScale)
  canvas.style.width = `${Math.floor(viewport.width)}px`
  canvas.style.height = `${Math.floor(viewport.height)}px`
  ctx.setTransform(outputScale, 0, 0, outputScale, 0, 0)

  await pdfPage.render({ canvasContext: ctx, viewport }).promise
}

async function prevPage() {
  if (page.value <= 1) return
  page.value -= 1
  await drawPage()
}

async function nextPage() {
  if (page.value >= pageCount.value) return
  page.value += 1
  await drawPage()
}

async function zoomBy(delta: number) {
  scale.value = Math.min(2.4, Math.max(0.6, Number((scale.value + delta).toFixed(2))))
  await drawPage()
}

function openTab() {
  if (objectUrl) window.open(objectUrl, '_blank', 'noopener')
  else if (props.url) window.open(props.url, '_blank', 'noopener')
}

onMounted(() => window.addEventListener('keydown', onKey))
onUnmounted(() => {
  window.removeEventListener('keydown', onKey)
  void destroyDoc()
  revoke()
  document.body.style.overflow = ''
})

watch(
  () => [props.open, props.url] as const,
  ([open, url]) => {
    document.body.style.overflow = open ? 'hidden' : ''
    if (open && url) void loadPdf(url)
    if (!open) {
      void destroyDoc()
      revoke()
      err.value = ''
    }
  },
)
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="pdf-mask" @click.self="close">
      <div class="pdf-shell" role="dialog" aria-modal="true" :aria-label="title || 'PDF 预览'">
        <header class="pdf-bar">
          <strong>{{ title || 'PDF 预览' }}</strong>
          <div class="pdf-bar-actions">
            <button type="button" class="ghost" @click="openTab">新窗口打开</button>
            <button type="button" class="solid" @click="close">关闭</button>
          </div>
        </header>

        <div v-if="!loading && !err && pageCount" class="pdf-tools">
          <button type="button" class="tool" :disabled="page <= 1" @click="prevPage">上一页</button>
          <span class="page-ind">{{ page }} / {{ pageCount }}</span>
          <button type="button" class="tool" :disabled="page >= pageCount" @click="nextPage">
            下一页
          </button>
          <span class="sep" />
          <button type="button" class="tool" @click="zoomBy(-0.15)">缩小</button>
          <span class="zoom">{{ Math.round(scale * 100) }}%</span>
          <button type="button" class="tool" @click="zoomBy(0.15)">放大</button>
        </div>

        <div class="pdf-body">
          <p v-if="loading" class="pdf-state">正在加载预览…</p>
          <p v-else-if="err" class="pdf-state err">
            {{ err }}
            <button type="button" class="ghost dark" @click="openTab">改用新窗口打开</button>
          </p>
          <div v-else class="pdf-stage">
            <canvas ref="canvasRef" class="pdf-canvas" />
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.pdf-mask {
  position: fixed;
  inset: 0;
  z-index: 3200;
  background: rgba(15, 23, 42, 0.58);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1.25rem;
}
.pdf-shell {
  width: min(1080px, 100%);
  max-height: min(92vh, 920px);
  background: #fff;
  border-radius: 10px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  box-shadow: 0 24px 64px rgba(15, 23, 42, 0.35);
  border: 1px solid #e2e8f0;
}
.pdf-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
  padding: 0.85rem 1.15rem;
  background: #0f2744;
  color: #f8fafc;
}
.pdf-bar strong {
  font-size: 0.95rem;
  font-weight: 650;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.pdf-bar-actions {
  display: flex;
  gap: 0.5rem;
  flex-shrink: 0;
}
.ghost,
.solid,
.tool {
  border: 0;
  cursor: pointer;
  font: inherit;
  font-size: 0.86rem;
  border-radius: 6px;
  padding: 0.38rem 0.75rem;
}
.ghost {
  background: transparent;
  color: #e2e8f0;
  border: 1px solid rgba(226, 232, 240, 0.45);
}
.ghost:hover {
  background: rgba(255, 255, 255, 0.08);
}
.ghost.dark {
  color: #1e3a5f;
  border-color: #cbd5e1;
  margin-left: 0.75rem;
}
.solid {
  background: #2563eb;
  color: #fff;
}
.solid:hover {
  background: #1d4ed8;
}
.pdf-tools {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  padding: 0.55rem 1rem;
  background: #f8fafc;
  border-bottom: 1px solid #e2e8f0;
  color: #334155;
  font-size: 0.86rem;
}
.tool {
  background: #fff;
  border: 1px solid #dbe3f0;
  color: #1e293b;
  padding: 0.28rem 0.65rem;
}
.tool:hover:not(:disabled) {
  border-color: #93c5fd;
  color: #1d4ed8;
}
.tool:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.page-ind,
.zoom {
  min-width: 4.2rem;
  text-align: center;
  color: #64748b;
  font-variant-numeric: tabular-nums;
}
.sep {
  width: 1px;
  height: 1.1rem;
  background: #dbe3f0;
  margin: 0 0.35rem;
}
.pdf-body {
  flex: 1;
  min-height: 0;
  background: #edf2f7;
  display: flex;
  flex-direction: column;
}
.pdf-stage {
  flex: 1;
  overflow: auto;
  padding: 1.25rem;
  display: flex;
  justify-content: center;
  align-items: flex-start;
}
.pdf-canvas {
  background: #fff;
  box-shadow: 0 8px 28px rgba(15, 23, 42, 0.12);
  border-radius: 2px;
}
.pdf-state {
  margin: auto;
  padding: 2.5rem 1.5rem;
  text-align: center;
  color: #475569;
  font-weight: 600;
}
.pdf-state.err {
  color: #b91c1c;
}
</style>
