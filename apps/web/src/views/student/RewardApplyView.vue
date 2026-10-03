<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import api, { withFileAuth } from '@/api/client'
import type { ApplicationOut, MessageOut } from '@/api/types'
import PageCrumb from '@/components/PageCrumb.vue'
import ZipDropZone from '@/components/ZipDropZone.vue'
import AgreementDialog from '@/components/AgreementDialog.vue'

const route = useRoute()
const router = useRouter()
const app = ref<ApplicationOut | null>(null)
const sent = ref<MessageOut | null>(null)
const text = ref('')
const phone = ref('')
const email = ref('')
const extra = ref('')
const zipUrl = ref('')
const zipName = ref('')
const agreed = ref(false)
const agreeOpen = ref(false)
const busy = ref(false)
const error = ref('')
const rewardTerms = [
  '一、本协议适用于验收通过后向本社区申请奖励。ZIP 和联系方式只交给该项目所属社区的管理员，组委会不接收、也不代发奖励。',
  '二、联系方式至少填写一项，只用于通知奖励发放。请填写本人正在使用的手机、邮箱或其他联系方式，不要填写他人信息。',
  '三、ZIP 未交、没有联系方式，或未同意本协议，不能提交。说明可以不写。勾选同意并提交，即表示你确认材料真实，并授权平台按上述范围使用。',
]

const id = () => String(route.params.id)
const allowed = computed(() =>
  ['community_final_review', 'committee_final_review', 'completed'].includes(app.value?.status || ''),
)
const crumbs = computed(() => [
  { label: '我的项目', to: '/projects?tab=mine' },
  { label: app.value?.project_title || `申请 #${id()}`, to: `/student/applications/${id()}?tab=task` },
  { label: '申请奖励' },
])
const zipLabel = computed(() => sent.value?.attachment_name || '证明材料.zip')
const hasContact = computed(() => [phone.value, email.value, extra.value].some((item) => item.trim()))
const ready = computed(() => !!zipUrl.value && hasContact.value && agreed.value)
const canSubmit = computed(() => ready.value && !busy.value)

function acceptTerms() {
  agreed.value = true
}

async function load() {
  error.value = ''
  const { data } = await api.get<ApplicationOut>(`/applications/${id()}`)
  app.value = data
  const { data: msgs } = await api.get<MessageOut[]>(`/applications/${id()}/messages`)
  const latest = [...msgs].reverse().find((item) => item.kind === 'reward')
  sent.value = latest && latest.reward_status !== 'rejected' ? latest : null
}

async function submit() {
  if (!canSubmit.value) return
  busy.value = true
  error.value = ''
  try {
    const body = [
      text.value.trim() ? `说明：${text.value.trim()}` : '',
      phone.value.trim() ? `手机：${phone.value.trim()}` : '',
      email.value.trim() ? `邮箱：${email.value.trim()}` : '',
      extra.value.trim() ? `其他联系方式：${extra.value.trim()}` : '',
    ]
      .filter(Boolean)
      .join('\n')
    await api.post(`/applications/${id()}/messages`, {
      body,
      kind: 'reward',
      attachment_url: zipUrl.value,
      attachment_name: zipName.value || '证明材料.zip',
    })
    await router.push(`/student/applications/${id()}?tab=task`)
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : '提交失败'
  } finally {
    busy.value = false
  }
}

watch(
  () => route.params.id,
  () => void load().catch((e: unknown) => {
    error.value = e instanceof Error ? e.message : '加载失败'
  }),
)
onMounted(() => void load().catch((e: unknown) => {
  error.value = e instanceof Error ? e.message : '加载失败'
}))
</script>

