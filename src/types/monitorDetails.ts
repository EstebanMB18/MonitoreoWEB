export interface MonitorMetric {
  id: string
  metric: string
  value: number | string | null
  status: string
  severity?: string | null
  query_ok?: boolean
  technical_error?: string | null
  detail?: string | null
  raw_status?: string | null

  cantidad_ok?: number
  cantidad_total?: number
  cantidad_fallida?: number

  valor_ok?: number
  ultima_ok?: string | null

  medio_pago?: string | null
  medio_salida?: string | null

  [key: string]: unknown
}

export interface MonitorServiceDetail {
  id: string
  name: string
  status: string
  metrics: MonitorMetric[]
}

export interface MonitorGroupDetail {
  id: string
  name: string
  code?: string | null
  services: MonitorServiceDetail[]
}

export interface MonitorDetailsSummary {
  rows?: number
  verticals?: number
  cantidad_total?: number
  cantidad_ok?: number
  cantidad_fallida?: number
  business_alerts?: number
  technical_errors?: number
  technical_warnings?: number

  [key: string]: unknown
}

export interface StructuredMonitorDetails {
  summary?: MonitorDetailsSummary
  groups?: MonitorGroupDetail[]
  business_alerts?: unknown[]
  technical_errors?: unknown[]
  technical_warnings?: unknown[]
  series?: Record<string, unknown>

  [key: string]: unknown
}

export function isStructuredMonitorDetails(
  value: unknown,
): value is StructuredMonitorDetails {
  if (
    typeof value !== 'object' ||
    value === null
  ) {
    return false
  }

  const candidate =
    value as StructuredMonitorDetails

  return (
    Array.isArray(candidate.groups) ||
    typeof candidate.summary === 'object'
  )
}
