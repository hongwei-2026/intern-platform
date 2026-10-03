<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import api from '@/api/client'
import type { ApplicationOut, CommunityOut, ProjectOut } from '@/api/types'
import PageCrumb from '@/components/PageCrumb.vue'
import PdfDropZone from '@/components/PdfDropZone.vue'
import ToastFeedback from '@/components/ToastFeedback.vue'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const toast = ref<InstanceType<typeof ToastFeedback> | null>(null)

const project = ref<ProjectOut | null>(null)
const community = ref<CommunityOut | null>(null)
const error = ref('')
const applyError = ref('')
const submitting = ref(false)
const blocked = ref('')
const hold = ref('')

const statement = ref('')
const resumeFile = ref<File | null>(null)
const designFile = ref<File | null>(null)
const submitNow = ref(true)

const projectId = computed(() => String(route.params.id))
const backTo = computed(() => `/projects/${projectId.value}`)
const crumbs = computed(() => [
  { label: '查看项目', to: '/projects' },
  ...(community.value ? [{ label: community.value.name, to: `/communities/${community.value.slug}` }] : []),
  { label: project.value?.title || '任务介绍', to: backTo.value },
  { label: '填写申请书' },
])

async function load() {
  error.value = ''
  blocked.value = ''
  hold.value = ''
  if (!auth.isLoggedIn) {
    router.replace({ name: 'login', query: { redirect: route.fullPath, role: 'student' } })
    return
  }
  if (!auth.canApplyProjects) {
    blocked.value = '当前账号不能申请项目，请使用学生账号。'
    return
  }
  try {
    const { data } = await api.get<ProjectOut>(`/projects/${projectId.value}`)
    project.value = data
    const { data: orgs } = await api.get<CommunityOut[]>('/communities', { params: { status: 'approved' } })
    community.value = orgs.find((item) => item.id === data.community_id) || null
    const { data: mine } = await api.get<ApplicationOut | null>(`/projects/${projectId.value}/my-application`)
    const reapply = !!mine && ['rejected', 'withdrawn', 'draft'].includes(mine.status)
    if (mine && !reapply) {
      router.replace(`/student/applications/${mine.id}?tab=task`)
      return
    }
    const { data: allMine } = await api.get<ApplicationOut[]>('/applications/mine')
    const currentId = Number(projectId.value)
    const finished = new Set(['rejected', 'withdrawn', 'completed', 'community_final_review', 'committee_final_review', 'draft'])
    const other = allMine.find((item) => item.project_id !== currentId && !finished.has(item.status))
    if (other) {
      hold.value = `你正在进行「${other.project_title || '另一个任务'}」，这个任务结束前不能再接取。`
    }
    const taken = data.seats_taken ?? (data.assignees || []).length
    const avail = data.seats_available ?? Math.max(0, (data.quota || 0) - taken)
    if (data.status !== 'published' || avail <= 0) {
      blocked.value = '这个任务现在不能申请，名额已满或尚未开放。'
    }
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : '加载失败'
  }
}

async function uploadPdf(file: File): Promise<string> {
  const fd = new FormData()
  fd.append('file', file)
  const { data } = await api.post<{ url: string }>('/uploads/pdf', fd)
  return data.url
}

