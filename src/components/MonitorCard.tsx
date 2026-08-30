import type { DashboardMonitor } from '../types/api'
import { StatusBadge } from './StatusBadge'

interface MonitorCardProps {
  monitor: DashboardMonitor
}

const activeStates = new Set([
  'PREPARING',
  'RUNNING',
  'PROCESSING',
  'PUBLISHING',
])

function formatDuration(seconds?: number | null) {
  if (seconds == null) return '—'

  if (seconds < 60) {
    return `${seconds.toFixed(0)} s`
  }

  const minutes = Math.floor(seconds / 60)
  const remaining = Math.round(seconds % 60)

  return `${minutes}m ${remaining}s`
}

export function MonitorCard({ monitor }: MonitorCardProps) {
  const isActive = activeStates.has(monitor.status)

  return (
    <article className="monitor-card">
      <div className="monitor-card-header">
        <div className="monitor-identity">
          <div className="monitor-icon">
            {monitor.name.slice(0, 1).toUpperCase()}
          </div>

          <div>
            <p className="monitor-eyebrow">Monitor</p>
            <h3>{monitor.name}</h3>
          </div>
        </div>

        <StatusBadge status={monitor.status} />
      </div>

      {isActive && (
        <div className="monitor-progress-block">
          <div className="progress-heading">
            <span>Progreso</span>
            <strong>{monitor.progress}%</strong>
          </div>

          <div
            className="progress-track"
            role="progressbar"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={monitor.progress}
          >
            <span style={{ width: `${monitor.progress}%` }} />
          </div>
        </div>
      )}

      <div className="monitor-metrics">
        <div>
          <span>Registros</span>
          <strong>
            {monitor.records == null
              ? '—'
              : monitor.records.toLocaleString('es-CO')}
          </strong>
        </div>

        <div>
          <span>Alertas</span>
          <strong>{monitor.alerts.length}</strong>
        </div>

        <div>
          <span>Duración</span>
          <strong>{formatDuration(monitor.duration_seconds)}</strong>
        </div>
      </div>

      <div className="monitor-card-footer">
        <span>
          {monitor.last_run_type
            ? `Última ejecución · ${monitor.last_run_type}`
            : 'Sin ejecuciones registradas'}
        </span>

        <button type="button" className="link-button">
          Ver detalle
        </button>
      </div>
    </article>
  )
}
