import type {
  DashboardResponse,
  HealthResponse,
  MonitorsResponse,
  RunDetail,
  RunRequest,
} from '../types/api'

import type {
  AuthStatus,
  AuthUser,
  BootstrapRequest,
  LoginRequest,
  LoginResponse,
  MFASetupResponse,
} from '../types/auth'

import {
  clearAccessToken,
  getAccessToken,
} from './authSession'

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ??
  'http://127.0.0.1:8000'

async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const headers = new Headers(options.headers)

  headers.set('Accept', 'application/json')

  if (options.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }

  const token = getAccessToken()

  if (token) {
    headers.set('Authorization', `Bearer ${token}`)
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
  })

  if (response.status === 401 && token) {
    clearAccessToken()

    window.dispatchEvent(
      new CustomEvent('nexus:auth-expired'),
    )
  }

  if (!response.ok) {
    let detail = `HTTP ${response.status}`

    try {
      const payload = (await response.json()) as {
        detail?: string
        message?: string
      }

      detail =
        payload.detail ??
        payload.message ??
        detail
    } catch {
      // Respuesta sin JSON.
    }

    throw new Error(detail)
  }

  if (response.status === 204) {
    return undefined as T
  }

  return (await response.json()) as T
}

export const api = {
  health: () =>
    request<HealthResponse>('/api/health'),

  monitors: () =>
    request<MonitorsResponse>('/api/monitors'),

  dashboard: () =>
    request<DashboardResponse>('/api/dashboard'),

  runMonitor: (
    monitorId: string,
    payload: RunRequest = {
      run_type: 'MANUAL',
    },
  ) =>
    request<RunDetail>(
      `/api/monitors/${monitorId}/run`,
      {
        method: 'POST',
        body: JSON.stringify(payload),
      },
    ),

  runDetail: (runId: string) =>
    request<RunDetail>(`/api/runs/${runId}`),

  authStatus: () =>
    request<AuthStatus>('/api/auth/status'),

  bootstrap: (payload: BootstrapRequest) =>
    request<Record<string, unknown>>(
      '/api/auth/bootstrap',
      {
        method: 'POST',
        body: JSON.stringify(payload),
      },
    ),

  login: (payload: LoginRequest) =>
    request<LoginResponse>('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  me: () =>
    request<AuthUser>('/api/auth/me'),

  logout: () =>
    request<Record<string, unknown>>(
      '/api/auth/logout',
      {
        method: 'POST',
      },
    ),

  mfaSetup: () =>
    request<MFASetupResponse>(
      '/api/auth/mfa/setup',
      {
        method: 'POST',
      },
    ),

  mfaConfirm: (code: string) =>
    request<Record<string, unknown>>(
      '/api/auth/mfa/confirm',
      {
        method: 'POST',
        body: JSON.stringify({ code }),
      },
    ),
}
