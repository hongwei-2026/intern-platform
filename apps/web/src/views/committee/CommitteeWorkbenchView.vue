<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import api from '@/api/client'
import type { AnnouncementOut, ApplicationOut, CommunityOut, ReviewResponse } from '@/api/types'
import ReviewTimeline from '@/components/ReviewTimeline.vue'
import ToastFeedback from '@/components/ToastFeedback.vue'

const pendingCommunities = ref<CommunityOut[]>([])
const loadErr = ref('')
const busy = ref(false)
const toast = ref<InstanceType<typeof ToastFeedback> | null>(null)

const communityComment = ref('')
const communityMsg = ref('')

const applyForm = ref({
  name: '',
  slug: '',
  description: '',
})
const applyMsg = ref('')

const appId = ref('')
const app = ref<ApplicationOut | null>(null)
const appComment = ref('')
const appMsg = ref('')
const appErr = ref('')

const annForm = ref({
  type: 'general',
  title: '',
  body: '',
  community_id: '',
  project_id: '',
})
const annMsg = ref('')
const annErr = ref('')

async function loadCommunities() {
  loadErr.value = ''
  try {
    const { data } = await api.get<CommunityOut[]>('/communities', {
      params: { status: 'pending' },
    })
    pendingCommunities.value = data
  } catch (e: unknown) {
    loadErr.value = e instanceof Error ? e.message : '加载待审社区失败'
  }
}

async function submitOrgApply() {
  busy.value = true
  applyMsg.value = ''
  try {
    const slug =
      applyForm.value.slug.trim() ||
      applyForm.value.name
        .trim()
        .toLowerCase()
        .replace(/\s+/g, '-')
        .replace(/[^a-z0-9\-]/g, '')
    const { data } = await api.post<CommunityOut>('/communities', {
      name: applyForm.value.name.trim(),
      slug,
      description: applyForm.value.description || null,
    })
    applyMsg.value = `已登记入驻申请 #${data.id}（演示：组委会可代录）`
    applyForm.value = { name: '', slug: '', description: '' }
    await loadCommunities()
    toast.value?.show('入驻申请已提交', 'ok')
  } catch (e: unknown) {
    toast.value?.show(e instanceof Error ? e.message : '提交失败', 'err')
  } finally {
    busy.value = false
  }
}

async function reviewCommunity(id: number, decision: 'approve' | 'reject') {
  busy.value = true
  communityMsg.value = ''
  try {
    const { data } = await api.post<CommunityOut>(`/communities/${id}/review`, {
      decision,
      comment: communityComment.value || null,
    })
    communityMsg.value = `社区 #${id} 已${decision === 'approve' ? '通过' : '拒绝'}${
      data.invite_code ? `，组织码：${data.invite_code}` : ''
    }`
    toast.value?.show(communityMsg.value, decision === 'approve' ? 'ok' : 'err')
    await loadCommunities()
  } catch (e: unknown) {
    loadErr.value = e instanceof Error ? e.message : '审核失败'
    toast.value?.show(loadErr.value, 'err')
  } finally {
    busy.value = false
  }
}

async function loadApp() {
  appErr.value = ''
  appMsg.value = ''
  app.value = null
  const id = Number(appId.value)
  if (!id) {
    appErr.value = '请输入申请 ID'
    return
  }
  try {
    const { data } = await api.get<ApplicationOut>(`/applications/${id}`)
    app.value = data
  } catch (e: unknown) {
    appErr.value = e instanceof Error ? e.message : '加载失败'
  }
}

async function reviewApp(decision: 'approve' | 'reject') {
  if (!app.value) return
  busy.value = true
  appErr.value = ''
  appMsg.value = ''
  try {
    const { data } = await api.post<ReviewResponse>(
      `/applications/${app.value.id}/reviews`,
      {
        decision,
        comment: appComment.value || null,
        version: app.value.version,
      },
    )
    appMsg.value = `${decision === 'approve' ? '已通过' : '已拒绝'}：${data.from_status} → ${data.to_status}`
    await loadApp()
  } catch (e: unknown) {
    appErr.value = e instanceof Error ? e.message : '审核失败'
  } finally {
    busy.value = false
  }
}

async function createAnnouncement() {
  annErr.value = ''
  annMsg.value = ''
  busy.value = true
  try {
    const { data } = await api.post<AnnouncementOut>('/announcements', {
      type: annForm.value.type,
      title: annForm.value.title,
      body: annForm.value.body || null,
      community_id: annForm.value.community_id ? Number(annForm.value.community_id) : null,
      project_id: annForm.value.project_id ? Number(annForm.value.project_id) : null,
      is_public: true,
    })
    annMsg.value = `公示已发布 #${data.id}`
    annForm.value.title = ''
    annForm.value.body = ''
  } catch (e: unknown) {
    annErr.value = e instanceof Error ? e.message : '发布失败'
  } finally {
    busy.value = false
  }
}

