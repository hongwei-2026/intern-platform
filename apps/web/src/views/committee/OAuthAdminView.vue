<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import api from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import { BIND_PROVIDERS } from '@/utils/bindProviders'

interface ProviderStatus {
  key: string
  name: string
  configured: boolean
  callback_uri: string
  create_url: string
  hint: string
}

const auth = useAuthStore()
const loading = ref(true)
const saving = ref(false)
const msg = ref('')
const err = ref('')
const providers = ref<ProviderStatus[]>([])
const current = ref('github')
const clientId = ref('')
const clientSecret = ref('')
const copied = ref(false)

const metaOf = (key: string) => BIND_PROVIDERS.find((p) => p.key === key)
const order = BIND_PROVIDERS.map((p) => p.key)
const list = computed(() =>
  [...providers.value].sort(
    (a, b) =>
      order.indexOf(a.key as (typeof order)[number]) - order.indexOf(b.key as (typeof order)[number]),
  ),
)
const active = computed(() => list.value.find((p) => p.key === current.value))
const opened = computed(() => list.value.filter((p) => p.configured).length)

onMounted(async () => {
  if (!auth.user) await auth.fetchMe()
  await load()
})

async function load() {
  loading.value = true
  err.value = ''
  try {
    const { data } = await api.get<ProviderStatus[]>('/auth/oauth/providers')
    providers.value = data
    if (!list.value.some((p) => p.key === current.value)) {
      current.value = list.value[0]?.key || 'github'
    }
  } catch (e: unknown) {
    err.value = e instanceof Error ? e.message : '加载失败'
  } finally {
    loading.value = false
  }
}

function pick(key: string) {
  current.value = key
  clientId.value = ''
  clientSecret.value = ''
  msg.value = ''
  err.value = ''
  copied.value = false
}

async function copyCallback() {
  if (!active.value) return
  await navigator.clipboard.writeText(active.value.callback_uri)
  copied.value = true
  window.setTimeout(() => {
    copied.value = false
  }, 1200)
}

