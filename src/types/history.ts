export type CoverageStatus =
  | 'EXECUTED'
  | 'SIN_EJECUCION'

export type HistoryOverallStatus =
  | 'OK'
  | 'WARNING'
  | 'ERROR'
  | 'NO_DATA'
  | 'SIN_EJECUCION'
  | string

export interface HistorySnapshot {
  schema_version?: number
  monitor?: string
  date?: string
  coverage?: CoverageStatus | string
  overall_status?: HistoryOverallStatus
  official_runs?: number
  successful_runs?: number
  records?: number
  alerts?: number
  errors?: number
  runs?: unknown[]
}

export interface DailyHistoryItem {
  monitor: string
  closure_date: string
  coverage_status: CoverageStatus | string
  overall_status: HistoryOverallStatus
  official_runs: number
  successful_runs: number
  total_records: number
  alerts_count: number
  errors_count: number
  first_run_at: string | null
  last_run_at: string | null
  created_at: string
  updated_at: string
  snapshot?: HistorySnapshot
}

export interface DailyHistoryResponse {
  items: DailyHistoryItem[]
  total: number
}

export interface DailyMonitorHistoryResponse {
  monitor: string
  items: DailyHistoryItem[]
  total: number
}

export interface HistoryFilters {
  monitor?: string | null
  start_date?: string | null
  end_date?: string | null
  closure_date?: string | null
}