async function apply() {
  if (hold.value) return
  applyError.value = ''
  if (!resumeFile.value || !designFile.value) {
    applyError.value = '请上传个人简历 PDF 与项目设计 PDF'
    toast.value?.show(applyError.value, 'err')
    return
  }
  if (!resumeFile.value.name.toLowerCase().endsWith('.pdf') || !designFile.value.name.toLowerCase().endsWith('.pdf')) {
    applyError.value = '简历与项目设计均须为 PDF'
    toast.value?.show(applyError.value, 'err')
    return
  }
  submitting.value = true
  try {
    const resumeUrl = await uploadPdf(resumeFile.value)
    const designUrl = await uploadPdf(designFile.value)
    const { data } = await api.post<ApplicationOut>(`/projects/${projectId.value}/applications`, {
      statement: statement.value || null,
      attachment_url: resumeUrl,
      extra_fields: { resume_pdf: resumeUrl, design_pdf: designUrl },
      submit: submitNow.value,
    })
    toast.value?.show('申请提交成功', 'ok')
    router.push(`/student/applications/${data.id}?tab=task`)
  } catch (e: unknown) {
    applyError.value = e instanceof Error ? e.message : '申请失败'
    toast.value?.show(applyError.value, 'err')
  } finally {
    submitting.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="apply-page">
    <ToastFeedback ref="toast" />
    <PageCrumb :items="crumbs" />
    <p v-if="error" class="error">{{ error }}</p>
    <p v-else-if="blocked" class="error">{{ blocked }} <RouterLink :to="backTo">返回任务</RouterLink></p>
    <p v-else-if="!project" class="muted">加载中…</p>
    <form v-else class="sheet" @submit.prevent="apply">
      <header>
        <p class="kicker">{{ community?.name || '开源实习' }}</p>
        <h1>填写申请书</h1>
        <p class="title">{{ project.title }}</p>
        <p class="tip">提交后进入导师 → 社区 → 组委会三级审核。附件统一为 PDF。</p>
      </header>
      <div class="cols">
        <label>
          申请陈述 <span>选填</span>
          <textarea v-model="statement" rows="8" placeholder="可选：补充背景、方案、里程碑与时间安排" />
        </label>
        <div class="files">
          <PdfDropZone v-model="resumeFile" label="个人简历（PDF）" required />
          <PdfDropZone v-model="designFile" label="项目设计（PDF）" required />
          <p class="template">
            没有模板？
            <a href="/samples/project-design-template.pdf" download="项目申请书示例.pdf">下载项目申请书示例 PDF</a>
          </p>
        </div>
      </div>
      <label class="check"><input v-model="submitNow" type="checkbox" /> 立即提交审核</label>
      <p v-if="hold" class="hold">{{ hold }}</p>
      <p v-if="applyError" class="error">{{ applyError }}</p>
      <div class="acts">
        <button class="btn" type="submit" :disabled="submitting || !!hold">{{ submitting ? '提交中…' : '确认提交' }}</button>
        <RouterLink class="btn ghost" :to="backTo">返回任务</RouterLink>
      </div>
    </form>
  </div>
</template>

<style scoped>
.apply-page { width: min(1100px, 100%); margin: 0 auto; padding: 20px clamp(16px, 3vw, 36px) 48px; box-sizing: border-box; }
.sheet { border: 1px solid #eef2f6; border-radius: 14px; padding: 22px 24px 20px; background: #fff; }
.kicker { margin: 0; color: #1677ff; font-size: 0.85rem; font-weight: 700; }
h1 { margin: 0.2rem 0 0.35rem; color: #1e3a5f; font-size: 1.6rem; }
.title { margin: 0; color: #1e3a5f; font-weight: 700; }
.tip { margin: 0.45rem 0 0; color: #64748b; }
.cols { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 22px; margin-top: 18px; }
label { display: flex; flex-direction: column; gap: 8px; color: #1e3a5f; font-weight: 600; }
label span { font-weight: 400; color: #8c8c8c; }
textarea { width: 100%; box-sizing: border-box; border: 1px solid #d0d7e2; border-radius: 10px; padding: 10px 12px; font: inherit; font-weight: 400; min-height: 220px; resize: vertical; }
.files { display: flex; flex-direction: column; gap: 12px; }
.template { margin: 0; color: #64748b; font-weight: 400; }
.template a { color: #1677ff; }
.check { flex-direction: row; align-items: center; margin-top: 14px; font-weight: 500; }
.acts { display: flex; gap: 10px; margin-top: 16px; justify-content: center; }
.btn { display: inline-flex; align-items: center; justify-content: center; background: #1677ff; color: #fff; border: 0; border-radius: 8px; padding: 8px 16px; text-decoration: none; font: inherit; cursor: pointer; }
.btn:disabled { background: #d9d9d9; color: #8c8c8c; cursor: not-allowed; }
.hold { margin: 14px 0 0; color: #b45309; text-align: center; }
.btn.ghost { background: #fff; color: #1e3a5f; border: 1px solid #d0d7e2; }
.error { color: #dc2626; }
.muted { color: #64748b; }
@media (max-width: 800px) { .cols { grid-template-columns: 1fr; } }
</style>
