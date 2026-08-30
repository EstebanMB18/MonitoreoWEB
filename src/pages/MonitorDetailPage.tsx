import {
  useEffect,
  useState,
} from 'react'

import { StatusBadge } from '../components/StatusBadge'
import { api } from '../services/api'

import type {
  DashboardMonitor,
  RunDetail,
} from '../types/api'

import {
  isStructuredMonitorDetails,
  type MonitorMetric,
  type StructuredMonitorDetails,
} from '../types/monitorDetails'

interface MonitorDetailPageProps {
  monitor: DashboardMonitor | null
  onBack: () => void
}

function formatNumber(
  value: number | null | undefined,
) {
  if (
    value === null ||
    value === undefined
  ) {
    return '—'
  }

  return new Intl.NumberFormat(
    'es-CO',
  ).format(value)
}

function formatMoney(
  value: number | null | undefined,
) {
  if (!value) {
    return '$ 0'
  }

  return new Intl.NumberFormat(
    'es-CO',
    {
      style: 'currency',
      currency: 'COP',
      maximumFractionDigits: 0,
    },
  ).format(value)
}

function detailStatusClass(
  status?: string | null,
) {
  const normalized =
    status?.toUpperCase() ?? ''

  if (
    normalized === 'OK' ||
    normalized === 'NORMAL' ||
    normalized === 'NORMALIDAD'
  ) {
    return 'detail-pill ok'
  }

  if (
    normalized.includes('ALERT') ||
    normalized === 'ERROR'
  ) {
    return 'detail-pill error'
  }

  if (
    normalized.includes('WARN') ||
    normalized === 'REVISAR'
  ) {
    return 'detail-pill warning'
  }

  if (
    normalized === 'LEARNING' ||
    normalized === 'APRENDIENDO'
  ) {
    return 'detail-pill learning'
  }

  return 'detail-pill neutral'
}

function metricRatio(
  metric: MonitorMetric,
) {
  const total =
    metric.cantidad_total ?? 0

  const ok =
    metric.cantidad_ok ?? 0

  if (total <= 0) {
    return 0
  }

  return Math.max(
    0,
    Math.min(
      100,
      (ok / total) * 100,
    ),
  )
}

