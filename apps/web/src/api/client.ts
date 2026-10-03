import axios, { type InternalAxiosRequestConfig } from 'axios'

const PUBLIC_TOKEN_KEY = 'intern_platform_token'
const OPS_TOKEN_KEY = 'intern_platform_ops_token'

export function isOpsPath(path = window.location.pathname): boolean {
  return path.startsWith('/ops') || path.startsWith('/committee')
}

function keyFor(scope: 'public' | 'ops'): string {
  return scope === 'ops' ? OPS_TOKEN_KEY : PUBLIC_TOKEN_KEY
}

/** 每个窗口各记各的登录。localStorage 两个窗口共用，登录会互相顶掉。 */
function readToken(scope: 'public' | 'ops'): string | null {
  const key = keyFor(scope)
  localStorage.removeItem(key)
  return sessionStorage.getItem(key)
}

export function getStoredToken(scope?: 'public' | 'ops'): string | null {
  const useOps = scope ? scope === 'ops' : isOpsPath()
  return readToken(useOps ? 'ops' : 'public')
}

export function withFileAuth(url?: string | null): string {
  if (!url || !url.includes('/uploads/files/')) return url || ''
  const token = getStoredToken()
  if (!token) return url
  const sep = url.includes('?') ? '&' : '?'
  return `${url}${sep}access_token=${encodeURIComponent(token)}`
}

export function setStoredToken(token: string | null, scope?: 'public' | 'ops') {
  const useOps = scope ? scope === 'ops' : isOpsPath()
  const key = keyFor(useOps ? 'ops' : 'public')
  localStorage.removeItem(key)
  if (token) sessionStorage.setItem(key, token)
  else sessionStorage.removeItem(key)
}

function uuid(): string {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID()
  }
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0
    const v = c === 'x' ? r : (r & 0x3) | 0x8
    return v.toString(16)
  })
}

export const api = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = getStoredToken()
  if (token) {
    config.headers.set('Authorization', `Bearer ${token}`)
  }

  // FormData 需由浏览器自动带 multipart boundary，勿强制 JSON
  if (typeof FormData !== 'undefined' && config.data instanceof FormData) {
    config.headers.delete('Content-Type')
  }

  const method = (config.method || 'get').toUpperCase()
  if (['POST', 'PUT', 'PATCH'].includes(method)) {
    if (!config.headers.get('X-Idempotency-Key')) {
      config.headers.set('X-Idempotency-Key', uuid())
    }
    if (!config.headers.get('X-Request-ID')) {
      config.headers.set('X-Request-ID', uuid())
    }
  }
  return config
})

api.interceptors.response.use(
  (res) => res,
  (err) => {
    const detail = err.response?.data?.detail
    if (typeof detail === 'string') {
      err.message = detail
    } else if (Array.isArray(detail)) {
      err.message = detail.map((d: { msg?: string }) => d.msg || JSON.stringify(d)).join('; ')
    }
    return Promise.reject(err)
  },
)

export default api
