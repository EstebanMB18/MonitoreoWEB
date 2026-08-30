import { StatusBadge } from '../components/StatusBadge'
import type { DashboardMonitor } from '../types/api'

interface MonitorDetailPageProps {
  monitor: DashboardMonitor | null
  onBack: () => void
}

function formatDuration(seconds?: number | null) {
  if (seconds == null) return '—'

  if (seconds < 60) {
    return `${seconds.toFixed(0)} s`
  }

  const minutes = Math.floor(seconds / 60)
  const remaining = Math.round(seconds % 60)

  return `${minutes}m ${remaining}s`
}

export function MonitorDetailPage({
  monitor,
  onBack,
}: MonitorDetailPageProps) {
  if (!monitor) {
    return (
      <section className="state-panel">
        <span className="state-icon">!</span>
        <h2>Monitor no disponible</h2>
        <p>No fue posible cargar el monitor seleccionado.</p>

        <button type="button" onClick={onBack}>
          Volver
        </button>
      </section>
    )
  }

  return (
    <div className="monitor-detail-page">
      <div className="detail-toolbar">
        <button
          type="button"
          className="back-button"
          onClick={onBack}
        >
          ← Volver
        </button>

        <StatusBadge status={monitor.status} />
      </div>

      <section className="detail-hero">
        <div>
          <p className="section-eyebrow">Detalle del monitor</p>
          <h2>{monitor.name}</h2>

          <p>
            Estado y resultados de la última ejecución disponible.
          </p>
        </div>

        <div className="detail-run-info">
          <div>
            <span>Última ejecución</span>
            <strong>{monitor.last_run_type ?? '—'}</strong>
          </div>

          <div>
            <span>Run ID</span>
            <strong>
              {monitor.last_run_id
                ? monitor.last_run_id.slice(0, 12)
                : '—'}
            </strong>
          </div>
        </div>
      </section>

      <section className="detail-metrics-grid">
        <article className="detail-metric-card">
          <span>Progreso</span>
          <strong>{monitor.progress}%</strong>
        </article>

        <article className="detail-metric-card">
          <span>Registros</span>
          <strong>
            {monitor.records == null
              ? '—'
              : monitor.records.toLocaleString('es-CO')}
          </strong>
        </article>

        <article className="detail-metric-card">
          <span>Alertas</span>
          <strong>{monitor.alerts.length}</strong>
        </article>

        <article className="detail-metric-card">
          <span>Duración</span>
          <strong>{formatDuration(monitor.duration_seconds)}</strong>
        </article>
      </section>

      <section className="detail-section">
        <div className="section-heading">
          <div>
            <p className="section-eyebrow">Resultado</p>
            <h2>Estado actual</h2>
          </div>
        </div>

        <div className="detail-status-panel">
          <div>
            <span>Estado</span>
            <StatusBadge status={monitor.status} />
          </div>

          <div>
            <span>Alertas registradas</span>
            <strong>{monitor.alerts.length}</strong>
          </div>

          <div>
            <span>Último tipo de ejecución</span>
            <strong>{monitor.last_run_type ?? '—'}</strong>
          </div>
        </div>
      </section>
    </div>
  )
}