function PasarelasDetail({
  details,
}: {
  details: StructuredMonitorDetails
}) {
  const summary =
    details.summary ?? {}

  const groups =
    details.groups ?? []

  const alertGroups =
    groups.filter((group) =>
      group.services.some(
        (service) =>
          service.status
            .toUpperCase()
            .includes('ALERT') ||
          service.metrics.some(
            (metric) =>
              metric.status
                .toUpperCase()
                .includes('ALERT'),
          ),
      ),
    )

  return (
    <>
      <section className="monitor-detail-kpis">
        <article>
          <span>Verticales</span>
          <strong>
            {formatNumber(
              summary.verticals,
            )}
          </strong>
        </article>

        <article>
          <span>Métricas</span>
          <strong>
            {formatNumber(
              summary.rows,
            )}
          </strong>
        </article>

        <article>
          <span>Aprobadas</span>
          <strong>
            {formatNumber(
              summary.cantidad_ok,
            )}
          </strong>
        </article>

        <article>
          <span>Total observado</span>
          <strong>
            {formatNumber(
              summary.cantidad_total,
            )}
          </strong>
        </article>

        <article>
          <span>Fallidas</span>
          <strong>
            {formatNumber(
              summary.cantidad_fallida,
            )}
          </strong>
        </article>

        <article>
          <span>Verticales con alerta</span>
          <strong>
            {alertGroups.length}
          </strong>
        </article>
      </section>

      {alertGroups.length > 0 && (
        <section className="monitor-alert-summary">
          <div>
            <span className="section-eyebrow">
              Atención requerida
            </span>

            <h2>
              Alertas detectadas
            </h2>
          </div>

          <div className="monitor-alert-list">
            {alertGroups.map(
              (group) => (
                <article
                  key={group.id}
                  className="monitor-alert-item"
                >
                  <strong>
                    {group.name}
                  </strong>

                  <span>
                    Revisar resultados de
                    esta vertical.
                  </span>
                </article>
              ),
            )}
          </div>
        </section>
      )}

      <section className="detail-section-heading">
        <div>
          <span className="section-eyebrow">
            Pasarelas
          </span>

          <h2>
            Detalle por vertical
          </h2>
        </div>

        <span>
          {groups.length} verticales
        </span>
      </section>

      <div className="vertical-detail-list">
        {groups.map((group) => {
          const groupAlert =
            group.services.some(
              (service) =>
                service.status
                  .toUpperCase()
                  .includes('ALERT'),
            )

          return (
            <details
              className={
                groupAlert
                  ? 'vertical-detail-card has-alert'
                  : 'vertical-detail-card'
              }
              key={group.id}
            >
              <summary>
                <div>
                  <span className="vertical-code">
                    {group.code ??
                      group.id}
                  </span>

                  <strong>
                    {group.name}
                  </strong>
                </div>

                <div className="vertical-summary-meta">
                  <span>
                    {
                      group.services
                        .length
                    }{' '}
                    servicio
                    {group.services
                      .length === 1
                      ? ''
                      : 's'}
                  </span>

                  <span>
                    {group.services.reduce(
                      (
                        total,
                        service,
                      ) =>
                        total +
                        service.metrics
                          .length,
                      0,
                    )}{' '}
                    métricas
                  </span>
                </div>
              </summary>

              <div className="vertical-services">
                {group.services.map(
                  (service) => (
                    <section
                      className="service-detail"
                      key={service.id}
                    >
                      <header>
                        <div>
                          <span>
                            Servicio
                          </span>

                          <h3>
                            {service.name}
                          </h3>
                        </div>

                        <span
                          className={detailStatusClass(
                            service.status,
                          )}
                        >
                          {service.status}
                        </span>
                      </header>

                      <div className="metric-table-wrap">
                        <table className="metric-table">
                          <thead>
                            <tr>
                              <th>
                                Medio
                              </th>
                              <th>
                                Estado
                              </th>
                              <th>
                                OK
                              </th>
                              <th>
                                Total
                              </th>
                              <th>
                                Fallidas
                              </th>
                              <th>
                                Calidad
                              </th>
                              <th>
                                Valor OK
                              </th>
                              <th>
                                Última OK
                              </th>
                            </tr>
                          </thead>

                          <tbody>
                            {service.metrics.map(
                              (
                                metric,
                              ) => {
                                const ratio =
                                  metricRatio(
                                    metric,
                                  )

                                return (
                                  <tr
                                    key={
                                      metric.id
                                    }
                                  >
                                    <td>
                                      <div className="metric-name-cell">
                                        <strong>
                                          {
                                            metric.metric
                                          }
                                        </strong>

                                        {metric.detail && (
                                          <span>
                                            {
                                              metric.detail
                                            }
                                          </span>
                                        )}
                                      </div>
                                    </td>

                                    <td>
                                      <span
                                        className={detailStatusClass(
                                          metric.status,
                                        )}
                                      >
                                        {
                                          metric.status
                                        }
                                      </span>
                                    </td>

                                    <td>
                                      {formatNumber(
                                        metric.cantidad_ok,
                                      )}
                                    </td>

                                    <td>
                                      {formatNumber(
                                        metric.cantidad_total,
                                      )}
                                    </td>

                                    <td>
                                      <strong
                                        className={
                                          (
                                            metric.cantidad_fallida ??
                                            0
                                          ) > 0
                                            ? 'metric-failed'
                                            : undefined
                                        }
                                      >
                                        {formatNumber(
                                          metric.cantidad_fallida,
                                        )}
                                      </strong>
                                    </td>

                                    <td>
                                      <div className="metric-quality">
                                        <div>
                                          <span
                                            style={{
                                              width: `${ratio}%`,
                                            }}
                                          />
                                        </div>

                                        <small>
                                          {ratio.toFixed(
                                            0,
                                          )}
                                          %
                                        </small>
                                      </div>
                                    </td>

                                    <td>
                                      {formatMoney(
                                        metric.valor_ok,
                                      )}
                                    </td>

                                    <td>
                                      {metric.ultima_ok ??
                                        '—'}
                                    </td>
                                  </tr>
                                )
                              },
                            )}
                          </tbody>
                        </table>
                      </div>
                    </section>
                  ),
                )}
              </div>
            </details>
          )
        })}
      </div>
    </>
  )
}