async function save() {
  const id = clientId.value.trim()
  const secret = clientSecret.value.trim()
  if (!id || !secret) {
    err.value = '请填写应用 ID 和密钥'
    return
  }
  if (id.includes('@')) {
    err.value = '应用 ID 不是邮箱，请从平台应用页复制'
    return
  }
  saving.value = true
  msg.value = ''
  err.value = ''
  try {
    await api.post(`/auth/oauth/${current.value}/client`, {
      client_id: id,
      client_secret: secret,
    })
    clientSecret.value = ''
    msg.value = `${active.value?.name || ''} 已开通`
    await load()
  } catch (e: unknown) {
    err.value = e instanceof Error ? e.message : '保存失败'
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="page oauth-page">
    <div class="oauth-head">
      <div>
        <p class="oauth-back"><RouterLink to="/committee">← 返回工作台</RouterLink></p>
        <h1 class="page-title">开通账号绑定</h1>
        <p class="page-desc">左侧选平台，右侧填配置。已开通 {{ opened }} / {{ list.length }}</p>
      </div>
    </div>

    <p v-if="msg" class="success-msg">{{ msg }}</p>
    <p v-if="err" class="error">{{ err }}</p>
    <p v-if="loading" class="muted">加载中…</p>

    <div v-else class="oauth-layout">
      <aside class="oauth-side">
        <h2>平台列表</h2>
        <button
          v-for="p in list"
          :key="p.key"
          type="button"
          class="oauth-side-item"
          :class="{ on: current === p.key }"
          @click="pick(p.key)"
        >
          <span
            class="oauth-side-mark"
            :style="{ background: metaOf(p.key)?.color || '#64748b' }"
          >
            {{ metaOf(p.key)?.mark || p.name.slice(0, 1) }}
          </span>
          <span class="oauth-side-text">
            <strong>{{ p.name }}</strong>
            <small :class="p.configured ? 'ok' : 'no'">{{ p.configured ? '已开通' : '未开通' }}</small>
          </span>
        </button>
      </aside>

      <section v-if="active" class="oauth-main card">
        <header class="oauth-main-head">
          <span
            class="oauth-side-mark lg"
            :style="{ background: metaOf(active.key)?.color || '#64748b' }"
          >
            {{ metaOf(active.key)?.mark || active.name.slice(0, 1) }}
          </span>
          <div>
            <h2>{{ active.name }}</h2>
            <p>{{ active.configured ? '已开通，可更新密钥' : '未开通，按下面三步完成' }}</p>
          </div>
        </header>

        <div class="oauth-grid">
          <div class="oauth-block">
            <h3>1. 创建应用</h3>
            <template v-if="active.create_url">
              <a class="btn" :href="active.create_url" target="_blank" rel="noopener">
                去 {{ active.name }} 创建
              </a>
              <p v-if="active.hint" class="hint">{{ active.hint }}</p>
            </template>
            <div v-else class="oauth-blocked">
              <p class="oauth-blocked-title">{{ active.name }} 暂时无法外链创建</p>
              <p class="hint">
                {{ active.hint || '创建页打不开或无权限，这是平台/网络侧限制，不是本站故障。' }}
              </p>
              <p class="hint">
                若手上已有应用 ID 和密钥，可直接在下方填写并保存；否则请先开通已可用的 GitHub / Gitee。
              </p>
            </div>
          </div>

          <div class="oauth-block">
            <h3>2. 回调地址</h3>
            <p class="hint">创建时粘贴到 Callback / 回调 URL（须完全一致）</p>
            <div class="cb">
              <code>{{ active.callback_uri }}</code>
              <button class="btn sm secondary" type="button" @click="copyCallback">
                {{ copied ? '已复制' : '复制' }}
              </button>
            </div>
          </div>

          <div class="oauth-block full">
            <h3>3. 填入密钥</h3>
            <div class="oauth-fields">
              <label>
                应用 ID
                <input v-model="clientId" autocomplete="off" placeholder="一串英文数字，不要填邮箱" />
              </label>
              <label>
                应用密钥
                <input
                  v-model="clientSecret"
                  type="password"
                  autocomplete="off"
                  placeholder="Client Secret"
                />
              </label>
            </div>
            <button class="btn" type="button" :disabled="saving" @click="save">
              {{ saving ? '保存中…' : active.configured ? '更新并保存' : '保存开通' }}
            </button>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.oauth-page {
  max-width: 1100px;
}
.oauth-back {
  margin: 0 0 6px;
}
.oauth-layout {
  display: grid;
  grid-template-columns: 260px minmax(0, 1fr);
  gap: 20px;
  align-items: start;
  margin-top: 8px;
}
.oauth-side {
  background: #fff;
  border: 1px solid #eef0f3;
  border-radius: 14px;
  padding: 14px;
}
.oauth-side h2 {
  margin: 0 0 10px;
  font-size: 13px;
  color: #9ca3af;
  font-weight: 600;
}
.oauth-side-item {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 10px;
  border: none;
  background: transparent;
  border-radius: 10px;
  cursor: pointer;
  text-align: left;
  margin-bottom: 4px;
}
.oauth-side-item:hover {
  background: #f8fafc;
}
.oauth-side-item.on {
  background: #eff6ff;
}
.oauth-side-mark {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  color: #fff;
  display: grid;
  place-items: center;
  font-size: 12px;
  font-weight: 800;
  flex-shrink: 0;
}
.oauth-side-mark.lg {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  font-size: 14px;
}
.oauth-side-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.oauth-side-text strong {
  font-size: 14px;
  color: #111827;
}
.oauth-side-text small {
  font-size: 12px;
}
.oauth-side-text .ok {
  color: #16a34a;
}
.oauth-side-text .no {
  color: #9ca3af;
}
.oauth-main {
  padding: 24px;
  min-height: 420px;
}
.oauth-main-head {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 22px;
  padding-bottom: 18px;
  border-bottom: 1px solid #f0f2f5;
}
.oauth-main-head h2 {
  margin: 0 0 4px;
  font-size: 20px;
}
.oauth-main-head p {
  margin: 0;
  color: #9ca3af;
  font-size: 13px;
}
.oauth-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}
.oauth-block {
  background: #f8fafc;
  border-radius: 12px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  align-items: flex-start;
}
.oauth-block.full {
  grid-column: 1 / -1;
}
.oauth-block h3 {
  margin: 0;
  font-size: 14px;
  color: #111827;
}
.hint {
  margin: 0;
  font-size: 12px;
  color: #9ca3af;
  line-height: 1.6;
}
.oauth-blocked {
  width: 100%;
  padding: 12px;
  border-radius: 10px;
  background: #fff7ed;
  border: 1px solid #ffedd5;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.oauth-blocked-title {
  margin: 0;
  font-size: 14px;
  font-weight: 700;
  color: #c2410c;
}
.cb {
  width: 100%;
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
}
.cb code {
  flex: 1;
  min-width: 0;
  padding: 10px 12px;
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  font-size: 12px;
  word-break: break-all;
}
.oauth-fields {
  width: 100%;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}
.oauth-fields label {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 13px;
  color: #374151;
}
.oauth-fields input {
  height: 42px;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  padding: 0 12px;
  background: #fff;
}
@media (max-width: 860px) {
  .oauth-layout {
    grid-template-columns: 1fr;
  }
  .oauth-grid,
  .oauth-fields {
    grid-template-columns: 1fr;
  }
}
</style>
