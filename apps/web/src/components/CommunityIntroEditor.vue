<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import api from '@/api/client'
import type { CommunityIntroBody, IntroBlock } from '@/api/types'

const props = withDefaults(
  defineProps<{
    modelValue: CommunityIntroBody | null
    tags?: string[]
    compact?: boolean
  }>(),
  { tags: () => [], compact: false },
)

const emit = defineEmits<{
  'update:modelValue': [CommunityIntroBody]
  'update:tags': [string[]]
  publish: []
}>()

const busy = ref(false)
const err = ref('')
const imgInput = ref<HTMLInputElement | null>(null)
const replaceIndex = ref<number | null>(null)
const videoDraft = ref('')
const showVideoBox = ref(false)
const tagDraft = ref('')
const MAX_TAGS = 12

const tagList = computed({
  get: () => props.tags ?? [],
  set: (next: string[]) => emit('update:tags', next),
})

const blocks = computed({
  get: () => props.modelValue?.blocks ?? [],
  set: (next: IntroBlock[]) => emit('update:modelValue', { blocks: next }),
})

function uid() {
  return Math.random().toString(36).slice(2, 10)
}

function setBlocks(next: IntroBlock[]) {
  // 深拷贝，避免父级引用不刷新右侧预览
  emit('update:modelValue', {
    blocks: next.map((b) => ({ ...b, rows: b.rows?.map((r) => [...r]), headers: b.headers ? [...b.headers] : b.headers })),
  })
}

function ensureStarter() {
  if (blocks.value.length) return
  setBlocks([{ id: uid(), type: 'paragraph', text: '' }])
}

onMounted(ensureStarter)

function pushBlock(block: IntroBlock) {
  setBlocks([...blocks.value, block])
}

function addHeading() {
  pushBlock({ id: uid(), type: 'heading', text: '' })
}

function addParagraph() {
  pushBlock({ id: uid(), type: 'paragraph', text: '' })
}

function addTable() {
  pushBlock({
    id: uid(),
    type: 'table',
    headers: ['列 1', '列 2'],
    rows: [
      ['', ''],
      ['', ''],
    ],
  })
}

function openVideo() {
  showVideoBox.value = !showVideoBox.value
}

function addVideo() {
  const url = videoDraft.value.trim()
  if (!url) return
  pushBlock({ id: uid(), type: 'video', url })
  videoDraft.value = ''
  showVideoBox.value = false
}

function pickImage() {
  replaceIndex.value = null
  imgInput.value?.click()
}

function replaceImage(i: number) {
  replaceIndex.value = i
  imgInput.value?.click()
}

async function onImageFile(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (imgInput.value) imgInput.value.value = ''
  if (!file) return
  err.value = ''
  busy.value = true
  const localUrl = URL.createObjectURL(file)
  const replaceAt = replaceIndex.value
  try {
    // 先本地预览（左右立即能看见）
    if (replaceAt != null) {
      patch(replaceAt, { url: localUrl })
    } else {
      pushBlock({ id: uid(), type: 'image', url: localUrl, caption: '' })
    }
    const fd = new FormData()
    fd.append('file', file)
    const { data } = await api.post<{ url: string }>('/uploads/image', fd)
    setBlocks(blocks.value.map((b) => (b.url === localUrl ? { ...b, url: data.url } : b)))
    URL.revokeObjectURL(localUrl)
  } catch (ex: unknown) {
    setBlocks(blocks.value.filter((b) => b.url !== localUrl))
    URL.revokeObjectURL(localUrl)
    const msg =
      ex && typeof ex === 'object' && 'response' in ex
        ? String((ex as { response?: { data?: { detail?: string } } }).response?.data?.detail || '')
        : ''
    err.value = msg || (ex instanceof Error ? ex.message : '图片上传失败')
  } finally {
    busy.value = false
    replaceIndex.value = null
  }
}

