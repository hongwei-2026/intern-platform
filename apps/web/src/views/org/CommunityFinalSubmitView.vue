<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import api from '@/api/client'
import type { ApplicationOut } from '@/api/types'
import ZipDropZone from '@/components/ZipDropZone.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import AgreementDialog from '@/components/AgreementDialog.vue'

const props = defineProps<{ applicationId?: number | null; embedded?: boolean }>()
const route = useRoute()
const router = useRouter()
const app = ref<ApplicationOut | null>(null)
const text = ref('')
const designDoc = ref('')
const codeUrl = ref('')
const zipUrl = ref('')
const zipName = ref('')
const agreed = ref(false)
const agreeOpen = ref(false)
const finalTerms = [
  '一、本协议适用于社区向组委会报送结项。你提交的说明、交付件、设计文档链接和代码链接，只用于组委会接收结项与结项公示。',
  '二、请确认材料与学生验收内容一致，且不包含账号密码或其他无关隐私。',
  '三、勾选同意并提交，即表示你已阅读本协议，并授权组委会按上述范围使用这些材料。未同意本协议，不能提交结项。',
]

function acceptTerms() {
  agreed.value = true
}
const busy = ref(false)
const error = ref('')
const confirmOpen = ref(false)

const id = () => (props.applicationId ? String(props.applicationId) : String(route.params.id || ''))

const ready = computed(() => app.value?.status === 'community_final_review')

async function load() {
  error.value = ''
  const current = id()
  if (!current) {
    app.value = null
    return
  }
  try {
    const { data } = await api.get<ApplicationOut>(`/applications/${current}`)
    app.value = data
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : '加载失败'
  }
}

watch(() => props.applicationId, () => void load())

function requestSubmit() {
  if (!ready.value) return
  if (!text.value.trim()) {
    error.value = '请填写结项说明'
    return
  }
  if (!zipUrl.value) {
    error.value = '请上传交付件（zip）'
    return
  }
  if (!agreed.value) {
    error.value = '请先阅读并同意《结项报送协议》'
    return
  }
  error.value = ''
  confirmOpen.value = true
}

async function doSubmit() {
  busy.value = true
  error.value = ''
  try {
    await api.post(`/applications/${id()}/community-final`, {
      note: text.value.trim(),
      attachment_url: zipUrl.value,
      attachment_name: zipName.value || null,
      report_url: designDoc.value.trim() || null,
      code_url: codeUrl.value.trim() || null,
    })
    await router.push('/org?tab=liaison')
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : '提交失败'
  } finally {
    busy.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="page wide hw-form-page">
    <AgreementDialog
      v-model:open="agreeOpen"
      title="结项报送协议"
      :paragraphs="finalTerms"
      @agree="acceptTerms"
    />
    <ConfirmDialog
      v-model:open="confirmOpen"
      title="确认报送组委会？"
      message="提交后组委会会自动接收并计入结项名单，公开页还看不到。请确认说明、交付件和链接已经完整。"
      confirm-text="确认提交"
      cancel-text="再检查一下"
      @confirm="doSubmit"
    />
    <RouterLink v-if="!embedded" class="back" to="/org?tab=finals">← 返回结项材料</RouterLink>
    <h1 v-if="!embedded" class="page-title">{{ app?.project_title || '结项材料' }}</h1>
    <p v-if="app" class="who">{{ app.student_name }} · 申请 #{{ app.id }}</p>
    <div class="card">
      <h2>提交结项材料</h2>
      <p class="sub">导师通过后，把说明、交付件和链接报送组委会；提交后自动接收，不必再等组委会点通过</p>
      <p v-if="error" class="error">{{ error }}</p>
      <fieldset :disabled="!ready || busy" class="wrap">
        <div class="form-grid">
          <label class="lab req">说明</label>
          <div class="ctrl">
            <textarea v-model="text" maxlength="500" rows="5" placeholder="说明这份结项做了什么、材料在哪里" />
            <span class="counter">{{ text.length }}/500</span>
          </div>
          <span class="lab req">交付件</span>
          <div class="ctrl">
            <ZipDropZone v-model:url="zipUrl" v-model:name="zipName" :disabled="!ready || busy" @error="(m) => (error = m)" />
          </div>
          <label class="lab">设计文档链接</label>
          <div class="ctrl">
            <textarea v-model="designDoc" maxlength="500" rows="2" placeholder="设计文档地址，没有就留空" />
          </div>
          <label class="lab">代码链接</label>
          <div class="ctrl">
            <textarea v-model="codeUrl" maxlength="500" rows="2" placeholder="代码仓或合并请求地址，没有就留空" />
          </div>
        </div>
        <label class="agree">
          <input v-model="agreed" type="checkbox" :disabled="!ready || busy" />
          <span>
            我已阅读并同意
            <button type="button" class="as-link" @click.prevent="agreeOpen = true">《结项报送协议》</button>
            。未同意不能提交结项。
          </span>
        </label>
      </fieldset>
      <div class="actions">
        <button class="btn primary" type="button" :disabled="busy || !ready || !agreed" @click="requestSubmit">确认提交</button>
        <RouterLink class="btn outline" to="/org?tab=liaison">取消</RouterLink>
      </div>
    </div>
  </div>
</template>

<style scoped>
.hw-form-page { max-width: 960px; margin: 0 auto; }
.back { color: #1677ff; text-decoration: none; font-size: 0.92rem; }
.page-title { margin: 0.6rem 0 0.2rem; font-size: 1.35rem; color: #111; }
.who { margin: 0 0 1rem; color: #6b7280; }
.card { background: #fff; border: 1px solid #e5e7eb; border-radius: 12px; padding: 1.5rem 1.75rem 1.75rem; }
.card h2 { margin: 0 0 0.35rem; font-size: 1.15rem; }
.sub { margin: 0 0 1.2rem; color: #6b7280; font-size: 0.88rem; }
.error { color: #dc2626; }
.wrap { border: 0; padding: 0; margin: 0; }
.wrap:disabled { opacity: 0.55; }
.form-grid { display: grid; grid-template-columns: 7.5rem minmax(0, 1fr); column-gap: 1.25rem; row-gap: 1.2rem; align-items: start; }
.lab { padding-top: 0.55rem; font-weight: 600; text-align: right; }
.lab.req::before { content: '*'; color: #ef4444; margin-right: 0.2rem; }
textarea { width: 100%; box-sizing: border-box; border: 1px solid #e5e7eb; border-radius: 8px; padding: 8px 10px; font: inherit; }
.counter { display: block; text-align: right; color: #9ca3af; font-size: 0.78rem; }
.agree { display: flex; flex-direction: row; align-items: flex-start; gap: 8px; margin: 1.2rem 0 0; color: #334155; font-size: 0.88rem; line-height: 1.55; }
.agree input { margin-top: 0.2rem; flex: 0 0 auto; }
.as-link { border: 0; background: none; padding: 0; color: #1677ff; font: inherit; cursor: pointer; text-decoration: underline; }
.actions { display: flex; gap: 10px; margin-top: 1.2rem; }
.btn { border-radius: 8px; padding: 8px 16px; font: inherit; cursor: pointer; text-decoration: none; }
.btn.primary { background: #111; color: #fff; border: 0; }
.btn.outline { background: #fff; color: #111; border: 1px solid #d1d5db; }
</style>
