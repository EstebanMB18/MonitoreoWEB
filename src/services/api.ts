import type {
  DashboardResponse,
  HealthResponse,
  MonitorsResponse,
} from '../types/api'

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, '') ??
  'http://127.0.0.1:8000'

async function request<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      Accept: 'application/json',
    },
  })

  if (!response.ok) {
    throw new Error(`API ${response.status}: ${response.statusText}`)
  }

  return response.json() as Promise<T>
}

export const api = {
  health: () => request<HealthResponse>('/api/health'),
  monitors: () => request<MonitorsResponse>('/api/monitors'),
  dashboard: () => request<DashboardResponse>('/api/dashboard'),
}

export { API_BASE_URL }
