<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import api from '@/api/client'
import type { UserOut } from '@/api/types'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import { useAuthStore } from '@/stores/auth'
import { getProvider, type BindField } from '@/utils/bindProviders'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

const provider = computed(() => getProvider(String(route.params.provider || '')))
const busy = ref(false)
const err = ref('')
const ok = ref('')
const mode = ref<'real' | 'unavailable' | ''>('')
const unbindOpen = ref(false)

const boundValue = computed(() => {
  const p = provider.value
  if (!p || !auth.user) return ''
  return (auth.user[p.field as keyof UserOut] as string) || ''
})

const avatarUrl = computed(() => {
  const p = provider.value
  if (!p || !auth.user?.oauth_avatars) return ''
  return auth.user.oauth_avatars[p.key] || ''
})

const canAuthorize = computed(() => mode.value === 'real')
const isCommittee = computed(() => auth.hasRole('committee'))

onMounted(async () => {
  if (!auth.user) await auth.fetchMe()
  if (!provider.value) {
    router.replace('/me?tab=bindings')
    return
  }
  await probeMode()
})

async function probeMode() {
  const p = provider.value
  if (!p) return
  try {
    const { data } = await api.get<Array<{ key: string; configured: boolean }>>(
      '/auth/oauth/providers',
    )
    const hit = data.find((x) => x.key === p.key)
    mode.value = hit?.configured ? 'real' : 'unavailable'
  } catch {
    mode.value = 'unavailable'
  }
}

async function authorize() {
  const p = provider.value
  if (!p || !canAuthorize.value) return
  busy.value = true
  err.value = ''
  try {
    const { data } = await api.get<{ authorize_url: string; mode: string }>(
      `/auth/oauth/${p.key}/start`,
    )
    if (data.mode !== 'real' || !data.authorize_url) {
      mode.value = 'unavailable'
      busy.value = false
      return
    }
    window.location.href = data.authorize_url
  } catch (e: unknown) {
    err.value = e instanceof Error ? e.message : '无法发起授权'
    busy.value = false
  }
}

async function unbind() {
  const p = provider.value
  if (!p) return
  unbindOpen.value = true
}

async function confirmUnbind() {
  const p = provider.value
  if (!p) return
  busy.value = true
  err.value = ''
  try {
    const payload: Partial<Record<BindField, null>> = { [p.field]: null }
    const { data } = await api.patch<UserOut>('/auth/me', payload)
    auth.user = data
    ok.value = '已解除绑定'
  } catch (e: unknown) {
    err.value = e instanceof Error ? e.message : '解绑失败'
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="link-page" v-if="provider">
    <ConfirmDialog
      v-model:open="unbindOpen"
      title="解除绑定？"
      :message="`确定解除与 ${provider.name} 的绑定？`"
      confirm-text="解除绑定"
      danger
      @confirm="confirmUnbind"
    />
    <div class="link-shell">
      <RouterLink class="link-back" to="/me?tab=bindings">← 返回平台绑定</RouterLink>

      <section class="link-hero">
        <div
          class="link-mark"
          :class="{ 'has-avatar': !!avatarUrl }"
          :style="{
            background: avatarUrl ? `center / cover url(${avatarUrl})` : provider.color,
          }"
        >
          <span v-if="!avatarUrl">{{ provider.mark }}</span>
        </div>

        <h1>{{ boundValue ? `已绑定 ${provider.name}` : `绑定 ${provider.name}` }}</h1>

        <p v-if="boundValue" class="link-account">
          <span class="link-at">@{{ boundValue }}</span>
        </p>
        <p v-else class="link-desc">
          点击授权后跳转 {{ provider.name }} 官方页面；本机已登录会自动带出账号与头像，同意即可完成绑定。
        </p>

        <div class="link-cta">
          <button
            class="link-btn primary"
            type="button"
            :disabled="busy || !canAuthorize"
            @click="authorize"
          >
            {{
              busy
                ? '正在跳转…'
                : boundValue
                  ? '重新授权'
                  : `使用 ${provider.name} 账号授权`
            }}
          </button>
          <button
            v-if="boundValue"
            class="link-btn ghost"
            type="button"
            :disabled="busy"
            @click="unbind"
          >
            解除绑定
          </button>
        </div>

        <p v-if="!canAuthorize" class="link-soft">
          该平台尚未由组委会开通 OAuth。
          <RouterLink v-if="isCommittee" to="/committee/oauth">前往开通配置</RouterLink>
          <span v-else>开通后全体用户均可一键授权，无需每人单独配置。</span>
        </p>
        <p v-if="ok" class="link-ok">{{ ok }}</p>
        <p v-if="err" class="link-err">{{ err }}</p>

        <ul class="link-perms">
          <li>仅读取公开用户名与头像</li>
          <li>不会修改仓库或代发操作</li>
        </ul>
      </section>
    </div>
  </div>
</template>
