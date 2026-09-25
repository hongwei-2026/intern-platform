<script setup lang="ts">
import { ref } from 'vue'

const props = withDefaults(
  defineProps<{
    modelValue: string[]
    label?: string
    max?: number
  }>(),
  { label: '社区标签', max: 12 },
)

const emit = defineEmits<{
  'update:modelValue': [string[]]
}>()

const draft = ref('')

function add() {
  const t = draft.value.trim().replace(/\s+/g, ' ')
  if (!t) return
  const next = [...props.modelValue]
  if (!next.includes(t) && next.length < props.max) next.push(t.slice(0, 24))
  emit('update:modelValue', next)
  draft.value = ''
}

function remove(tag: string) {
  emit(
    'update:modelValue',
    props.modelValue.filter((x) => x !== tag),
  )
}

function onKey(e: KeyboardEvent) {
  if (e.key === 'Enter' || e.key === ',') {
    e.preventDefault()
    add()
  }
}
</script>

<template>
  <div class="tags-ed">
    <div v-if="label" class="lbl">{{ label }}</div>
    <div class="chips">
      <span v-for="t in modelValue" :key="t" class="chip">
        {{ t }}
        <button type="button" aria-label="删除" @click="remove(t)">×</button>
      </span>
      <input
        v-model="draft"
        type="text"
        maxlength="24"
        :placeholder="modelValue.length ? '继续添加…' : '输入后回车，如：内核、驱动、镜像'"
        @keydown="onKey"
      />
      <button class="btn sm secondary" type="button" @click="add">添加</button>
    </div>
    <p class="hint">回车或逗号添加，最多 {{ max }} 个；保存后显示在公开组织主页。</p>
  </div>
</template>

<style scoped>
.tags-ed {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}
.lbl {
  font-size: 0.86rem;
  color: #595959;
  font-weight: 600;
}
.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  align-items: center;
  padding: 0.55rem 0.65rem;
  border: 1px solid #f0f0f0;
  border-radius: 8px;
  background: #fafafa;
}
.chip {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  padding: 2px 8px;
  border-radius: 4px;
  background: #e6f4ff;
  color: #1677ff;
  font-size: 0.82rem;
  font-weight: 600;
}
.chip button {
  border: none;
  background: transparent;
  color: #69b1ff;
  cursor: pointer;
  font-size: 1rem;
  line-height: 1;
  padding: 0;
}
.chips input {
  flex: 1;
  min-width: 8rem;
  border: none;
  background: transparent;
  outline: none;
  font-size: 0.88rem;
}
.hint {
  margin: 0;
  font-size: 0.78rem;
  color: #8c8c8c;
}
</style>
