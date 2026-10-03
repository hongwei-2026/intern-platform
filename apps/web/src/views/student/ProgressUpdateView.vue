<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter, RouterLink } from 'vue-router'
import api from '@/api/client'
import type { ApplicationOut } from '@/api/types'
import ZipDropZone from '@/components/ZipDropZone.vue'
import AgreementDialog from '@/components/AgreementDialog.vue'
import PageCrumb from '@/components/PageCrumb.vue'
import { resolveCrumbs } from '@/utils/crumbTrail'

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
const progressTerms = [
  '一、本协议适用于在本平台更新任务进展。你提交的说明、压缩包、设计文档链接和代码链接，只用于导师查看进度并给出建议。',
  '二、进展材料不是结项验收，不会因此通过或退回验收。请只放与当前进度有关的内容，不要夹带账号密码或其他无关隐私。',
  '三、勾选同意并提交，即表示你已阅读本协议，并授权导师按上述范围查看这些材料。未同意本协议，不能提交进展。',
]

function acceptTerms() {
  agreed.value = true
}
const busy = ref(false)
const error = ref('')

const id = () => String(route.params.id)
const backTo = computed(() => `/student/applications/${id()}?tab=task`)
const crumbs = computed(() =>
  resolveCrumbs(
    { label: '更新进展', to: `/student/applications/${id()}/progress` },
    [
      { label: '我的项目', to: '/projects?tab=mine' },
      {
        label: app.value?.project_title || `申请 #${id()}`,
        to: backTo.value,
      },
    ],
  ),
)
const textLen = computed(() => text.value.length)
const designLen = computed(() => designDoc.value.length)
const codeLen = computed(() => codeUrl.value.length)

async function load() {
  error.value = ''
  try {
    const { data } = await api.get<ApplicationOut>(`/applications/${id()}`)
    app.value = data
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : '加载失败'
  }
}

async function ensureInProgress(status: string) {
  if (['community_review', 'committee_review', 'selected'].includes(status)) {
    await api.post(`/applications/${id()}/start-progress`)
  }
}

async function submit() {
  if (!zipUrl.value) {
    error.value = '请上传交付件（zip）'
    return
  }
  if (!agreed.value) {
    error.value = '请先阅读并同意《任务进展提交协议》'
    return
  }
  if (!app.value) return
  busy.value = true
  error.value = ''
  try {
    await ensureInProgress(app.value.status)
    await api.post(`/applications/${id()}/messages`, {
      body: text.value.trim() || '进展更新',
      kind: 'progress',
      design_doc_url: designDoc.value.trim() || '暂无',
      code_url: codeUrl.value.trim() || '暂无',
      attachment_url: zipUrl.value,
      attachment_name: zipName.value || null,
    })
    await router.push(`/student/applications/${id()}?tab=task`)
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : '提交失败'
  } finally {
    busy.value = false
  }
}

watch(() => route.params.id, load)
onMounted(load)
</script>

