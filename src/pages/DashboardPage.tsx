import {
  useCallback,
  useEffect,
  useRef,
  useState,
} from 'react'

import { MonitorCard } from '../components/MonitorCard'
import { StatusBadge } from '../components/StatusBadge'
import { api } from '../services/api'

import type {
  DashboardResponse,
  HealthResponse,
  RunDetail,
  RunStatus,
} from '../types/api'

import { parseAlert } from '../utils/alerts'

interface DashboardPageProps {
  onBackendStatusChange: (online: boolean) => void
  onViewMonitor: (monitorId: string) => void
  canExecuteManual: boolean
}

const terminalStates = new Set<RunStatus>([
  'OK',
  'WARNING',
  'ERROR',
  'TIMEOUT',
  'CANCELLED',
  'NO_DATA',
  'STALE',
])

export function DashboardPage({
  onBackendStatusChange,
  onViewMonitor,
  canExecuteManual,
}: DashboardPageProps) {
  const [health, setHealth] =
    useState<HealthResponse | null>(null)

  const [dashboard, setDashboard] =
    useState<DashboardResponse | null>(null)

  const [loading, setLoading] = useState(true)

  const [error, setError] =
    useState<string | null>(null)

  const [activeRuns, setActiveRuns] =
    useState<Record<string, RunDetail>>({})

  const [runErrors, setRunErrors] =
    useState<Record<string, string>>({})

  const [startingMonitors, setStartingMonitors] =
    useState<Record<string, boolean>>({})

  const pollTimers = useRef<
    Record<string, number>
  >({})

  const loadDashboard = useCallback(async () => {
    try {
      const [
        healthResponse,
        dashboardResponse,
      ] = await Promise.all([
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

  const stopPolling = useCallback(
    (monitorId: string) => {
      const timer =
        pollTimers.current[monitorId]

      if (timer != null) {
        window.clearTimeout(timer)
        delete pollTimers.current[monitorId]
      }
    },
    [],
  )

  const pollRun = useCallback(
    async function pollRunTask(
      monitorId: string,
      runId: string,
    ): Promise<void> {
      try {
        const run = await api.runDetail(runId)

        setActiveRuns((current) => ({
          ...current,
          [monitorId]: run,
        }))

        setRunErrors((current) => {
          const next = { ...current }
          delete next[monitorId]
          return next
        })

        if (terminalStates.has(run.status)) {
          stopPolling(monitorId)
          await loadDashboard()
          return
        }

        pollTimers.current[monitorId] =
          window.setTimeout(() => {
            void pollRunTask(monitorId, runId)
          }, 2000)
      } catch (err) {
        stopPolling(monitorId)

        setRunErrors((current) => ({
          ...current,
          [monitorId]:
            err instanceof Error
              ? err.message
              : 'No fue posible consultar la ejecución',
        }))
      }
    },
    [loadDashboard, stopPolling],
  )

  const runMonitor = useCallback(
    async (monitorId: string) => {
      setStartingMonitors((current) => ({
        ...current,
        [monitorId]: true,
      }))

      setRunErrors((current) => {
        const next = { ...current }
        delete next[monitorId]
        return next
      })

      try {
        const run = await api.runMonitor(
          monitorId,
          {
            run_type: 'MANUAL',
            reason: 'Ejecución manual desde NEXUS',
          },
        )

        setActiveRuns((current) => ({
          ...current,
          [monitorId]: run,
        }))

        void pollRun(
          monitorId,
          run.run_id,
        )
      } catch (err) {
        setRunErrors((current) => ({
          ...current,
          [monitorId]:
            err instanceof Error
              ? err.message
              : 'No fue posible iniciar el monitor',
        }))
      } finally {
        setStartingMonitors((current) => ({
          ...current,
          [monitorId]: false,
        }))
      }
    },
    [pollRun],
  )

  useEffect(() => {
    const timers = pollTimers.current

    const initialLoad =
      window.setTimeout(() => {
        void loadDashboard()
      }, 0)

    const interval =
      window.setInterval(() => {
        void loadDashboard()
      }, 15000)

    return () => {
      window.clearTimeout(initialLoad)
      window.clearInterval(interval)

      Object.values(timers).forEach((timer) => {
        window.clearTimeout(timer)
      })
    }
  }, [loadDashboard])

  if (loading) {
    return (
      <section className="state-panel">
        <div className="loading-ring" />
        <h2>Conectando con NEXUS</h2>
        <p>
          Consultando el estado actual de la operación.
        </p>
      </section>
    )
  }

  if (!dashboard || error) {
    return (
      <section className="state-panel error-panel">
        <span className="state-icon">!</span>
        <h2>Backend no disponible</h2>
        <p>
          {error ??
            'No fue posible obtener el dashboard.'}
        </p>

        <button
          type="button"
          onClick={() =>
            void loadDashboard()
          }
        >
          Reintentar conexión
        </button>
      </section>
    )
  }

  return (
    <div className="dashboard">
      <section className="operation-hero">
        <div>
          <p className="section-eyebrow">
            Estado general de la operación
          </p>

          <div className="operation-title">
            <h2>Visión consolidada</h2>

            <StatusBadge
              status={dashboard.overall_status}
            />
          </div>

          <p>
            Información operacional obtenida
            directamente del backend local.
          </p>
        </div>

        <div className="hero-facts">
          <div>
            <span>Servicio</span>
            <strong>
              {health?.service ?? 'NEXUS'}
            </strong>
          </div>

          <div>
            <span>Monitores</span>
            <strong>
              {dashboard.monitors.length}
            </strong>
          </div>

          <div>
            <span>Alertas activas</span>
            <strong>
              {dashboard.active_alerts.length}
            </strong>
          </div>
        </div>
      </section>

      <section className="section-block">
        <div className="section-heading">
          <div>
            <p className="section-eyebrow">
              Operación
            </p>

            <h2>Monitores</h2>
          </div>

          <span className="refresh-note">
            Dashboard 15 s · Runs 2 s
          </span>
        </div>

        <div className="monitor-grid">
          {dashboard.monitors.map(
            (monitor) => (
              <MonitorCard
                key={monitor.id}
                monitor={monitor}
                activeRun={
                  activeRuns[monitor.id]
                }
                runError={
                  runErrors[monitor.id]
                }
                starting={
                  startingMonitors[
                    monitor.id
                  ] ?? false
                }
                onRun={
                  canExecuteManual
                    ? runMonitor
                    : undefined
                }
                canExecuteManual={
                  canExecuteManual
                }
                onViewDetail={onViewMonitor}
              />
            ),
          )}
        </div>
      </section>

      <section className="section-block">
        <div className="section-heading">
          <div>
            <p className="section-eyebrow">
              Atención requerida
            </p>

            <h2>Alertas activas</h2>
          </div>

          <span className="alert-count">
            {dashboard.active_alerts.length}
          </span>
        </div>

        {dashboard.active_alerts.length ===
        0 ? (
          <div className="empty-alerts">
            <span>✓</span>

            <div>
              <strong>
                Sin alertas activas
              </strong>

              <p>
                La operación no reporta
                novedades en este momento.
              </p>
            </div>
          </div>
        ) : (
          <div className="alerts-list">
            {dashboard.active_alerts.map(
              (alert, index) => {
                const parsed =
                  parseAlert(alert.message)

                return (
                  <article
                    className="alert-row"
                    key={`${alert.run_id}-${index}`}
                  >
                    <div className="alert-severity">
                      {parsed.nivel ??
                        'ALERTA'}
                    </div>

                    <div className="alert-content">
                      <div className="alert-heading">
                        <strong>
                          {parsed.servicio ??
                            alert.monitor}
                        </strong>

                        <span>
                          {parsed.grupo ??
                            alert.monitor}
                        </span>
                      </div>

                      <p>
                        {parsed.metrica ??
                          parsed.detalle ??
                          alert.message}
                      </p>

                      {parsed.detalle &&
                        parsed.metrica &&
                        parsed.detalle !==
                          parsed.metrica && (
                          <small>
                            {parsed.detalle}
                          </small>
                        )}
                    </div>

                    <div className="alert-monitor">
                      {alert.monitor}
                    </div>
                  </article>
                )
              },
            )}
          </div>
        )}
      </section>
    </div>
  )
}

