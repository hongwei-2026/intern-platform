<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

export type PaperBlock = {
  id: string
  type: 'text' | 'image' | 'video' | 'table'
  text?: string
  url?: string
  rows?: string[][]
}

const props = defineProps<{ host: { body?: string | null; blocks?: PaperBlock[] } }>()

const root = ref<HTMLElement | null>(null)
const picked = ref('')
const cell = ref<{ id: string; r: number; c: number } | null>(null)

function blocks(): PaperBlock[] {
  if (!props.host.blocks?.length) {
    props.host.blocks = [{ id: `b-${Date.now()}`, type: 'text', text: props.host.body || '' }]
  }
  return props.host.blocks
}

/** 图、表、视频后面一定留一段可以接着写的文字。 */
function followText() {
  const list = blocks()
  for (let i = 0; i < list.length; i += 1) {
    if (list[i].type !== 'text' && list[i + 1]?.type !== 'text') {
      list.splice(i + 1, 0, { id: `b-${Date.now()}-${i}`, type: 'text', text: '' })
    }
  }
  if (list[list.length - 1]?.type !== 'text') {
    list.push({ id: `b-${Date.now()}-end`, type: 'text', text: '' })
  }
}

watch(() => props.host, () => followText(), { immediate: true })
watch(() => props.host.blocks?.length, () => followText())

function remove(id: string) {
  const list = blocks()
  const rest = list.filter((block) => block.id !== id)
  props.host.blocks = rest.length ? rest : [{ id: `b-${Date.now()}`, type: 'text', text: '' }]
  picked.value = ''
  followText()
  void nextTick(() => focusText(rest.find((block) => block.type === 'text')?.id))
}

function focusText(id?: string) {
  const area = id
    ? (root.value?.querySelector(`textarea[data-id="${id}"]`) as HTMLTextAreaElement | null)
    : (root.value?.querySelectorAll('textarea')[root.value.querySelectorAll('textarea').length - 1] as HTMLTextAreaElement | undefined)
  area?.focus()
}

function addRow(block: PaperBlock) {
  const width = block.rows?.[0]?.length || 3
  block.rows = block.rows || []
  block.rows.push(Array.from({ length: width }, () => ''))
}

function addCol(block: PaperBlock) {
  if (!block.rows?.length) block.rows = [['']]
  block.rows.forEach((row) => row.push(''))
}

function dropRow(block: PaperBlock) {
  const rows = block.rows || []
  if (rows.length <= 1) return
  const at = cell.value?.id === block.id ? cell.value.r : rows.length - 1
  rows.splice(Math.min(at, rows.length - 1), 1)
}

function dropCol(block: PaperBlock) {
  const rows = block.rows || []
  const width = rows[0]?.length || 0
  if (width <= 1) return
  const at = cell.value?.id === block.id ? cell.value.c : width - 1
  const index = Math.min(at, width - 1)
  rows.forEach((row) => row.splice(index, 1))
}

function pick(id: string, event: MouseEvent) {
  const target = event.target as HTMLElement
  if (target.closest('input, textarea, button, video')) return
  event.preventDefault()
  picked.value = id
  const host = event.currentTarget as HTMLElement
  host.focus()
}

function onRootDown(event: MouseEvent) {
  const target = event.target as HTMLElement
  if (target.closest('input, textarea, button, .pick, select')) return
  picked.value = ''
  focusText()
}

function onWindowKey(event: KeyboardEvent) {
  if (!picked.value) return
  if (event.key !== 'Delete' && event.key !== 'Backspace') return
  const active = document.activeElement as HTMLElement | null
  if (active?.closest('input, textarea, select')) return
  const inside = !active || active === document.body || active === document.documentElement || (root.value?.contains(active) ?? false)
  if (!inside) return
  event.preventDefault()
  remove(picked.value)
}

function onTextKey(block: PaperBlock, event: KeyboardEvent) {
  if (event.key !== 'Backspace') return
  const field = event.target as HTMLTextAreaElement
  const start = field.selectionStart ?? 0
  const end = field.selectionEnd ?? 0
  if (start !== end || start !== 0) return
  const list = blocks()
  const index = list.findIndex((item) => item.id === block.id)
  const prev = list[index - 1]
  if (!prev) {
    if (!(block.text || '').length && list.length > 1) {
      event.preventDefault()
      remove(block.id)
    }
    return
  }
  event.preventDefault()
  if (prev.type !== 'text') {
    remove(prev.id)
    void nextTick(() => focusText(block.id))
    return
  }
  if (!(block.text || '').length) {
    remove(block.id)
    void nextTick(() => focusText(prev.id))
    return
  }
  const caret = (prev.text || '').length
  prev.text = `${prev.text || ''}${block.text || ''}`
  remove(block.id)
  void nextTick(() => {
    const area = root.value?.querySelector(`textarea[data-id="${prev.id}"]`) as HTMLTextAreaElement | null
    area?.focus()
    area?.setSelectionRange(caret, caret)
  })
}

