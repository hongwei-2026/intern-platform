<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import api from '@/api/client'
import { packLiaison, type LiaisonFile } from '@/utils/liaisonBody'

const props = defineProps<{
  placeholder?: string
  sendLabel?: string
  disabled?: boolean
}>()

const emit = defineEmits<{ send: [body: string] }>()

const draft = ref('')
const parts = ref<(LiaisonFile & { id: string })[]>([])
const open = ref(false)
const picked = ref('')
const cell = ref<{ id: string; r: number; c: number } | null>(null)
const imageRef = ref<HTMLInputElement | null>(null)
const fileRef = ref<HTMLInputElement | null>(null)
const busy = ref(false)
const error = ref('')

function addTable() {
  open.value = false
  parts.value.push({
    id: `t-${Date.now()}`,
    type: 'table',
    rows: [
      ['', ''],
      ['', ''],
    ],
  })
}

function addRow(part: LiaisonFile) {
  const width = part.rows?.[0]?.length || 2
  part.rows = part.rows || []
  part.rows.push(Array.from({ length: width }, () => ''))
}

function addCol(part: LiaisonFile) {
  part.rows?.forEach((row) => row.push(''))
}

type Part = LiaisonFile & { id: string }

function dropRow(part: Part) {
  const rows = part.rows || []
  if (rows.length <= 1) return
  const at = cell.value?.id === part.id ? cell.value.r : rows.length - 1
  rows.splice(Math.min(at, rows.length - 1), 1)
}

function dropCol(part: Part) {
  const rows = part.rows || []
  const width = rows[0]?.length || 0
  if (width <= 1) return
  const at = cell.value?.id === part.id ? cell.value.c : width - 1
  const index = Math.min(at, width - 1)
  rows.forEach((row) => row.splice(index, 1))
}

function drop(id: string) {
  parts.value = parts.value.filter((part) => part.id !== id)
}

async function upload(kind: 'image' | 'file', event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  busy.value = true
  error.value = ''
  try {
    const body = new FormData()
    body.append('file', file)
    const { data } = await api.post<{ url: string; filename: string }>(`/uploads/${kind}`, body)
    parts.value.push({ id: `f-${Date.now()}`, type: kind, url: data.url, name: data.filename || file.name })
  } catch (err: unknown) {
    error.value = err instanceof Error ? err.message : '上传失败'
  } finally {
    busy.value = false
  }
}

function markCell(part: Part, row: number, col: number) {
  cell.value = { id: part.id, r: row, c: col }
  picked.value = ''
}

function pickPart(id: string, event: MouseEvent) {
  const target = event.target as HTMLElement
  if (target.closest('input, button')) return
  event.preventDefault()
  picked.value = id
  ;(event.currentTarget as HTMLElement).focus()
}

function onWindowKey(event: KeyboardEvent) {
  if (!picked.value) return
  if (event.key !== 'Delete' && event.key !== 'Backspace') return
  const active = document.activeElement as HTMLElement | null
  if (active?.closest('input, textarea, select')) return
  event.preventDefault()
  drop(picked.value)
  picked.value = ''
}

onMounted(() => window.addEventListener('keydown', onWindowKey))
onBeforeUnmount(() => window.removeEventListener('keydown', onWindowKey))

function submit() {
  const text = draft.value.trim()
  if (!text && !parts.value.length) return
  emit('send', packLiaison(text, parts.value.map(({ id: _id, ...part }) => part)))
  draft.value = ''
  parts.value = []
}
</script>

<template>
  <form class="composer" @submit.prevent="submit">
    <p v-if="error" class="err">{{ error }}</p>
    <div v-for="part in parts" :key="part.id" class="part" :class="{ on: picked === part.id }" tabindex="0" @mousedown="pickPart(part.id, $event)">
      <img v-if="part.type === 'image'" :src="part.url" alt="" />
      <span v-else-if="part.type === 'file'">{{ part.name }}</span>
      <div v-else>
        <table>
          <tr v-for="(row, ri) in part.rows" :key="ri">
            <td v-for="(cellText, ci) in row" :key="ci"><input v-model="row[ci]" @focus="markCell(part, ri, ci)" /></td>
          </tr>
        </table>
        <button type="button" @click="addRow(part)">加一行</button>
        <button type="button" :disabled="(part.rows || []).length <= 1" @click="dropRow(part)">删一行</button>
        <button type="button" @click="addCol(part)">加一列</button>
        <button type="button" :disabled="(part.rows?.[0]?.length || 0) <= 1" @click="dropCol(part)">删一列</button>
      </div>
      <button type="button" @click="drop(part.id)">去掉</button>
    </div>
    <textarea v-model="draft" rows="3" :placeholder="placeholder || '写消息，也可以附上材料'" />
    <div class="bar">
      <div class="plus">
        <button type="button" class="plus-btn" aria-label="添加材料" @click="open = !open">+</button>
        <div v-if="open" class="menu">
          <button type="button" @click="imageRef?.click()">图片</button>
          <button type="button" @click="addTable">表格</button>
          <button type="button" @click="fileRef?.click()">文件</button>
        </div>
        <input ref="imageRef" type="file" accept="image/jpeg,image/png,image/webp,image/gif" hidden @change="upload('image', $event); open = false" />
        <input ref="fileRef" type="file" accept=".pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.txt,.csv,.zip" hidden @change="upload('file', $event); open = false" />
      </div>
      <button class="send" type="submit" :disabled="disabled || busy">{{ busy ? '上传中…' : sendLabel || '发送' }}</button>
    </div>
  </form>
</template>

<style scoped>
.composer { display: flex; flex-direction: column; gap: 8px; }
.err { margin: 0; color: #dc2626; font-size: 0.82rem; }
.part { display: flex; gap: 8px; align-items: flex-start; border-radius: 8px; padding: 4px; }
.part.on, .part:focus { outline: 2px solid #1677ff; outline-offset: 2px; }
.part img { width: 96px; height: 72px; object-fit: cover; border-radius: 6px; pointer-events: none; }
table { border-collapse: collapse; }
td { border: 1px solid #d0d7e2; padding: 0; }
input { border: 0; width: 6rem; padding: 4px 6px; font: inherit; }
textarea { width: 100%; box-sizing: border-box; border: 1px solid #b7c3d4; border-radius: 8px; padding: 8px 10px; font: inherit; }
.bar { display: flex; gap: 8px; justify-content: flex-end; align-items: center; }
.plus { position: relative; }
.plus-btn { width: 36px; height: 36px; border-radius: 999px; border: 1px solid #d0d7e2; background: #fff; color: #1e3a5f; font-size: 1.4rem; line-height: 1; cursor: pointer; }
.menu { position: absolute; right: 0; bottom: 42px; display: flex; flex-direction: column; min-width: 88px; background: #fff; border: 1px solid #d0d7e2; border-radius: 10px; box-shadow: 0 8px 24px rgba(15, 23, 42, 0.12); overflow: hidden; z-index: 2; }
.menu button { border: 0; border-bottom: 1px solid #eef2f6; background: #fff; padding: 8px 12px; text-align: left; cursor: pointer; font: inherit; color: #1e3a5f; }
.menu button:last-child { border-bottom: 0; }
.bar .send { background: #1677ff; color: #fff; border: 0; border-radius: 8px; padding: 6px 14px; cursor: pointer; font: inherit; }
</style>
