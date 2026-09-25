<script setup lang="ts">
import { onUnmounted, ref } from 'vue'

const visible = ref(false)
const text = ref('')
const kind = ref<'ok' | 'err'>('ok')
let timer: number | undefined

function show(message: string, type: 'ok' | 'err' = 'ok', ms = 3200) {
  text.value = message
  kind.value = type
  visible.value = true
  if (timer !== undefined) window.clearTimeout(timer)
  timer = window.setTimeout(() => {
    visible.value = false
  }, ms)
}

onUnmounted(() => {
  if (timer !== undefined) window.clearTimeout(timer)
})

defineExpose({ show })
</script>

<template>
  <Teleport to="body">
    <div v-if="visible" class="toast" :class="kind" role="status">{{ text }}</div>
  </Teleport>
</template>

<style scoped>
.toast {
  position: fixed;
  top: 72px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 2000;
  min-width: 220px;
  max-width: min(520px, 92vw);
  padding: 0.75rem 1.1rem;
  border-radius: 10px;
  font-weight: 600;
  font-size: 0.92rem;
  box-shadow: 0 12px 32px rgba(15, 23, 42, 0.18);
  text-align: center;
}
.toast.ok {
  background: #ecfdf5;
  color: #065f46;
  border: 1px solid #a7f3d0;
}
.toast.err {
  background: #fef2f2;
  color: #991b1b;
  border: 1px solid #fecaca;
}
</style>