onMounted(loadCommunities)
</script>

<template>
  <div class="page">
    <ToastFeedback ref="toast" />
    <h1 class="page-title">组委会工作台</h1>
    <p class="page-desc">全站统筹：社区入驻审核、申请终审、公示与账号绑定。单个社区的导师/项目由社区管理员管理。</p>

    <div class="card" style="margin-bottom: 1.5rem">
      <h3 style="margin-top: 0">登记组织入驻（组委会）</h3>
      <p class="muted">新组织入驻申请由组委会受理；通过后发放组织码并指定社区管理员。</p>
      <form class="form" style="max-width: 28rem" @submit.prevent="submitOrgApply">
        <label>
          组织名称 <span class="req">*</span>
          <input v-model="applyForm.name" required placeholder="如：内核社区" />
        </label>
        <label>
          标识（英文，可选）
          <input v-model="applyForm.slug" placeholder="自动生成" />
        </label>
        <label>
          简介
          <textarea v-model="applyForm.description" rows="2" />
        </label>
        <button class="btn" type="submit" :disabled="busy">提交入驻申请</button>
      </form>
      <p v-if="applyMsg" class="success-msg">{{ applyMsg }}</p>
    </div>

    <div class="card" style="margin-bottom: 1.5rem">
      <h3 style="margin-top: 0">学生账号绑定</h3>
      <p class="muted">开通 GitHub、Gitee、GitCode、GitLink、俱乐部 Gitea 后，学生可一键官方授权绑定。</p>
      <RouterLink class="btn" to="/committee/oauth">去开通账号绑定</RouterLink>
    </div>

    <p v-if="loadErr" class="error">{{ loadErr }}</p>

    <h2>待审社区</h2>
    <label class="form" style="margin-bottom: 0.75rem">
      审核意见（可选）
      <input v-model="communityComment" />
    </label>
    <p v-if="communityMsg" class="success-msg">{{ communityMsg }}</p>
    <div v-if="!pendingCommunities.length" class="muted">暂无待审社区。</div>
    <div v-else class="stack">
      <div v-for="c in pendingCommunities" :key="c.id" class="card">
        <h3>{{ c.name }} <span class="muted">({{ c.slug }})</span></h3>
        <p class="muted">{{ c.description || '暂无简介' }}</p>
        <div class="btn-row">
          <button class="btn success" type="button" :disabled="busy" @click="reviewCommunity(c.id, 'approve')">
            通过
          </button>
          <button class="btn danger" type="button" :disabled="busy" @click="reviewCommunity(c.id, 'reject')">
            拒绝
          </button>
        </div>
      </div>
    </div>

    <hr class="hr" />

    <h2>申请审核</h2>
    <p class="muted">输入申请 ID 进行组委会节点审核。</p>
    <form class="form" @submit.prevent="loadApp">
      <label>
        申请 ID
        <input v-model="appId" type="number" min="1" required />
      </label>
      <button class="btn" type="submit">加载</button>
    </form>
    <p v-if="appErr" class="error">{{ appErr }}</p>
    <p v-if="appMsg" class="success-msg">{{ appMsg }}</p>
    <template v-if="app">
      <div class="card">
        <h3>申请 #{{ app.id }}</h3>
        <p class="muted">状态 {{ app.status }} · 节点 {{ app.current_node }}</p>
      </div>
      <ReviewTimeline :application="app" />
      <label class="form">
        审核意见
        <textarea v-model="appComment" />
      </label>
      <div class="btn-row">
        <button class="btn success" type="button" :disabled="busy" @click="reviewApp('approve')">通过</button>
        <button class="btn danger" type="button" :disabled="busy" @click="reviewApp('reject')">拒绝</button>
      </div>
    </template>

    <hr class="hr" />

    <h2>发布公示</h2>
    <form class="form wide" @submit.prevent="createAnnouncement">
      <label>
        类型
        <select v-model="annForm.type">
          <option value="general">一般</option>
          <option value="selection">选拔</option>
          <option value="final">结项</option>
        </select>
      </label>
      <label>
        标题
        <input v-model="annForm.title" required />
      </label>
      <label>
        正文
        <textarea v-model="annForm.body" />
      </label>
      <label>
        社区 ID（可选）
        <input v-model="annForm.community_id" type="number" />
      </label>
      <label>
        项目 ID（可选）
        <input v-model="annForm.project_id" type="number" />
      </label>
      <p v-if="annErr" class="error">{{ annErr }}</p>
      <p v-if="annMsg" class="success-msg">{{ annMsg }}</p>
      <button class="btn" type="submit" :disabled="busy">发布</button>
    </form>
  </div>
</template>