<template>
  <div class="page wide hw-form-page">
    <AgreementDialog
      v-model:open="agreeOpen"
      title="任务进展提交协议"
      :paragraphs="progressTerms"
      @agree="acceptTerms"
    />
    <PageCrumb :items="crumbs" />

    <h1 class="page-title">{{ app?.project_title || `申请 #${id()}` }}</h1>

    <div class="card">
      <h2>更新任务进展</h2>
      <p class="sub">后续进展反馈，请前往 PR 查看</p>
      <p v-if="error" class="error">{{ error }}</p>

      <div class="form-grid">
        <label class="lab">说明</label>
        <div class="ctrl">
          <div class="box">
            <textarea
              v-model="text"
              maxlength="500"
              rows="5"
              placeholder="请说明阶段进展，建议包含：已实现功能、遗留技术难点、后续研发计划"
            />
            <span class="counter">{{ textLen }}/500</span>
          </div>
        </div>

        <span class="lab req">交付件</span>
        <div class="ctrl">
          <ZipDropZone
            v-model:url="zipUrl"
            v-model:name="zipName"
            :disabled="busy"
            @error="(m) => (error = m)"
          />
        </div>

        <label class="lab">设计文档链接</label>
        <div class="ctrl">
          <div class="box">
            <textarea
              v-model="designDoc"
              maxlength="500"
              rows="3"
              placeholder="请填写设计文档 PR 链接，若不涉及填写「暂无」"
            />
            <span class="counter">{{ designLen }}/500</span>
          </div>
        </div>

        <label class="lab">代码链接</label>
        <div class="ctrl">
          <div class="box">
            <textarea
              v-model="codeUrl"
              maxlength="500"
              rows="3"
              placeholder="请填写个人代码仓链接（同时在私仓中邀请账号 Ascend-CANN 作为开发者），若不涉及填写「暂无」"
            />
            <span class="counter">{{ codeLen }}/500</span>
          </div>
        </div>
      </div>

      <label class="agree">
        <input v-model="agreed" type="checkbox" :disabled="busy" />
        <span>
          我已阅读并同意
          <button type="button" class="as-link" @click.prevent="agreeOpen = true">《任务进展提交协议》</button>
          。未同意不能提交进展。
        </span>
      </label>

      <div class="actions">
        <button class="btn primary" type="button" :disabled="busy || !agreed" @click="submit">
          提交进展
        </button>
        <RouterLink class="btn outline" :to="backTo">取消</RouterLink>
      </div>
    </div>
  </div>
</template>

<style scoped>
.hw-form-page {
  max-width: 960px;
  margin: 0 auto;
}
.page-title {
  margin: 0 0 1rem;
  font-size: 1.35rem;
  font-weight: 700;
  line-height: 1.35;
  color: #111;
}
.card {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 1.5rem 1.75rem 1.75rem;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
}
.card h2 {
  margin: 0 0 0.35rem;
  font-size: 1.15rem;
}
.sub {
  margin: 0 0 1.35rem;
  color: #6b7280;
  font-size: 0.88rem;
}
.form-grid {
  display: grid;
  grid-template-columns: 7.5rem minmax(0, 1fr);
  column-gap: 1.25rem;
  row-gap: 1.35rem;
  align-items: start;
}
.lab {
  padding-top: 0.65rem;
  font-weight: 600;
  font-size: 0.92rem;
  color: #111;
  text-align: right;
}
.lab.req::before {
  content: '*';
  color: #ef4444;
  margin-right: 0.2rem;
}
.ctrl {
  min-width: 0;
}
.box {
  position: relative;
}
textarea {
  width: 100%;
  font: inherit;
  font-weight: 400;
  padding: 0.7rem 0.8rem 1.5rem;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  resize: vertical;
  background: #fff;
  box-sizing: border-box;
}
.counter {
  position: absolute;
  right: 0.65rem;
  bottom: 0.4rem;
  font-size: 0.75rem;
  color: #9ca3af;
}
.agree {
  display: flex;
  flex-direction: row;
  align-items: flex-start;
  gap: 0.5rem;
  font-size: 0.88rem;
  color: #334155;
  margin: 1.35rem 0 1.25rem;
  line-height: 1.55;
}
.agree input { margin-top: 0.25rem; flex: 0 0 auto; }
.as-link { border: 0; background: none; padding: 0; color: #1677ff; font: inherit; cursor: pointer; text-decoration: underline; }
.actions {
  display: flex;
  gap: 0.55rem;
  justify-content: flex-end;
}
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0.5rem 1.35rem;
  border-radius: 999px;
  font-size: 0.9rem;
  font-weight: 600;
  cursor: pointer;
  text-decoration: none;
  border: 1px solid transparent;
  font: inherit;
}
.btn.primary {
  background: #111;
  color: #fff;
}
.btn.primary:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}
.btn.outline {
  background: #fff;
  border-color: #d1d5db;
  color: #111;
}
.error {
  color: #b91c1c;
  margin-bottom: 0.75rem;
}

@media (max-width: 640px) {
  .form-grid {
    grid-template-columns: 1fr;
    row-gap: 0.45rem;
  }
  .lab {
    text-align: left;
    padding-top: 0;
  }
}
</style>
