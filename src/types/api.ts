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
