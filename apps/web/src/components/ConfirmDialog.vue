<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'

const props = withDefaults(
  defineProps<{
    open: boolean
    title?: string
    message?: string
    confirmText?: string
    cancelText?: string
    danger?: boolean
  }>(),
  {
    title: '请确认',
    message: '',
    confirmText: '确定',
    cancelText: '取消',
    danger: false,
  },
)

const emit = defineEmits<{
  confirm: []
  cancel: []
  'update:open': [value: boolean]
}>()

const panel = ref<HTMLElement | null>(null)

function close() {
  emit('update:open', false)
  emit('cancel')
}

function ok() {
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
  (v) => {
    if (v) document.body.style.overflow = 'hidden'
    else document.body.style.overflow = ''
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
        <div class="dlg-actions">
          <button type="button" class="btn secondary" @click="close">{{ cancelText }}</button>
          <button type="button" class="btn" :class="tone" @click="ok">{{ confirmText }}</button>
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
</style>
