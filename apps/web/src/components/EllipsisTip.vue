<script setup lang="ts">
import { ref } from 'vue'

const props = defineProps<{
  text?: string | null
  lines?: number
}>()

const open = ref(false)
const x = ref(0)
const y = ref(0)

function show(e: MouseEvent) {
  const full = (props.text || '').trim()
  if (!full || full === '—') return
  const el = e.currentTarget as HTMLElement
  const r = el.getBoundingClientRect()
  x.value = Math.min(r.left, window.innerWidth - 320)
  y.value = r.top
  open.value = true
}

function hide() {
  open.value = false
}
</script>

<template>
  <span class="ellipsis-root">
  <span
    class="ellipsis"
    :style="{ WebkitLineClamp: String(lines || 1) }"
    :class="{ multi: (lines || 1) > 1 }"
    @mouseenter="show"
    @mouseleave="hide"
  >{{ text || '—' }}</span>
  <Teleport to="body">
    <div
      v-if="open"
      class="ellipsis-tip"
      role="tooltip"
      :style="{ left: x + 'px', top: y + 'px' }"
    >
      {{ text }}
    </div>
  </Teleport>
  </span>
</template>

<style scoped>
.ellipsis-root {
  display: inline-block;
  max-width: 100%;
  vertical-align: top;
}
.ellipsis {
  display: block;
  max-width: 16rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  cursor: default;
}
.ellipsis.multi {
  display: -webkit-box;
  -webkit-box-orient: vertical;
  white-space: normal;
}
.ellipsis-tip {
  position: fixed;
  z-index: 4000;
  transform: translateY(calc(-100% - 10px));
  max-width: min(22rem, 70vw);
  max-height: 16rem;
  overflow: auto;
  padding: 0.6rem 0.75rem;
  background: #fff;
  color: #1f2937;
  font-size: 0.82rem;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
  border-radius: 8px;
  box-shadow: 0 10px 28px rgba(15, 23, 42, 0.18);
  border: 1px solid #e5e7eb;
  pointer-events: none;
}
</style>
