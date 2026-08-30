import { useCallback, useEffect, useState } from 'react'
import { MonitorCard } from '../components/MonitorCard'
import { StatusBadge } from '../components/StatusBadge'
import { api } from '../services/api'
import type {
  DashboardResponse,
  HealthResponse,
} from '../types/api'
import { parseAlert } from '../utils/alerts'

interface DashboardPageProps {
  onBackendStatusChange: (online: boolean) => void
}

export function DashboardPage({
  onBackendStatusChange,
}: DashboardPageProps) {
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [dashboard, setDashboard] =
    useState<DashboardResponse | null>(null)

  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const loadDashboard = useCallback(async () => {
    try {
      const [healthResponse, dashboardResponse] = await Promise.all([
        api.health(),
        api.dashboard(),
      ])

      setHealth(healthResponse)
      setDashboard(dashboardResponse)
      setError(null)
      onBackendStatusChange(true)
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'No fue posible conectar con el backend',
      )

      onBackendStatusChange(false)
    } finally {
      setLoading(false)
    }
  }, [onBackendStatusChange])

  useEffect(() => {
    void loadDashboard()

    const interval = window.setInterval(() => {
      void loadDashboard()
    }, 15000)

    return () => window.clearInterval(interval)
  }, [loadDashboard])

  if (loading) {
    return (
      <section className="state-panel">
        <div className="loading-ring" />
        <h2>Conectando con NEXUS</h2>
        <p>Consultando el estado actual de la operación.</p>
      </section>
    )
  }

  if (!dashboard || error) {
    return (
      <section className="state-panel error-panel">
        <span className="state-icon">!</span>
        <h2>Backend no disponible</h2>
        <p>{error ?? 'No fue posible obtener el dashboard.'}</p>

        <button type="button" onClick={() => void loadDashboard()}>
          Reintentar conexión
        </button>
      </section>
    )
  }

  return (
    <div className="dashboard">
      <section className="operation-hero">
        <div>
          <p className="section-eyebrow">Estado general de la operación</p>

          <div className="operation-title">
            <h2>Visión consolidada</h2>
            <StatusBadge status={dashboard.overall_status} />
          </div>

          <p>
            Información operacional obtenida directamente del backend local.
          </p>
        </div>

        <div className="hero-facts">
          <div>
            <span>Servicio</span>
            <strong>{health?.service ?? 'NEXUS'}</strong>
          </div>

          <div>
            <span>Monitores</span>
            <strong>{dashboard.monitors.length}</strong>
          </div>

          <div>
            <span>Alertas activas</span>
            <strong>{dashboard.active_alerts.length}</strong>
          </div>
        </div>
      </section>

      <section className="section-block">
        <div className="section-heading">
          <div>
            <p className="section-eyebrow">Operación</p>
            <h2>Monitores</h2>
          </div>

          <span className="refresh-note">
            Actualización automática · 15 s
          </span>
        </div>

        <div className="monitor-grid">
          {dashboard.monitors.map((monitor) => (
            <MonitorCard key={monitor.id} monitor={monitor} />
          ))}
        </div>
      </section>

      <section className="section-block">
        <div className="section-heading">
          <div>
            <p className="section-eyebrow">Atención requerida</p>
            <h2>Alertas activas</h2>
          </div>

          <span className="alert-count">
            {dashboard.active_alerts.length}
          </span>
        </div>

        {dashboard.active_alerts.length === 0 ? (
          <div className="empty-alerts">
            <span>✓</span>
            <div>
              <strong>Sin alertas activas</strong>
              <p>La operación no reporta novedades en este momento.</p>
            </div>
          </div>
        ) : (
          <div className="alerts-list">
            {dashboard.active_alerts.map((alert, index) => {
              const parsed = parseAlert(alert.message)

              return (
                <article
                  className="alert-row"
                  key={`${alert.run_id}-${index}`}
                >
                  <div className="alert-severity">
                    {parsed.nivel ?? 'ALERTA'}
                  </div>

                  <div className="alert-content">
                    <div className="alert-heading">
                      <strong>
                        {parsed.servicio ?? alert.monitor}
                      </strong>

                      <span>{parsed.grupo ?? alert.monitor}</span>
                    </div>

                    <p>
                      {parsed.metrica ??
                        parsed.detalle ??
                        alert.message}
                    </p>

                    {parsed.detalle &&
                      parsed.metrica &&
                      parsed.detalle !== parsed.metrica && (
                        <small>{parsed.detalle}</small>
                      )}
                  </div>

                  <div className="alert-monitor">
                    {alert.monitor}
                  </div>
                </article>
              )
            })}
          </div>
        )}
      </section>
    </div>
  )
}
