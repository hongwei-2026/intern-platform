<script setup lang="ts">
import { computed, ref } from 'vue'

const props = withDefaults(
  defineProps<{
    label: string
    required?: boolean
    modelValue: File | null
    hint?: string
  }>(),
  { required: false, hint: '支持拖拽或点击选择，仅 PDF，最大 8MB' },
)

const emit = defineEmits<{
  'update:modelValue': [File | null]
}>()

const dragging = ref(false)
const inputRef = ref<HTMLInputElement | null>(null)
const localError = ref('')

const fileName = computed(() => props.modelValue?.name || '')

function pick() {
  inputRef.value?.click()
}

function acceptFile(file: File | null | undefined) {
  localError.value = ''
  if (!file) {
    emit('update:modelValue', null)
    return
  }
  if (!file.name.toLowerCase().endsWith('.pdf') && file.type !== 'application/pdf') {
    localError.value = '请上传 PDF 文件'
    emit('update:modelValue', null)
    return
  }
  if (file.size > 8 * 1024 * 1024) {
    localError.value = '文件不能超过 8MB'
    emit('update:modelValue', null)
    return
  }
  emit('update:modelValue', file)
}

function onInput(e: Event) {
  const f = (e.target as HTMLInputElement).files?.[0]
  acceptFile(f)
}

function onDrop(e: DragEvent) {
  dragging.value = false
  e.preventDefault()
  acceptFile(e.dataTransfer?.files?.[0])
}

function clear() {
  emit('update:modelValue', null)
  if (inputRef.value) inputRef.value.value = ''
}
</script>

<template>
  <div class="pdf-field">
    <div class="pdf-label">
      {{ label }}
      <span v-if="required" class="req">*</span>
    </div>
    <div
      class="pdf-drop"
      :class="{ dragging, filled: !!modelValue, err: !!localError }"
      role="button"
      tabindex="0"
      @click="pick"
      @keydown.enter.prevent="pick"
      @dragenter.prevent="dragging = true"
      @dragover.prevent="dragging = true"
      @dragleave.prevent="dragging = false"
      @drop.prevent="onDrop"
    >
      <input
        ref="inputRef"
        class="pdf-input"
        type="file"
        accept="application/pdf,.pdf"
        @change="onInput"
        @click.stop
      />
      <div class="pdf-icon" aria-hidden="true">
        <svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" stroke-width="1.8">
          <path d="M12 16V4M8 8l4-4 4 4" />
          <path d="M4 14v4a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-4" />
        </svg>
      </div>
      <template v-if="modelValue">
        <div class="pdf-name">{{ fileName }}</div>
        <button class="pdf-clear" type="button" @click.stop="clear">更换文件</button>
      </template>
      <template v-else>
        <div class="pdf-title">拖拽 PDF 到此处，或点击选择</div>
        <div class="pdf-hint">{{ hint }}</div>
      </template>
    </div>
    <p v-if="localError" class="error" style="margin: 0.35rem 0 0">{{ localError }}</p>
  </div>
</template>

<style scoped>
.pdf-field {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}
.pdf-label {
  font-weight: 600;
  font-size: 0.92rem;
}
.pdf-drop {
  position: relative;
  border: 1.5px dashed #94a3b8;
  border-radius: 14px;
  background: linear-gradient(180deg, #f8fafc 0%, #f1f5f9 100%);
  padding: 1.15rem 1rem;
  text-align: center;
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s, box-shadow 0.15s;
}
.pdf-drop:hover,
.pdf-drop.dragging {
  border-color: #2563eb;
  background: #eff6ff;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.12);
}
.pdf-drop.filled {
  border-style: solid;
  border-color: #86efac;
  background: #f0fdf4;
}
.pdf-drop.err {
  border-color: #f87171;
  background: #fef2f2;
}
.pdf-input {
  position: absolute;
  inset: 0;
  opacity: 0;
  pointer-events: none;
}
.pdf-icon {
  color: #64748b;
  margin-bottom: 0.35rem;
}
.pdf-drop.dragging .pdf-icon,
.pdf-drop:hover .pdf-icon {
  color: #2563eb;
}
.pdf-title {
  font-weight: 600;
  color: #0f172a;
  font-size: 0.95rem;
}
.pdf-hint,
.pdf-name {
  margin-top: 0.25rem;
  color: #64748b;
  font-size: 0.82rem;
}
.pdf-name {
  color: #166534;
  font-weight: 600;
  word-break: break-all;
}
.pdf-clear {
  margin-top: 0.55rem;
  border: 0;
  background: #fff;
  color: #2563eb;
  border-radius: 999px;
  padding: 0.28rem 0.85rem;
  font-size: 0.82rem;
  font-weight: 600;
  cursor: pointer;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.08);
}
</style>
