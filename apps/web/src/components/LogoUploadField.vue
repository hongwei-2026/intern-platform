<script setup lang="ts">
import { computed, ref } from 'vue'
import api from '@/api/client'

const props = withDefaults(
  defineProps<{
    modelValue: string
    label?: string
    hint?: string
  }>(),
  {
    label: '社区 Logo',
    hint: '支持 JPG / PNG / WebP / GIF，最大 5MB',
  },
)

const emit = defineEmits<{
  'update:modelValue': [string]
}>()

const busy = ref(false)
const err = ref('')
const inputRef = ref<HTMLInputElement | null>(null)

const preview = computed(() => props.modelValue || '')

function pick() {
  inputRef.value?.click()
}

async function onFile(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (inputRef.value) inputRef.value.value = ''
  if (!file) return
  err.value = ''
  busy.value = true
  try {
    const fd = new FormData()
    fd.append('file', file)
    const { data } = await api.post<{ url: string }>('/uploads/image', fd)
    emit('update:modelValue', data.url)
  } catch (e: unknown) {
    err.value = e instanceof Error ? e.message : '上传失败'
  } finally {
    busy.value = false
  }
}

function clear() {
  emit('update:modelValue', '')
}
</script>

<template>
  <div class="logo-up">
    <div class="lbl">{{ label }}</div>
    <div class="row">
      <div class="prev" aria-hidden="true">
        <img v-if="preview" :src="preview" alt="" />
        <span v-else>Logo</span>
      </div>
      <div class="acts">
        <button class="btn sm" type="button" :disabled="busy" @click="pick">
          {{ busy ? '上传中…' : preview ? '更换图片' : '上传图片' }}
        </button>
        <button v-if="preview" class="btn sm secondary" type="button" :disabled="busy" @click="clear">
          清除
        </button>
        <p class="hint">{{ hint }}</p>
        <p v-if="err" class="err">{{ err }}</p>
      </div>
    </div>
    <input ref="inputRef" type="file" accept="image/jpeg,image/png,image/webp,image/gif" hidden @change="onFile" />
  </div>
</template>

<style scoped>
.logo-up {
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
}
.lbl {
  font-size: 0.86rem;
  color: #595959;
  font-weight: 600;
}
.row {
  display: flex;
  gap: 1rem;
  align-items: center;
}
.prev {
  width: 72px;
  height: 72px;
  border-radius: 10px;
  border: 1px solid #f0f0f0;
  background: #fafafa;
  display: grid;
  place-items: center;
  overflow: hidden;
  color: #bfbfbf;
  font-size: 0.78rem;
  font-weight: 700;
  flex-shrink: 0;
}
.prev img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.acts {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
  align-items: center;
}
.hint {
  margin: 0;
  width: 100%;
  font-size: 0.78rem;
  color: #8c8c8c;
}
.err {
  margin: 0;
  width: 100%;
  color: #cf1322;
  font-size: 0.82rem;
}
</style>
