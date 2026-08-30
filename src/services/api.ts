import type {
  DashboardResponse,
  HealthResponse,
  MonitorsResponse,
  RunDetail,
  RunRequest,
} from '../types/api'

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, '') ??
  'http://127.0.0.1:8000'

async function request<T>(
  path: string,
  options?: RequestInit,
): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      Accept: 'application/json',
      ...(options?.body
        ? { 'Content-Type': 'application/json' }
        : {}),
      ...options?.headers,
    },
  })

  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`

    try {
      const body = (await response.json()) as {
        detail?: string
      }

      if (body.detail) {
        detail = body.detail
      }
    } catch {
      // La respuesta puede no contener JSON.
    }

    throw new Error(`API: ${detail}`)
  }

  return response.json() as Promise<T>
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
      `/api/monitors/${encodeURIComponent(monitorId)}/run`,
      {
        method: 'POST',
        body: JSON.stringify(payload),
      },
    ),

  runDetail: (runId: string) =>
    request<RunDetail>(
      `/api/runs/${encodeURIComponent(runId)}`,
    ),
}

export { API_BASE_URL }
