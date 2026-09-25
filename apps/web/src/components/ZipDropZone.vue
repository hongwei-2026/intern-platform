<script setup lang="ts">
import { ref } from 'vue'
import api from '@/api/client'

const props = defineProps<{
  url: string
  name: string
  disabled?: boolean
}>()

const emit = defineEmits<{
  'update:url': [string]
  'update:name': [string]
  error: [string]
}>()

const dragging = ref(false)
const uploading = ref(false)
const inputRef = ref<HTMLInputElement | null>(null)

function pick() {
  if (props.disabled || uploading.value) return
  inputRef.value?.click()
}

async function uploadFile(file: File | null | undefined) {
  if (!file || props.disabled) return
  if (!file.name.toLowerCase().endsWith('.zip') && file.type !== 'application/zip') {
    emit('error', '只能上传 zip 文件格式')
    return
  }
  if (file.size > 100 * 1024 * 1024) {
    emit('error', '文件最大不超过 100M')
    return
  }
  uploading.value = true
  emit('error', '')
  try {
    const fd = new FormData()
    fd.append('file', file)
    const { data } = await api.post<{ url: string; filename: string }>('/uploads/zip', fd)
    emit('update:url', data.url)
    emit('update:name', data.filename || file.name)
  } catch (e: unknown) {
    emit('error', e instanceof Error ? e.message : '上传失败')
  } finally {
    uploading.value = false
  }
}

function onInput(e: Event) {
  const input = e.target as HTMLInputElement
  const f = input.files?.[0]
  input.value = ''
  void uploadFile(f)
}

function onDrop(e: DragEvent) {
  dragging.value = false
  e.preventDefault()
  void uploadFile(e.dataTransfer?.files?.[0])
}

function clear() {
  emit('update:url', '')
  emit('update:name', '')
  if (inputRef.value) inputRef.value.value = ''
}
</script>

<template>
  <div class="zip-zone">
    <div
      class="upload-wrap"
      :class="{ dragging, filled: !!url, disabled }"
      @dragenter.prevent="!disabled && (dragging = true)"
      @dragover.prevent="!disabled && (dragging = true)"
      @dragleave.prevent="dragging = false"
      @drop.prevent="onDrop"
    >
      <input
        ref="inputRef"
        type="file"
        accept=".zip,application/zip"
        hidden
        :disabled="disabled || uploading"
        @change="onInput"
      />
      <button class="upload-btn" type="button" :disabled="disabled || uploading" @click="pick">
        + 上传文件
      </button>
      <span v-if="uploading" class="muted">上传中…</span>
      <span v-else-if="dragging" class="muted">松开以上传 zip</span>
      <template v-else-if="url">
        <a class="zip-link" :href="url" target="_blank" rel="noopener">{{ name || '交付件.zip' }}</a>
        <button type="button" class="linkish" :disabled="disabled" @click="clear">移除</button>
      </template>
      <span v-else class="hint-inline">或将 zip 拖拽到此处</span>
    </div>
    <p class="hint">只能上传 zip 文件格式，且文件最大不超过 100M</p>
  </div>
</template>

<style scoped>
.upload-wrap {
  display: flex;
  flex-wrap: wrap;
  gap: 0.55rem;
  align-items: center;
  min-height: 2.6rem;
  padding: 0.55rem 0.75rem;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #fff;
  transition: border-color 0.15s, background 0.15s;
}
.upload-wrap.dragging {
  border-color: #2563eb;
  background: #eff6ff;
}
.upload-wrap.filled {
  border-color: #cbd5e1;
}
.upload-wrap.disabled {
  opacity: 0.55;
  pointer-events: none;
}
.upload-btn {
  display: inline-flex;
  padding: 0.35rem 0.75rem;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  background: #fff;
  cursor: pointer;
  font-weight: 600;
  font-size: 0.86rem;
  font: inherit;
}
.upload-btn:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}
.hint {
  margin: 0.45rem 0 0;
  font-size: 0.78rem;
  color: #9ca3af;
}
.hint-inline {
  font-size: 0.82rem;
  color: #9ca3af;
}
.zip-link {
  color: #2563eb;
  font-weight: 500;
  font-size: 0.86rem;
}
.linkish {
  border: none;
  background: none;
  color: #6b7280;
  cursor: pointer;
  font: inherit;
  font-size: 0.82rem;
}
.muted {
  color: #9ca3af;
  font-size: 0.85rem;
}
</style>
