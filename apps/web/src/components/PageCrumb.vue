<script setup lang="ts">
import { RouterLink } from 'vue-router'

export type CrumbItem = {
  label: string
  to?: string
}

defineProps<{
  items: CrumbItem[]
}>()
</script>

<template>
  <nav class="ospp-crumb" aria-label="面包屑">
    <template v-for="(item, i) in items" :key="i">
      <span v-if="i > 0" class="sep">›</span>
      <RouterLink v-if="item.to" :to="item.to">{{ item.label }}</RouterLink>
      <span v-else class="cur">{{ item.label }}</span>
    </template>
  </nav>
</template>

<style scoped>
.ospp-crumb {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
  justify-content: flex-start;
  color: #bfbfbf;
  font-size: 13px;
  margin: 0 0 1.25rem;
  text-align: left;
}
.ospp-crumb a {
  color: #8c8c8c;
  text-decoration: none;
}
.ospp-crumb a:hover {
  color: #1890ff;
  text-decoration: underline;
  text-underline-offset: 2px;
}
.sep {
  color: #d9d9d9;
}
.cur {
  color: #595959;
}
</style>
