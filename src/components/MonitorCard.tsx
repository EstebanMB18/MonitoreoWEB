import type {
  DashboardMonitor,
  RunDetail,
} from '../types/api'
import { StatusBadge } from './StatusBadge'

interface MonitorCardProps {
  monitor: DashboardMonitor
  activeRun?: RunDetail | null
  runError?: string | null
  starting?: boolean
  onRun?: (monitorId: string) => void
  canExecuteManual?: boolean
  onViewDetail?: (monitorId: string) => void
}

const activeStates = new Set([
  'PENDING',
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

export function MonitorCard({
  monitor,
  activeRun,
  runError,
  starting = false,
  onRun,
  canExecuteManual = false,
  onViewDetail,
}: MonitorCardProps) {
  const visibleRun = activeRun ?? null

  const visibleStatus =
    visibleRun?.status ?? monitor.status

  const visibleProgress =
    visibleRun?.progress ?? monitor.progress

  const visibleRecords =
    visibleRun?.records ?? monitor.records

  const visibleAlerts =
    visibleRun?.alerts ?? monitor.alerts

  const visibleDuration =
    visibleRun?.duration_seconds ??
    monitor.duration_seconds

  const isActive =
    visibleRun != null &&
    activeStates.has(visibleRun.status)

  const canRun =
    canExecuteManual &&
    monitor.id === 'aws' &&
    monitor.enabled &&
    monitor.supports_manual_run &&
    !isActive &&
    !starting


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

        <StatusBadge status={visibleStatus} />
      </div>

      {(isActive || starting) && (
        <div className="monitor-progress-block">
          <div className="progress-heading">
            <span>
              {starting
                ? 'Iniciando ejecución'
                : visibleRun?.current_message ??
                  'Ejecución en curso'}
            </span>

            <strong>
              {starting ? '...' : `${visibleProgress}%`}
            </strong>
          </div>

          <div
            className="progress-track"
            role="progressbar"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={visibleProgress}
          >
            <span
              style={{
                width: `${starting ? 3 : visibleProgress}%`,
              }}
            />
          </div>
        </div>
      )}

      {runError && (
        <div className="monitor-run-error">
          {runError}
        </div>
      )}

      <div className="monitor-metrics">
        <div>
          <span>Registros</span>
          <strong>
            {visibleRecords == null
              ? '—'
              : visibleRecords.toLocaleString('es-CO')}
          </strong>
        </div>

        <div>
          <span>Alertas</span>
          <strong>{visibleAlerts.length}</strong>
        </div>

        <div>
          <span>Duración</span>
          <strong>{formatDuration(visibleDuration)}</strong>
        </div>
      </div>

      <div className="monitor-card-footer">
        <span>
          {visibleRun
            ? `${visibleRun.run_type} · ${visibleRun.run_id.slice(0, 8)}`
            : monitor.last_run_type
              ? `Última ejecución · ${monitor.last_run_type}`
              : 'Sin ejecuciones registradas'}
        </span>

        <div className="monitor-actions">
          <button
            type="button"
            className="link-button"
            onClick={() => onViewDetail?.(monitor.id)}
          >
            Ver detalle
          </button>

          {monitor.id === 'aws' &&
            canExecuteManual && (
            <button
              type="button"
              className="run-button"
              disabled={!canRun}
              onClick={() => onRun?.(monitor.id)}
            >
              {starting
                ? 'Iniciando...'
                : isActive
                  ? 'Ejecutando'
                  : 'Ejecutar'}
            </button>
          )}
        </div>
      </div>
    </article>
  )
}