function addTag() {
  const t = tagDraft.value.trim().replace(/\s+/g, ' ').slice(0, 24)
  if (!t) return
  if (tagList.value.includes(t) || tagList.value.length >= MAX_TAGS) {
    tagDraft.value = ''
    return
  }
  tagList.value = [...tagList.value, t]
  tagDraft.value = ''
}

function removeTag(tag: string) {
  tagList.value = tagList.value.filter((x) => x !== tag)
}

function onTagKey(e: KeyboardEvent) {
  if (e.key === 'Enter' || e.key === ',') {
    e.preventDefault()
    addTag()
  }
}

function removeAt(i: number) {
  const list = [...blocks.value]
  list.splice(i, 1)
  setBlocks(list)
  if (!list.length) ensureStarter()
}

function move(i: number, dir: -1 | 1) {
  const j = i + dir
  if (j < 0 || j >= blocks.value.length) return
  const list = [...blocks.value]
  ;[list[i], list[j]] = [list[j], list[i]]
  setBlocks(list)
}

function patch(i: number, p: Partial<IntroBlock>) {
  setBlocks(blocks.value.map((b, idx) => (idx === i ? { ...b, ...p } : b)))
}

function onInputText(i: number, e: Event) {
  patch(i, { text: (e.target as HTMLInputElement | HTMLTextAreaElement).value })
}

function onInputCaption(i: number, e: Event) {
  patch(i, { caption: (e.target as HTMLInputElement).value })
}

function onInputUrl(i: number, e: Event) {
  patch(i, { url: (e.target as HTMLInputElement).value })
}

function onHeaderInput(i: number, ci: number, e: Event) {
  const b = blocks.value[i]
  if (b.type !== 'table') return
  const headers = [...(b.headers || [])]
  headers[ci] = (e.target as HTMLInputElement).value
  patch(i, { headers })
}

function onCellInput(i: number, ri: number, ci: number, e: Event) {
  const b = blocks.value[i]
  if (b.type !== 'table') return
  const rows = (b.rows || []).map((r) => [...r])
  rows[ri][ci] = (e.target as HTMLInputElement).value
  patch(i, { rows })
}

function addTableRow(i: number) {
  const b = blocks.value[i]
  if (b.type !== 'table') return
  const cols = Math.max(b.headers?.length || 2, 2)
  patch(i, { rows: [...(b.rows || []), Array.from({ length: cols }, () => '')] })
}

function addTableCol(i: number) {
  const b = blocks.value[i]
  if (b.type !== 'table') return
  const headers = [...(b.headers || []), `列 ${(b.headers?.length || 0) + 1}`]
  const rows = (b.rows || []).map((r) => [...r, ''])
  patch(i, { headers, rows })
}

function removeTableRow(i: number) {
  const b = blocks.value[i]
  if (b.type !== 'table') return
  const rows = [...(b.rows || [])]
  if (rows.length <= 1) return
  rows.pop()
  patch(i, { rows })
}

function removeTableCol(i: number) {
  const b = blocks.value[i]
  if (b.type !== 'table') return
  const headers = [...(b.headers || [])]
  if (headers.length <= 1) return
  headers.pop()
  const rows = (b.rows || []).map((r) => r.slice(0, -1))
  patch(i, { headers, rows })
}

function publish() {
  emit('publish')
}

const kindLabel: Record<string, string> = {
  heading: '标题',
  paragraph: '正文',
  image: '图片',
  table: '表格',
  video: '视频',
}
</script>

