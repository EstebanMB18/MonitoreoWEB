import type { RunStatus } from '../types/api'

interface StatusBadgeProps {
  status: RunStatus
}

const labels: Record<RunStatus, string> = {
  PENDING: 'Pendiente',
  PREPARING: 'Preparando',
  RUNNING: 'Ejecutando',
  PROCESSING: 'Procesando',
  PUBLISHING: 'Publicando',
  OK: 'Normal',
  WARNING: 'Advertencia',
  ERROR: 'Error',
  TIMEOUT: 'Timeout',
  CANCELLED: 'Cancelado',
  NO_DATA: 'Sin datos',
  STALE: 'Desactualizado',
}

export function StatusBadge({ status }: StatusBadgeProps) {
  return (
    <span className={`status-badge status-${status.toLowerCase()}`}>
      <span className="status-dot" />
      {labels[status] ?? status}
    </span>
  )
}
