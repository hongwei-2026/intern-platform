<script setup lang="ts">
const props = withDefaults(
  defineProps<{
    open: boolean
    title: string
    paragraphs: string[]
  }>(),
  {},
)

const emit = defineEmits<{
  agree: []
  'update:open': [value: boolean]
}>()

function close() {
  emit('update:open', false)
}

function agree() {
  emit('agree')
  emit('update:open', false)
}
</script>

<template>
  <div v-if="props.open" class="mask" @click.self="close">
    <div class="sheet" role="dialog" aria-modal="true" :aria-label="props.title">
      <header>
        <h2>{{ props.title }}</h2>
        <button type="button" class="x" aria-label="关闭" @click="close">×</button>
      </header>
      <div class="body">
        <p v-for="(paragraph, index) in props.paragraphs" :key="index">{{ paragraph }}</p>
      </div>
      <footer>
        <button type="button" class="ghost" @click="close">先看看</button>
        <button type="button" class="ok" @click="agree">我已阅读并同意</button>
      </footer>
    </div>
  </div>
</template>

<style scoped>
.mask {
  position: fixed;
  inset: 0;
  z-index: 4000;
  background: rgba(15, 23, 42, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px 16px;
}
.sheet {
  width: min(640px, 100%);
  max-height: min(78vh, 640px);
  display: flex;
  flex-direction: column;
  background: #fff;
  border-radius: 14px;
  box-shadow: 0 18px 48px rgba(15, 23, 42, 0.28);
}
header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  border-bottom: 1px solid #eef2f6;
}
h2 { margin: 0; font-size: 1.05rem; color: #1e3a5f; }
.x { border: 0; background: transparent; font-size: 1.4rem; line-height: 1; cursor: pointer; color: #64748b; }
.body { overflow: auto; padding: 16px 18px; }
.body p { margin: 0 0 0.85rem; line-height: 1.75; color: #334155; white-space: pre-wrap; }
footer { display: flex; justify-content: flex-end; gap: 8px; padding: 12px 16px 16px; border-top: 1px solid #eef2f6; }
.ghost, .ok { border-radius: 8px; padding: 8px 14px; font: inherit; cursor: pointer; }
.ghost { background: #fff; border: 1px solid #d0d7e2; color: #1e3a5f; }
.ok { background: #1677ff; border: 0; color: #fff; }
</style>