<template>
  <div class="page reward">
    <AgreementDialog
      v-model:open="agreeOpen"
      title="奖励申请协议"
      :paragraphs="rewardTerms"
      @agree="acceptTerms"
    />
    <PageCrumb :items="crumbs" />
    <header class="head">
      <div>
        <h1>申请奖励</h1>
        <p>{{ app?.project_title || '当前任务' }}。导师验收通过后，提交关闭证明和联系方式。</p>
      </div>
    </header>
    <p v-if="error" class="error">{{ error }}</p>
    <p v-if="!app && !error" class="muted">加载中…</p>
    <template v-else-if="app">
    <p v-if="!allowed" class="error">还没有验收通过，不能申请奖励。</p>
    <article v-else-if="sent" class="card done">
      <h2>已经提交过奖励申请</h2>
      <p>{{ sent.body }}</p>
      <a v-if="sent.attachment_url" class="file" :href="withFileAuth(sent.attachment_url)" download>{{ zipLabel }}</a>
      <RouterLink class="btn" :to="`/student/applications/${id()}?tab=task`">返回我的项目</RouterLink>
    </article>
    <form v-else @submit.prevent="submit">
      <div class="split">
      <section class="card">
        <h2><em class="must">*</em>关闭证明</h2>
        <p class="hint">把 Issue 和 PR 已关闭的截图、链接清单打成一个 ZIP。只接受 zip，不超过 100MB。</p>
        <ZipDropZone
          v-model:url="zipUrl"
          v-model:name="zipName"
          :disabled="busy"
          @error="(message) => (error = message)"
        />
        <label>
          <span>说明</span>
          <textarea
            v-model="text"
            rows="8"
            maxlength="800"
            placeholder="列出已关闭的 Issue、PR，以及各自的链接和关闭情况"
          />
        </label>
      </section>
      <section class="card">
        <h2><em class="must">*</em>联系方式</h2>
        <p class="hint">手机、邮箱、其他至少填写一项。</p>
        <label>
          手机
          <input v-model="phone" type="tel" maxlength="32" placeholder="手机号" />
        </label>
        <label>
          邮箱
          <input v-model="email" type="email" maxlength="120" placeholder="邮箱" />
        </label>
        <label>
          其他
          <textarea v-model="extra" rows="4" maxlength="200" placeholder="微信、QQ 或其他方便联系的方式" />
        </label>
      </section>
      </div>
      <div class="submit-bar">
        <label class="agree">
          <input type="checkbox" :checked="agreed" disabled />
          <span>
            <em class="must">*</em>我已阅读并同意
            <button type="button" class="as-link" @click="agreeOpen = true">《奖励申请协议》</button>
            。点开协议并同意后才能提交。
          </span>
        </label>
        <div class="acts">
          <button class="btn" type="submit" :disabled="!canSubmit">{{ busy ? '提交中…' : '提交奖励申请' }}</button>
          <RouterLink class="btn ghost" :to="`/student/applications/${id()}?tab=task`">返回</RouterLink>
        </div>
        <p v-if="!ready" class="hint">需上传 ZIP、填写至少一项联系方式，并同意协议。</p>
      </div>
    </form>
    </template>
  </div>
</template>

<style scoped>
.reward {
  width: 100%;
  max-width: none;
  margin: 0;
  padding-bottom: 48px;
}
.head h1 {
  margin: 0.35rem 0 0.25rem;
  color: #1e3a5f;
}
.head p,
.hint {
  margin: 0;
  color: #64748b;
  line-height: 1.6;
}
.split {
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(280px, 0.8fr);
  gap: 16px;
  margin-top: 16px;
  align-items: stretch;
}
.card {
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 18px 20px 20px;
  background: #fff;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.card h2 {
  margin: 0;
  color: #1e3a5f;
  font-size: 1.05rem;
}
.must {
  color: #ef4444;
  font-style: normal;
  font-weight: 700;
  margin-right: 0.2rem;
}
label {
  display: flex;
  flex-direction: column;
  gap: 6px;
  color: #1e3a5f;
  font-weight: 600;
}
textarea,
input {
  width: 100%;
  box-sizing: border-box;
  border: 1px solid #d0d7e2;
  border-radius: 8px;
  padding: 8px 10px;
  font: inherit;
  font-weight: 400;
  color: #0f172a;
}
textarea {
  resize: vertical;
  min-height: 96px;
}
.acts {
  display: flex;
  gap: 8px;
  margin-top: auto;
}
.submit-bar {
  grid-column: 1 / -1;
  margin-top: 16px;
  padding: 14px 16px;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  background: #fff;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px 16px;
}
.agree {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 8px;
  margin: 0;
  font-weight: 500;
  flex: 1 1 320px;
}
.agree input {
  width: auto;
  margin: 0;
}
.as-link {
  border: 0;
  background: none;
  padding: 0;
  color: #1677ff;
  font: inherit;
  font-weight: 700;
  cursor: pointer;
}
.btn:disabled {
  background: #cbd5e1;
  color: #fff;
  cursor: not-allowed;
}
.submit-bar .hint { flex: 1 0 100%; }
.btn {
  display: inline-flex;
  align-items: center;
  background: #1677ff;
  color: #fff;
  border: 0;
  border-radius: 8px;
  padding: 8px 14px;
  text-decoration: none;
  font: inherit;
  cursor: pointer;
}
.btn.ghost {
  background: #fff;
  color: #1e3a5f;
  border: 1px solid #d0d7e2;
}
.file {
  color: #1677ff;
  font-weight: 700;
}
.error { color: #dc2626; }
.muted { color: #64748b; }
.done p { white-space: pre-wrap; line-height: 1.6; }
@media (max-width: 860px) {
  .split { grid-template-columns: 1fr; }
}
</style>
