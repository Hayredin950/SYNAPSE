/**
 * api.ts — Axios instance with industry best practices:
 *  ✓ JWT Bearer auth from Zustand persist store
 *  ✓ Single-flight refresh queue (prevents multiple simultaneous refresh calls)
 *  ✓ Exponential-backoff retry for network errors & 5xx
 *  ✓ Structured error normalisation
 *  ✓ Request timeout (30s protected, 15s auth)
 */
import axios, {
  AxiosError,
  AxiosInstance,
  InternalAxiosRequestConfig,
} from 'axios'

// ── Config ─────────────────────────────────────────────────────────────────────

// Use a relative base URL so browser requests flow through Next.js rewrites
// (which proxy /api/v1/* → Django on localhost:8000 server-side).
// Never use http://localhost:8000 directly — the browser can't reach it through the proxy.
const BASE_URL = (
  process.env.NEXT_PUBLIC_API_URL || ''
).replace(/\/api\/v1\/?$/, '').replace(/\/$/, '')

// ── Token helpers ──────────────────────────────────────────────────────────────

const getAccessToken = (): string | null => {
  if (typeof window === 'undefined') return null
  const direct = localStorage.getItem('synapse_access_token')
  if (direct) return direct
  try {
    const raw = localStorage.getItem('synapse-auth')
    if (raw) return JSON.parse(raw)?.state?.accessToken ?? null
  } catch {}
  return null
}

const getRefreshToken = (): string | null => {
  if (typeof window === 'undefined') return null
  return localStorage.getItem('synapse_refresh_token')
}

const setAccessToken = (token: string) => {
  localStorage.setItem('synapse_access_token', token)
}

const setRefreshToken = (token: string) => {
  localStorage.setItem('synapse_refresh_token', token)
  // Also keep the Zustand persisted store in sync so rehydration uses the latest token
  try {
    const raw = localStorage.getItem('synapse-auth')
    if (raw) {
      const parsed = JSON.parse(raw)
      if (parsed?.state) {
        parsed.state.refreshToken = token
        localStorage.setItem('synapse-auth', JSON.stringify(parsed))
      }
    }
  } catch {}
}

const clearTokens = () => {
  localStorage.removeItem('synapse_access_token')
  localStorage.removeItem('synapse_refresh_token')
}

// ── Refresh queue ─────────────────────────────────────────────────────────────
// Prevents multiple simultaneous token refresh calls when several requests
// get 401 at the same time (single-flight pattern).

type QueueItem = { resolve: (token: string) => void; reject: (err: unknown) => void }
let isRefreshing = false
let failedQueue: QueueItem[] = []

const processQueue = (err: unknown, token: string | null) => {
  failedQueue.forEach((p) => (err ? p.reject(err) : p.resolve(token!)))
  failedQueue = []
}

// ── Retry config ───────────────────────────────────────────────────────────────
// NOTE: 429 (rate limit) is intentionally NOT retried — retrying makes it worse.
// The rate limit event handler shows the upgrade modal instead.
const RETRY_STATUS = new Set([408, 500, 502, 503, 504])
const MAX_RETRIES  = 3
const retryDelay   = (n: number) => Math.min(1000 * 2 ** n + Math.random() * 500, 15000)

// ── Axios instances ────────────────────────────────────────────────────────────

/** Authenticated instance — all protected API calls */
export const api: AxiosInstance = axios.create({
  baseURL: `${BASE_URL}/api/v1`,
  timeout: 60_000,
  headers: { 'Content-Type': 'application/json' },
})

/** Unauthenticated instance — login / refresh / register */
export const authApi: AxiosInstance = axios.create({
  baseURL: `${BASE_URL}/api/v1`,
  timeout: 60_000,
  headers: { 'Content-Type': 'application/json' },
})

// ── JWT expiry helper ──────────────────────────────────────────────────────────

/** Decode JWT payload (no verification — we trust our own backend). Returns null if malformed. */
const decodeJwtExp = (token: string): number | null => {
  try {
    const payload = token.split('.')[1]
    if (!payload) return null
    const json = JSON.parse(atob(payload.replace(/-/g, '+').replace(/_/g, '/')))
    return typeof json.exp === 'number' ? json.exp : null
  } catch (_) { return null }
}

/** Check if the current access token is expired (or expires within `bufferSec` seconds). */
const isTokenExpired = (bufferSec = 30): boolean => {
  const token = getAccessToken()
  if (!token) return true
  const exp = decodeJwtExp(token)
  if (!exp) return false // can't decode — let it through, backend will reject if bad
  return Date.now() / 1000 > exp - bufferSec
}

/** Proactively refresh the access token if it's expired. Returns the (possibly new) access token. */
const ensureValidToken = async (): Promise<string | null> => {
  if (!isTokenExpired()) return getAccessToken()

  // Token is expired — try to refresh before the request fires
  const refreshToken = getRefreshToken()
  if (!refreshToken) return null

  // Single-flight: if another refresh is in-flight, wait for it
  if (isRefreshing) {
    return new Promise<string | null>((resolve) => {
      failedQueue.push({ resolve, reject: () => resolve(null) })
    })
  }

  isRefreshing = true
  try {
    const { data } = await authApi.post<{ access: string; refresh?: string }>('/auth/token/refresh/', {
      refresh: refreshToken,
    })
    setAccessToken(data.access)
    if (data.refresh) setRefreshToken(data.refresh)
    processQueue(null, data.access)
    return data.access
  } catch (err) {
    processQueue(err, null)
    return null
  } finally {
    isRefreshing = false
  }
}