<template>
  <div class="editor" :class="{ compact }">
    <div class="topic-row">
      <span class="topic-lbl"># 标签</span>
      <span v-for="t in tagList" :key="t" class="chip">
        {{ t }}
        <button type="button" aria-label="删除" @click="removeTag(t)">×</button>
      </span>
      <input
        v-model="tagDraft"
        type="text"
        maxlength="24"
        placeholder="加话题，回车确认"
        @keydown="onTagKey"
      />
      <button type="button" class="linkish" @click="addTag">添加</button>
    </div>

    <div class="toolbar">
      <button type="button" class="tool" :disabled="busy" @click="pickImage">图片</button>
      <button type="button" class="tool" @click="openVideo">视频</button>
      <button type="button" class="tool" @click="addHeading">标题</button>
      <button type="button" class="tool" @click="addParagraph">段落</button>
      <button type="button" class="tool" @click="addTable">表格</button>
      <button type="button" class="publish" @click="publish">发布</button>
    </div>
    <p v-if="err" class="err">{{ err }}</p>
    <div v-if="showVideoBox" class="video-pop">
      <input v-model="videoDraft" type="url" placeholder="粘贴 B 站 / YouTube / 视频直链" />
      <button type="button" class="btn sm" @click="addVideo">插入</button>
      <button type="button" class="btn sm secondary" @click="showVideoBox = false">取消</button>
    </div>

    <div class="stream">
      <div v-for="(b, i) in blocks" :key="b.id || i" class="card">
        <div class="card-bar">
          <span class="kind">{{ kindLabel[b.type] || b.type }}</span>
          <button type="button" class="icon" :disabled="i === 0" @click="move(i, -1)">↑</button>
          <button type="button" class="icon" :disabled="i === blocks.length - 1" @click="move(i, 1)">
            ↓
          </button>
          <button type="button" class="icon danger" @click="removeAt(i)">删除</button>
        </div>

        <input
          v-if="b.type === 'heading'"
          class="heading"
          :value="b.text"
          placeholder="小节标题"
          @input="onInputText(i, $event)"
        />
        <textarea
          v-else-if="b.type === 'paragraph'"
          :rows="compact ? 3 : 4"
          :value="b.text"
          placeholder="在这里写介绍正文…"
          @input="onInputText(i, $event)"
        />
        <div v-else-if="b.type === 'image'" class="img-block">
          <img v-if="b.url" :src="b.url" alt="" />
          <div class="img-acts">
            <button class="btn sm" type="button" :disabled="busy" @click="replaceImage(i)">
              {{ busy ? '上传中…' : b.url ? '换图' : '上传' }}
            </button>
            <input
              :value="b.caption"
              placeholder="图片说明（可选）"
              @input="onInputCaption(i, $event)"
            />
          </div>
        </div>
        <div v-else-if="b.type === 'video'" class="video-block">
          <input :value="b.url" placeholder="视频链接" @input="onInputUrl(i, $event)" />
        </div>
        <div v-else-if="b.type === 'table'" class="table-block">
          <table>
            <thead>
              <tr>
                <th v-for="(h, ci) in b.headers || []" :key="'h' + ci">
                  <input :value="h" @input="onHeaderInput(i, ci, $event)" />
                </th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(row, ri) in b.rows || []" :key="'r' + ri">
                <td v-for="(cell, ci) in row" :key="'c' + ci">
                  <input :value="cell" @input="onCellInput(i, ri, ci, $event)" />
                </td>
              </tr>
            </tbody>
          </table>
          <div class="table-acts">
            <button class="btn sm secondary" type="button" @click="addTableRow(i)">加一行</button>
            <button
              class="btn sm secondary"
              type="button"
              :disabled="(b.rows || []).length <= 1"
              @click="removeTableRow(i)"
            >
              删一行
            </button>
            <button class="btn sm secondary" type="button" @click="addTableCol(i)">加一列</button>
            <button
              class="btn sm secondary"
              type="button"
              :disabled="(b.headers || []).length <= 1"
              @click="removeTableCol(i)"
            >
              删一列
            </button>
          </div>
        </div>
      </div>
    </div>

    <input
      ref="imgInput"
      type="file"
      accept="image/jpeg,image/png,image/webp,image/gif"
      hidden
      @change="onImageFile"
    />
  </div>
</template>

