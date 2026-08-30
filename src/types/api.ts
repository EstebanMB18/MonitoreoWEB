export type RunStatus =
  | 'PENDING'
  | 'PREPARING'
  | 'RUNNING'
  | 'PROCESSING'
  | 'PUBLISHING'
  | 'OK'
  | 'WARNING'
  | 'ERROR'
  | 'TIMEOUT'
  | 'CANCELLED'
  | 'NO_DATA'
  | 'STALE'

export interface HealthResponse {
  status: string
  service: string
}

export interface MonitorDefinition {
  id: string
  name: string
  enabled: boolean
  supports_manual_run: boolean
}

export interface MonitorsResponse {
  items: MonitorDefinition[]
  total: number
}

export interface DashboardMonitor extends MonitorDefinition {
  status: RunStatus
  progress: number
  records: number | null
  alerts: string[]
  last_run_id: string | null
  last_run_type?: string | null
  duration_seconds?: number | null
}

export interface DashboardAlert {
  monitor: string
  message: string
  run_id: string
}

export interface DashboardResponse {
  overall_status: RunStatus
  monitors: DashboardMonitor[]
  active_alerts: DashboardAlert[]
}

export interface ParsedAlert {
  nivel?: string
  grupo?: string
  servicio?: string
  metrica?: string
  valor?: number | string
  detalle?: string
  raw: string
}

export type RunType =
  | 'OFFICIAL'
  | 'MANUAL'
  | 'INCIDENT'
  | 'TEST'

export interface RunRequest {
  run_type?: RunType
  cut?: string | null
  reason?: string | null
}

export interface RunEvent {
  event_id: string
  timestamp: string
  run_id: string
  monitor: string
  level: string
  event_type: string
  message: string
  progress: number | null
  data: unknown
}

export interface RunDetail {
  run_id: string
  monitor: string
  run_type: RunType
  cut: string | null
  reason: string | null

  status: RunStatus
  progress: number
  current_message?: string | null

  official: boolean
  historical: boolean
  publish_allowed: boolean
  installation_mode: string

  created_at: string
  started_at: string | null
  finished_at: string | null
  duration_seconds: number | null

  records: number | null
  alerts: string[]
  errors: string[]

  outputs: Record<string, string>
  metadata: Record<string, unknown>
  details?: unknown
  events: RunEvent[]
}