// ── Request interceptor ────────────────────────────────────────────────────────

api.interceptors.request.use(
  async (config: InternalAxiosRequestConfig & { _proactiveRefresh?: boolean }) => {
    // Proactively refresh expired tokens before the request fires
    // (prevents 401 → refresh → retry cycle on initial page load)
    if (!config._proactiveRefresh) {
      const validToken = await ensureValidToken()
      if (validToken) config.headers.Authorization = `Bearer ${validToken}`
    } else {
      const token = getAccessToken()
      if (token) config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (err) => Promise.reject(err),
)

// ── Response interceptor — retry + silent refresh ─────────────────────────────

api.interceptors.response.use(
  (res) => res,
  async (
    error: AxiosError & {
      config: InternalAxiosRequestConfig & { _retry?: boolean; _retryCount?: number; _proactiveRefresh?: boolean }
    },
  ) => {
    const originalRequest = error.config
    if (!originalRequest) return Promise.reject(error)

    // Retry on network/5xx
    const retryCount = originalRequest._retryCount ?? 0
    if (shouldRetry(error, retryCount)) {
      originalRequest._retryCount = retryCount + 1
      await new Promise((r) => setTimeout(r, retryDelay(retryCount)))
      return api(originalRequest)
    }

    // Silent JWT refresh on 401
    if (error.response?.status === 401 && !originalRequest._retry) {
      if (isRefreshing) {
        return new Promise<string>((resolve, reject) => {
          failedQueue.push({ resolve, reject })
        }).then((token) => {
          originalRequest.headers.Authorization = `Bearer ${token}`
          originalRequest._proactiveRefresh = true  // skip proactive refresh on retry
          return api(originalRequest)
        })
      }

      originalRequest._retry = true
      originalRequest._proactiveRefresh = true  // skip proactive refresh on retry
      isRefreshing = true

      try {
        const refreshToken = getRefreshToken()
        if (!refreshToken) throw new Error('No refresh token')

        const { data } = await authApi.post<{ access: string; refresh?: string }>('/auth/token/refresh/', {
          refresh: refreshToken,
        })
        setAccessToken(data.access)
        // ROTATE_REFRESH_TOKENS=True: backend issues a new refresh token on every refresh.
        // Save it so the next silent refresh doesn't use the now-blacklisted old token.
        if (data.refresh) setRefreshToken(data.refresh)
        processQueue(null, data.access)
        originalRequest.headers.Authorization = `Bearer ${data.access}`
        return api(originalRequest)
      } catch (refreshErr) {
        processQueue(refreshErr, null)
        clearTokens()
        // Only redirect to login if not on a page that has active long-running
        // operations (e.g. automation polling). Give the user 2s to see the error.
        if (typeof window !== 'undefined') {
          setTimeout(() => { window.location.href = '/login' }, 2000)
        }
        return Promise.reject(refreshErr)
      } finally {
        isRefreshing = false
      }
    }

    // Plan limit exceeded (403 with error_code = plan_limit_exceeded)
    if (error.response?.status === 403) {
      const data = error.response.data as Record<string, unknown> | undefined
      if (data?.error_code === 'plan_limit_exceeded') {
        // Fire the upgrade modal via a custom DOM event so we don't couple api.ts to React context
        if (typeof window !== 'undefined') {
          window.dispatchEvent(new CustomEvent('synapse:plan_limit_exceeded', { detail: data }))
        }
      }
    }

    // TASK-501-F1: Rate limit exceeded (429) → show UpgradeModal with countdown
    if (error.response?.status === 429) {
      const data = error.response.data as Record<string, unknown> | undefined
      const resetAt = (data?.reset_at as string) ?? null
      const upgradeUrl = (data?.upgrade_url as string) ?? '/pricing'
      const message = (data?.message as string) ?? 'Rate limit exceeded. Please upgrade your plan for higher limits.'
      if (typeof window !== 'undefined') {
        window.dispatchEvent(
          new CustomEvent('synapse:rate_limit_exceeded', {
            detail: { resetAt, upgradeUrl, message, data },
          }),
        )
      }
    }

    return Promise.reject(error)
  },
)

function shouldRetry(error: AxiosError, retryCount: number): boolean {
  if (retryCount >= MAX_RETRIES) return false
  if (error.response?.status === 401) return false
  if (!error.response) return true
  return RETRY_STATUS.has(error.response.status)
}

// ── Error normaliser ───────────────────────────────────────────────────────────

export interface ApiErrorPayload {
  message: string
  status:  number
  detail?: unknown
}

export function normaliseApiError(error: unknown): ApiErrorPayload {
  if (axios.isAxiosError(error)) {
    const status = error.response?.status ?? 0
    const data   = error.response?.data
    const message =
      (typeof data === 'object' && data !== null
        ? (data as Record<string, unknown>).detail ??
          (data as Record<string, unknown>).message ??
          (data as Record<string, unknown>).error
        : null) ??
      error.message ??
      'An unexpected error occurred.'
    return { message: String(message), status, detail: data }
  }
  return { message: 'An unexpected error occurred.', status: 0 }
}

export default api
