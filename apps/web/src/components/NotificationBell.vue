<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import api from '@/api/client'
import type { ApplicationOut, NotificationListOut, NotificationOut } from '@/api/types'
import { useAuthStore } from '@/stores/auth'
import { statusLabel, statusTone } from '@/utils/statusLabel'

const auth = useAuthStore()
const open = ref(false)
const tab = ref<'notify' | 'apps'>('notify')
const notes = ref<NotificationOut[]>([])
const unread = ref(0)
const apps = ref<ApplicationOut[]>([])
const loading = ref(false)

const hasUnread = computed(() => unread.value > 0)

async function load() {
  if (!auth.isLoggedIn) return
  loading.value = true
  try {
    const [n, a] = await Promise.all([
      api.get<NotificationListOut>('/notifications'),
      api.get<ApplicationOut[]>('/applications/mine').catch(() => ({ data: [] as ApplicationOut[] })),
    ])
    notes.value = n.data.items
    unread.value = n.data.unread_count
    apps.value = a.data
  } catch {
    /* ignore */
  } finally {
    loading.value = false
  }
}

async function markAll() {
  await api.post('/notifications/read-all')
  unread.value = 0
  notes.value = notes.value.map((x) => ({ ...x, is_read: 1 }))
}

async function openNote(n: NotificationOut) {
  if (!n.is_read) {
    await api.post(`/notifications/${n.id}/read`).catch(() => null)
    n.is_read = 1
    unread.value = Math.max(0, unread.value - 1)
  }
  open.value = false
}

function onDocClick(e: MouseEvent) {
  const t = e.target as HTMLElement | null
  if (!t?.closest('.notify-wrap')) open.value = false
}

onMounted(() => {
  void load()
  document.addEventListener('click', onDocClick)
})
onUnmounted(() => document.removeEventListener('click', onDocClick))

watch(
  () => auth.isLoggedIn,
  (v) => {
    if (v) void load()
    else {
      notes.value = []
      apps.value = []
      unread.value = 0
    }
  },
)

defineExpose({ refresh: load })
</script>

<template>
  <div v-if="auth.isLoggedIn" class="notify-wrap">
    <button
      class="notify-bell"
      type="button"
      aria-label="消息通知"
      :aria-expanded="open"
      @click.stop="open = !open; if (open) load()"
    >
      <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">
        <path
          fill="currentColor"
          d="M12 22a2.5 2.5 0 0 0 2.45-2h-4.9A2.5 2.5 0 0 0 12 22Zm6-6V11a6 6 0 1 0-12 0v5l-2 2v1h16v-1l-2-2Z"
        />
      </svg>
      <span v-if="hasUnread" class="notify-dot">{{ unread > 9 ? '9+' : unread }}</span>
    </button>

    <div v-show="open" class="notify-panel" role="dialog" aria-label="通知与申请进度" @click.stop>
      <div class="notify-tabs">
        <button type="button" :class="{ active: tab === 'notify' }" @click="tab = 'notify'">
          审核通知
          <span v-if="hasUnread" class="mini-badge">{{ unread }}</span>
        </button>
        <button
          v-if="auth.canApplyProjects"
          type="button"
          :class="{ active: tab === 'apps' }"
          @click="tab = 'apps'"
        >
          我的申请
        </button>
        <RouterLink
          v-else-if="auth.isMentor"
          class="notify-workbench"
          to="/mentor"
          @click="open = false"
        >导师台</RouterLink>
      </div>

      <div v-if="tab === 'notify'" class="notify-body">
        <div class="notify-toolbar">
          <span class="muted">项目审核结果会出现在这里</span>
          <button v-if="hasUnread" class="linkish" type="button" @click="markAll">全部已读</button>
        </div>
        <p v-if="loading" class="muted pad">加载中…</p>
        <p v-else-if="!notes.length" class="muted pad">暂无通知</p>
        <RouterLink
          v-for="n in notes"
          :key="n.id"
          class="notify-item"
          :class="{ unread: !n.is_read }"
          :to="
            auth.isStaff && n.application_id
              ? '/mentor'
              : n.application_id
                ? `/student/applications/${n.application_id}`
                : n.project_id
                  ? `/projects/${n.project_id}`
                  : auth.canApplyProjects
                    ? '/me?tab=applications'
                    : auth.portalHome()
          "
          @click="openNote(n)"
        >
          <strong>{{ n.title }}</strong>
          <span class="muted">{{ n.body }}</span>
        </RouterLink>
      </div>

      <div v-else-if="auth.canApplyProjects" class="notify-body">
        <div class="notify-toolbar">
          <span class="muted">点击可看该项目审核进度</span>
          <RouterLink class="linkish" to="/me?tab=applications" @click="open = false">全部申请</RouterLink>
        </div>
        <p v-if="loading" class="muted pad">加载中…</p>
        <p v-else-if="!apps.length" class="muted pad">还没有申请，去项目列表看看吧</p>
        <RouterLink
          v-for="a in apps"
          :key="a.id"
          class="notify-item"
          :to="`/student/applications/${a.id}`"
          @click="open = false"
        >
          <strong>{{ a.project_title || `项目 #${a.project_id}` }}</strong>
          <span>
            <span class="badge" :class="statusTone(a.status)">{{ statusLabel(a.status) }}</span>
            <span class="muted" style="margin-left: 0.4rem">申请 #{{ a.id }}</span>
          </span>
        </RouterLink>
      </div>
    </div>
  </div>
</template>
