<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import api from '@/api/client'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import type { ProjectOut } from '@/api/types'
import { projectStatusLabel, statusTone } from '@/utils/statusLabel'

const projects = ref<ProjectOut[]>([])
const error = ref('')
const busy = ref(false)
const closeOpen = ref(false)
const closeId = ref<number | null>(null)

async function load() {
  error.value = ''
  try {
    const { data } = await api.get<ProjectOut[]>('/projects', { params: { owned: true } })
    projects.value = data.sort((a, b) => b.id - a.id)
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : '加载失败'
  }
}

async function publish(id: number) {
  busy.value = true
  try {
    await api.post(`/projects/${id}/publish`)
    await load()
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : '发布失败'
  } finally {
    busy.value = false
  }
}

onMounted(load)

function closeTake(id: number) {
  closeId.value = id
  closeOpen.value = true
}

async function confirmCloseTake() {
  const id = closeId.value
  closeId.value = null
  if (!id) return
  busy.value = true
  try {
    await api.post(`/projects/${id}/close`)
    await load()
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : '关闭失败'
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="page wide">
    <ConfirmDialog
      :open="closeOpen"
      title="关闭接取"
      message="关闭后不能再接取，项目介绍仍可查看。确定关闭？"
      confirm-text="关闭接取"
      cancel-text="取消"
      danger
      @update:open="closeOpen = $event"
      @cancel="closeId = null"
      @confirm="confirmCloseTake"
    />
    <header class="head">
      <div>
        <p class="eyebrow">导师工作台</p>
        <h1 class="page-title">我负责的项目</h1>
        <p class="muted">
          这里只列出<strong>组织指派给你</strong>的项目。新建与改派请由社区管理员在
          <RouterLink to="/org">组织工作台</RouterLink> 操作。
        </p>
      </div>
      <RouterLink class="btn secondary" to="/mentor">← 返回待审申请</RouterLink>
    </header>

    <p v-if="error" class="error">{{ error }}</p>

    <div v-if="!projects.length" class="empty card">
      <p>暂无指派给你的项目。</p>
      <p class="muted">请联系社区管理员创建项目并指定你为负责导师。</p>
    </div>

    <div v-else class="proj-grid">
      <article v-for="p in projects" :key="p.id" class="card proj">
        <div class="proj-top">
          <h3>
            <RouterLink :to="`/projects/${p.id}`">{{ p.title }}</RouterLink>
          </h3>
          <span class="badge" :class="statusTone(p.status)">{{ projectStatusLabel(p.status) }}</span>
        </div>
        <p class="muted">{{ p.summary || '暂无摘要' }}</p>
        <div class="btn-row">
          <RouterLink class="btn secondary sm" :to="`/projects/${p.id}`">查看详情</RouterLink>
          <button
            v-if="p.status === 'draft'"
            class="btn sm"
            type="button"
            :disabled="busy"
            @click="publish(p.id)"
          >
            发布上线
          </button>
          <button
            v-if="p.status === 'published'"
            class="btn sm secondary"
            type="button"
            :disabled="busy"
            @click="closeTake(p.id)"
          >
            关闭接取
          </button>
        </div>
      </article>
    </div>
  </div>
</template>

<style scoped>
.page.wide {
  max-width: none;
  width: 100%;
}
.head {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
  margin-bottom: 1.25rem;
}
.eyebrow {
  margin: 0 0 0.25rem;
  font-size: 0.8rem;
  font-weight: 700;
  color: #1e3a5f;
}
.proj-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 1rem;
}
.proj-top {
  display: flex;
  justify-content: space-between;
  gap: 0.75rem;
  align-items: flex-start;
  margin-bottom: 0.45rem;
}
.proj h3 {
  margin: 0;
  font-size: 1.05rem;
}
.empty {
  text-align: center;
  padding: 2rem 1rem;
}
</style>
