<script setup lang="ts">
import { onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()

onMounted(() => {
  const provider = String(route.query.provider || 'gitcode')
  router.replace(`/me/bind/${provider}`)
})
</script>

<template>
  <div class="link-page">
    <p class="link-desc" style="text-align: center; padding-top: 80px">正在进入绑定页…</p>
  </div>
</template>
