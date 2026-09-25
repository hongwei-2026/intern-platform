<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
onMounted(() => {
  router.replace({ path: '/projects', query: { tab: 'orgs' } })
})
</script>

<template>
  <div class="page">
    <p class="muted">正在跳转到「查看项目 · 社区列表」…</p>
  </div>
</template>
