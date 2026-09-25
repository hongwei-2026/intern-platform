<script setup lang="ts">
import { RouterLink } from 'vue-router'

defineProps<{
  to: string
  label?: string
}>()
</script>

<template>
  <p class="ospp-back">
    <RouterLink :to="to">← {{ label || '返回' }}</RouterLink>
  </p>
</template>

<style scoped>
.ospp-back {
  margin: 0 0 1.25rem;
  text-align: left;
}
.ospp-back a {
  color: #1890ff;
  text-decoration: none;
  font-size: 0.92rem;
}
.ospp-back a:hover {
  text-decoration: underline;
}
</style>