function markCell(block: PaperBlock, row: number, col: number) {
  cell.value = { id: block.id, r: row, c: col }
  picked.value = ''
}

onMounted(() => window.addEventListener('keydown', onWindowKey))
onBeforeUnmount(() => window.removeEventListener('keydown', onWindowKey))
</script>

<template>
  <div ref="root" class="paper-body" @mousedown="onRootDown">
    <div v-for="(block, index) in blocks()" :key="block.id" class="paper-block">
      <textarea
        v-if="block.type === 'text'"
        v-model="block.text"
        :data-id="block.id"
        class="paper-text"
        :class="{ grow: index === blocks().length - 1 }"
        rows="1"
        placeholder="从这里接着写"
        @focus="picked = ''"
        @keydown="onTextKey(block, $event)"
      />
      <div
        v-else-if="block.type === 'image'"
        class="pick"
        :class="{ on: picked === block.id }"
        tabindex="0"
        @mousedown="pick(block.id, $event)"
      >
        <img class="paper-media" :src="block.url" alt="" />
      </div>
      <div
        v-else-if="block.type === 'table'"
        class="table-wrap pick"
        :class="{ on: picked === block.id }"
        tabindex="0"
        @mousedown="pick(block.id, $event)"
      >
        <table class="paper-table">
          <tr v-for="(row, ri) in block.rows" :key="ri">
            <td v-for="(cellText, ci) in row" :key="ci">
              <input v-model="row[ci]" @focus="markCell(block, ri, ci)" />
            </td>
          </tr>
        </table>
        <div class="table-ops">
          <button type="button" class="table-op" @click="addRow(block)">加一行</button>
          <button type="button" class="table-op" :disabled="(block.rows || []).length <= 1" @click="dropRow(block)">删一行</button>
          <button type="button" class="table-op" @click="addCol(block)">加一列</button>
          <button type="button" class="table-op" :disabled="(block.rows?.[0]?.length || 0) <= 1" @click="dropCol(block)">删一列</button>
        </div>
      </div>
      <div v-else class="pick" :class="{ on: picked === block.id }" tabindex="0" @mousedown="pick(block.id, $event)">
        <video class="paper-media" :src="block.url" controls />
      </div>
    </div>
  </div>
</template>

<style scoped>
.paper-body { min-height: 100%; }
.paper-block { position: relative; margin: 0; }
.paper-text { display: block; width: 100%; box-sizing: border-box; border: 0; border-radius: 0; box-shadow: none; background: transparent; min-height: 2.6rem; resize: none; line-height: 1.85; font-size: 1.02rem; padding: 6px 0; margin: 0; font-family: inherit; color: inherit; }
.paper-text.grow { min-height: 7rem; }
.paper-text:focus { outline: none; }
.pick { border-radius: 8px; padding: 6px; cursor: pointer; }
.pick.on, .pick:focus { outline: 2px solid #1677ff; outline-offset: 3px; }
.paper-media { display: block; width: min(100%, 720px); max-height: 220px; object-fit: contain; background: #f7f9fc; border-radius: 8px; margin: 0; pointer-events: none; }
video.paper-media { pointer-events: auto; }
.table-wrap { padding: 6px; }
.paper-table { width: 100%; border-collapse: collapse; margin: 0; }
.paper-table td { border: 1px solid #d0d7e2; padding: 0; }
.paper-table input { border: 0; border-radius: 0; margin: 0; padding: 6px 8px; width: 100%; background: transparent; box-shadow: none; font: inherit; }
.table-ops { display: flex; flex-wrap: wrap; gap: 4px 0; padding-top: 4px; }
.table-op { border: 0; background: transparent; color: #1677ff; cursor: pointer; font: inherit; padding: 0 10px 0 0; }
.table-op:disabled { color: #b7c3d4; cursor: default; }
</style>