<style scoped>
.editor {
  display: flex;
  flex-direction: column;
  gap: 0.55rem;
}
.topic-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  align-items: center;
  padding: 0.4rem 0.5rem;
  background: #fafafa;
  border-radius: 8px;
  border: 1px solid #f0f0f0;
}
.topic-lbl {
  font-size: 0.8rem;
  font-weight: 700;
  color: #1677ff;
}
.chip {
  display: inline-flex;
  align-items: center;
  gap: 0.2rem;
  padding: 2px 8px;
  border-radius: 999px;
  background: #e6f4ff;
  color: #1677ff;
  font-size: 0.78rem;
  font-weight: 600;
}
.chip button {
  border: none;
  background: transparent;
  color: #69b1ff;
  cursor: pointer;
  font-size: 0.95rem;
  line-height: 1;
  padding: 0;
}
.topic-row input {
  flex: 1;
  min-width: 7rem;
  border: none;
  outline: none;
  background: transparent;
  font-size: 0.84rem;
}
.linkish {
  border: none;
  background: transparent;
  color: #1677ff;
  font-size: 0.8rem;
  font-weight: 600;
  cursor: pointer;
}
.toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 0.25rem;
  align-items: center;
}
.tool {
  border: 1px solid #f0f0f0;
  background: #fff;
  color: #595959;
  font-size: 0.82rem;
  font-weight: 600;
  padding: 0.35rem 0.65rem;
  border-radius: 6px;
  cursor: pointer;
}
.tool:hover {
  border-color: #91caff;
  color: #1677ff;
}
.tool:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}
.publish {
  margin-left: auto;
  border: none;
  background: #1677ff;
  color: #fff;
  font-weight: 700;
  font-size: 0.86rem;
  padding: 0.4rem 1rem;
  border-radius: 999px;
  cursor: pointer;
}
.publish:hover {
  background: #4096ff;
}
.err {
  margin: 0;
  color: #cf1322;
  font-size: 0.84rem;
}
.video-pop {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  padding: 0.5rem;
  background: #fafafa;
  border-radius: 8px;
}
.video-pop input {
  flex: 1;
  min-width: 12rem;
  border: 1px solid #f0f0f0;
  border-radius: 6px;
  padding: 0.4rem 0.55rem;
  font: inherit;
}
.stream {
  display: flex;
  flex-direction: column;
  gap: 0.55rem;
}
.card {
  border: 1px solid #f0f0f0;
  border-radius: 10px;
  padding: 0.65rem 0.75rem 0.75rem;
  background: #fff;
}
.card-bar {
  display: flex;
  gap: 0.3rem;
  align-items: center;
  margin-bottom: 0.4rem;
}
.kind {
  font-size: 0.72rem;
  font-weight: 700;
  color: #bfbfbf;
  margin-right: auto;
}
.icon {
  border: none;
  background: #f5f5f5;
  border-radius: 4px;
  padding: 0.12rem 0.4rem;
  cursor: pointer;
  font-size: 0.75rem;
  color: #595959;
}
.icon:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}
.icon.danger {
  color: #cf1322;
}
.heading {
  width: 100%;
  font-size: 1.05rem;
  font-weight: 700;
  border: 1px solid #f0f0f0;
  border-radius: 6px;
  padding: 0.4rem 0.55rem;
}
textarea,
.video-block input,
.img-acts input {
  width: 100%;
  border: 1px solid #f0f0f0;
  border-radius: 6px;
  padding: 0.45rem 0.55rem;
  font: inherit;
  resize: vertical;
  box-sizing: border-box;
}
.img-block img {
  max-width: 100%;
  max-height: 220px;
  border-radius: 8px;
  display: block;
  margin-bottom: 0.4rem;
  object-fit: contain;
  background: #fafafa;
}
.img-acts {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}
.table-block {
  overflow: auto;
}
.table-block table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.84rem;
}
.table-block th,
.table-block td {
  border: 1px solid #f0f0f0;
  padding: 0.2rem;
}
.table-block input {
  width: 100%;
  border: none;
  outline: none;
  padding: 0.3rem;
  background: transparent;
  font: inherit;
}
.table-acts {
  display: flex;
  gap: 0.35rem;
  margin-top: 0.4rem;
}
</style>
