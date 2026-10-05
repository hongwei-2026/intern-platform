<script setup lang="ts">
import { computed } from 'vue'
import { unpackLiaison } from '@/utils/liaisonBody'

const props = defineProps<{
  body: string
  mine?: boolean
  name?: string
  time?: string
}>()

const parsed = computed(() => unpackLiaison(props.body))
</script>

<template>
  <article class="bubble" :class="{ mine }">
    <small v-if="name || time">{{ name }}<template v-if="time"> · {{ time }}</template></small>
    <p v-if="parsed.text">{{ parsed.text }}</p>
    <template v-for="(file, i) in parsed.files" :key="i">
      <img v-if="file.type === 'image' && file.url" :src="file.url" alt="" />
      <a
        v-else-if="file.type === 'file' && file.url && file.url.startsWith('/api/v1/uploads/files/')"
        :href="file.url"
        :download="file.name || '材料'"
        target="_blank"
        rel="noopener"
      >下载 {{ file.name || '文件' }}</a>
      <table v-else-if="file.type === 'table'">
        <tr v-for="(row, ri) in file.rows" :key="ri"><td v-for="(cell, ci) in row" :key="ci">{{ cell }}</td></tr>
      </table>
    </template>
  </article>
</template>

<style scoped>
.bubble { background: #fff; border: 1px solid #d5deea; border-radius: 8px; padding: 8px 10px; }
.bubble.mine { border-color: #91caff; background: #f0f7ff; }
small { display: block; color: #64748b; font-size: 0.78rem; }
p { margin: 4px 0 0; white-space: pre-wrap; }
img { display: block; max-width: min(100%, 360px); max-height: 220px; object-fit: contain; border-radius: 8px; margin-top: 8px; background: #f7f9fc; }
a { display: inline-block; margin-top: 8px; color: #1677ff; }
table { width: 100%; border-collapse: collapse; margin-top: 8px; }
td { border: 1px solid #d0d7e2; padding: 4px 6px; }
</style>
