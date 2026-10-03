<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'

const props = withDefaults(
  defineProps<{
    open: boolean
    title?: string
    message?: string
    confirmText?: string
    cancelText?: string
    danger?: boolean
    /** 需要原样输入后才能点确定，例如组织全名 */
    expectText?: string
    expectHint?: string
  }>(),
  {
    title: '请确认',
    message: '',
    confirmText: '确定',
    cancelText: '取消',
    danger: false,
    expectText: '',
    expectHint: '',
  },
)

const emit = defineEmits<{
  confirm: []
  cancel: []
  'update:open': [value: boolean]
}>()

const panel = ref<HTMLElement | null>(null)
const inputEl = ref<HTMLInputElement | null>(null)
const typed = ref('')

const needType = computed(() => !!props.expectText)
const matched = computed(() => !needType.value || typed.value === props.expectText)
const hint = computed(() => {
  if (props.expectHint) return props.expectHint
  if (!props.expectText) return ''
  return `请输入「${props.expectText}」确认`
})

function close() {
  emit('update:open', false)
  emit('cancel')
}

function ok() {
  if (!matched.value) return
  emit('update:open', false)
  emit('confirm')
}

function onKey(e: KeyboardEvent) {
  if (!props.open) return
  if (e.key === 'Escape') close()
}

onMounted(() => window.addEventListener('keydown', onKey))
onUnmounted(() => window.removeEventListener('keydown', onKey))

watch(
  () => props.open,
  async (v) => {
    if (v) {
      document.body.style.overflow = 'hidden'
      typed.value = ''
      await nextTick()
      inputEl.value?.focus()
    } else {
      document.body.style.overflow = ''
      typed.value = ''
    }
  },
)

const tone = computed(() => (props.danger ? 'danger' : 'primary'))
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="dlg-mask" @click.self="close">
      <div ref="panel" class="dlg" role="dialog" aria-modal="true" :aria-label="title">
        <h3>{{ title }}</h3>
        <p v-if="message" class="dlg-msg">{{ message }}</p>
        <slot />
        <label v-if="needType" class="dlg-type">
          <span>{{ hint }}</span>
          <input
            ref="inputEl"
            v-model="typed"
            type="text"
            autocomplete="off"
            spellcheck="false"
            @keydown.enter.prevent="ok"
          />
        </label>
        <div class="dlg-actions">
          <button type="button" class="btn secondary" @click="close">{{ cancelText }}</button>
          <button type="button" class="btn" :class="tone" :disabled="!matched" @click="ok">
            {{ confirmText }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.dlg-mask {
  position: fixed;
  inset: 0;
  z-index: 3000;
  background: rgba(15, 23, 42, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1.25rem;
}
.dlg {
  width: min(420px, 100%);
  background: #fff;
  border-radius: 14px;
  padding: 1.25rem 1.35rem 1.15rem;
  box-shadow: 0 24px 64px rgba(15, 23, 42, 0.28);
}
.dlg h3 {
  margin: 0 0 0.55rem;
  font-size: 1.1rem;
  color: #0f172a;
}
.dlg-msg {
  margin: 0 0 1.1rem;
  color: #475569;
  line-height: 1.55;
  white-space: pre-wrap;
}
.dlg-type {
  display: grid;
  gap: 0.4rem;
  margin: 0 0 1.1rem;
  color: #334155;
  font-size: 0.92rem;
}
.dlg-type input {
  width: 100%;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  padding: 0.55rem 0.7rem;
  font: inherit;
}
.dlg-type input:focus {
  outline: none;
  border-color: #1677ff;
  box-shadow: 0 0 0 3px rgba(22, 119, 255, 0.15);
}
.dlg-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.55rem;
}
.btn.danger {
  background: #dc2626;
  border-color: #dc2626;
  color: #fff;
}
.btn.danger:hover {
  background: #b91c1c;
}
.btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}
</style>
