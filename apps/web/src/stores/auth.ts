import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import api, { getStoredToken, setStoredToken } from '@/api/client'
import type { UserOut } from '@/api/types'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(getStoredToken())
  const user = ref<UserOut | null>(null)
  const loading = ref(false)

  const isLoggedIn = computed(() => !!token.value)
  const roleCodes = computed(() => user.value?.roles.map((r) => r.code) ?? [])
  const displayName = computed(() => user.value?.display_name || user.value?.email || '')

  /** 组织侧角色：导师 / 社区管理员 / 组委会 */
  const isStaff = computed(() =>
    roleCodes.value.some((c) => ['mentor', 'community_admin', 'committee'].includes(c)),
  )
  const isMentor = computed(() => roleCodes.value.includes('mentor'))
  const isCommunityAdmin = computed(() => roleCodes.value.includes('community_admin'))
  /** 仅学生可申请项目（组织侧账号不混用学生申请能力） */
  const canApplyProjects = computed(() => !isStaff.value)

  function hasRole(...codes: string[]) {
    return codes.some((c) => roleCodes.value.includes(c))
  }

  function portalHome(): string {
    if (hasRole('committee') && !hasRole('mentor') && !hasRole('community_admin')) return '/committee'
    if (hasRole('community_admin') && !hasRole('mentor')) return '/org'
    if (hasRole('mentor')) return '/mentor'
    if (hasRole('community_admin')) return '/org'
    return '/me'
  }

  async function login(email: string, password: string) {
    loading.value = true
    try {
      const { data } = await api.post<{ access_token: string; user: UserOut }>('/auth/login', {
        email,
        password,
      })
      token.value = data.access_token
      setStoredToken(data.access_token)
      user.value = data.user
      return data.user
    } finally {
      loading.value = false
    }
  }

  async function register(payload: {
    email: string
    password: string
    display_name: string
    school?: string
  }) {
    loading.value = true
    try {
      const { data } = await api.post<{ access_token: string; user: UserOut }>(
        '/auth/register',
        payload,
      )
      token.value = data.access_token
      setStoredToken(data.access_token)
      user.value = data.user
      return data.user
    } finally {
      loading.value = false
    }
  }

  async function registerMentor(payload: {
    email: string
    password: string
    display_name: string
    invite_code: string
  }) {
    loading.value = true
    try {
      const { data } = await api.post<{ access_token: string; user: UserOut }>(
        '/auth/register-mentor',
        payload,
      )
      token.value = data.access_token
      setStoredToken(data.access_token)
      user.value = data.user
      return data.user
    } finally {
      loading.value = false
    }
  }

  async function fetchMe() {
    if (!token.value) {
      user.value = null
      return null
    }
    try {
      const { data } = await api.get<UserOut>('/auth/me')
      user.value = data
      return data
    } catch {
      logout()
      return null
    }
  }

  function logout() {
    token.value = null
    user.value = null
    setStoredToken(null)
  }

  return {
    token,
    user,
    loading,
    isLoggedIn,
    roleCodes,
    displayName,
    isStaff,
    isMentor,
    isCommunityAdmin,
    canApplyProjects,
    hasRole,
    portalHome,
    login,
    register,
    registerMentor,
    fetchMe,
    logout,
  }
})
