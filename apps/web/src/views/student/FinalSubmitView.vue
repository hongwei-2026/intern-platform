<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter, RouterLink } from 'vue-router'
import api from '@/api/client'
import type { ApplicationOut } from '@/api/types'
import ZipDropZone from '@/components/ZipDropZone.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
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
const busy = ref(false)
const error = ref('')
const confirmOpen = ref(false)

const id = () => String(route.params.id)
const backTo = computed(() => `/student/applications/${id()}?tab=task`)
const crumbs = computed(() =>
  resolveCrumbs(
    { label: '提交验收', to: `/student/applications/${id()}/final` },
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

const acceptancePending = computed(() =>
  ['final_submitted', 'mentor_final_review', 'committee_final_review'].includes(
    app.value?.status || '',
  ),
)

async function load() {
  error.value = ''
  try {
    const { data } = await api.get<ApplicationOut>(`/applications/${id()}`)
    app.value = data
    if (acceptancePending.value) {
      error.value = '已有验收在审核中，请等待审完；未通过后才能再次提交'
    }
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : '加载失败'
  }
}

function validateBeforeConfirm(): boolean {
  if (acceptancePending.value) {
    error.value = '验收审核中，暂不可再次提交'
    return false
  }
  if (!zipUrl.value) {
    error.value = '请上传交付件（zip）'
    return false
  }
  if (!agreed.value) {
    error.value = '请先勾选同意信息收集说明'
    return false
  }
  error.value = ''
  return true
}

function requestSubmit() {
  if (!validateBeforeConfirm()) return
  confirmOpen.value = true
}

async function doSubmit() {
  busy.value = true
  error.value = ''
  try {
    await api.put(`/applications/${id()}/final`, {
      pr_mr_url: codeUrl.value.trim() || '暂无',
      report_url: designDoc.value.trim() || '暂无',
      report_text: text.value.trim() || '提交验收',
      extra_fields: {
        attachment_url: zipUrl.value,
        attachment_name: zipName.value || null,
      },
    })
    await api.post(`/applications/${id()}/final/submit`)
    await api.post(`/applications/${id()}/messages`, {
      body: text.value.trim() || '提交验收',
      kind: 'acceptance',
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
    <ConfirmDialog
      v-model:open="confirmOpen"
      title="确认提交验收？"
      message="提交后进入审核期，期间不能再次提交验收。请确认交付件与材料已完整、正确后再提交。审核未通过后才可重新提交。"
      confirm-text="确认提交"
      cancel-text="再检查一下"
      @confirm="doSubmit"
    />

    <PageCrumb :items="crumbs" />

    <h1 class="page-title">{{ app?.project_title || `申请 #${id()}` }}</h1>

    <div class="card">
      <h2>提交验收</h2>
      <p class="sub">一次只能有一份验收在审；审核未通过后才能再次提交</p>
      <p v-if="error" class="error">{{ error }}</p>

      <fieldset :disabled="acceptancePending || busy" class="wrap">
        <div class="form-grid">
          <label class="lab">说明</label>
          <div class="ctrl">
            <div class="box">
              <textarea
                v-model="text"
                maxlength="500"
                rows="5"
                placeholder="请说明验收内容，建议包含：已完成功能、测试情况、PR / Issue 索引；ZIP 内可附截图"
              />
              <span class="counter">{{ textLen }}/500</span>
            </div>
          </div>

          <span class="lab req">交付件</span>
          <div class="ctrl">
            <ZipDropZone
              v-model:url="zipUrl"
              v-model:name="zipName"
              :disabled="acceptancePending || busy"
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
                placeholder="请填写个人代码仓 / PR 链接，若不涉及填写「暂无」"
              />
              <span class="counter">{{ codeLen }}/500</span>
            </div>
          </div>
        </div>

        <label class="agree">
          <input v-model="agreed" type="checkbox" />
          <span>
            已阅读并同意：提交验收时将收集附件、设计文档链接、代码链接与说明，用于验收审核与运营。
          </span>
        </label>
      </fieldset>

      <div class="actions">
        <button
          class="btn primary"
          type="button"
          :disabled="busy || acceptancePending"
          @click="requestSubmit"
        >
          确认提交验收
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
.wrap {
  border: none;
  padding: 0;
  margin: 0;
}
.wrap:disabled {
  opacity: 0.55;
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
  gap: 0.5rem;
  align-items: flex-start;
  font-size: 0.82rem;
  color: #4b5563;
  margin: 1.35rem 0 1.25rem;
  line-height: 1.45;
}
.agree input {
  margin-top: 0.2rem;
}
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
  opacity: 0.4;
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