export function MonitorDetailPage({
  monitor,
  onBack,
}: MonitorDetailPageProps) {
  const [run, setRun] =
    useState<RunDetail | null>(null)

  const [loading, setLoading] =
    useState(false)

  const [error, setError] =
    useState<string | null>(null)

  useEffect(() => {
    if (!monitor?.last_run_id) {
      return
    }

    const runId =
      monitor.last_run_id

    const timer =
      window.setTimeout(() => {
        setLoading(true)
        setError(null)

        void api
          .runDetail(runId)
          .then(setRun)
          .catch((err: unknown) => {
            setError(
              err instanceof Error
                ? err.message
                : 'No fue posible cargar el detalle.',
            )
          })
          .finally(() =>
            setLoading(false),
          )
      }, 0)

    return () =>
      window.clearTimeout(timer)
  }, [monitor])

  if (!monitor) {
    return (
      <section className="detail-empty-state">
        <strong>
          Monitor no disponible
        </strong>

        <button
          type="button"
          onClick={onBack}
        >
          Volver
        </button>
      </section>
    )
  }

  const structuredDetails =
    isStructuredMonitorDetails(
      run?.details,
    )
      ? run.details
      : null

  return (
    <div className="monitor-detail-page">
      <button
        type="button"
        className="detail-back-button"
        onClick={onBack}
      >
        ← Volver al centro
      </button>

      <section className="monitor-detail-hero">
        <div>
          <span className="section-eyebrow">
            Detalle del monitor
          </span>

          <h1>{monitor.name}</h1>

          <p>
            Resultado estructurado de la
            última ejecución disponible.
          </p>
        </div>

        <div className="monitor-detail-hero-meta">
          <StatusBadge
            status={monitor.status}
          />

          <div>
            <span>
              Última ejecución
            </span>
            <strong>
              {monitor.last_run_type ??
                '—'}
            </strong>
          </div>

          <div>
            <span>Run ID</span>
            <strong>
              {monitor.last_run_id
                ? monitor.last_run_id.slice(
                    0,
                    12,
                  )
                : '—'}
            </strong>
          </div>
        </div>
      </section>

      {loading && (
        <section className="detail-empty-state">
          <strong>
            Cargando detalle...
          </strong>
        </section>
      )}

      {error && (
        <section className="detail-error-state">
          <strong>
            No fue posible cargar el run
          </strong>
          <span>{error}</span>
        </section>
      )}

      {!loading &&
        !error &&
        !monitor.last_run_id && (
          <section className="detail-empty-state">
            <strong>
              Sin ejecuciones disponibles
            </strong>

            <span>
              Este monitor todavía no
              tiene un run registrado.
            </span>
          </section>
        )}

      {!loading &&
        !error &&
        run &&
        !structuredDetails && (
          <section className="detail-empty-state">
            <strong>
              Sin detalle estructurado
            </strong>

            <span>
              El run existe, pero el backend
              todavía no entregó
              información en
              <code> details </code>.
            </span>
          </section>
        )}

      {!loading &&
        !error &&
        run &&
        structuredDetails &&
        monitor.id === 'pasarelas' && (
          <PasarelasDetail
            details={structuredDetails}
          />
        )}
    </div>
  )
}
