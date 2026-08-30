import {
  useEffect,
  useState,
} from 'react'

import { api } from '../services/api'
import type {
  DashboardMonitor,
  RunDetail,
} from '../types/api'

import {
  isStructuredMonitorDetails,
  type StructuredMonitorDetails,
} from '../types/monitorDetails'

interface CaptureOverviewProps {
  monitors: DashboardMonitor[]
}

type RunMap = Record<string, RunDetail>

function numberValue(
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

function statusClass(status: string) {
  const normalized =
    status.toUpperCase()

  if (
    normalized === 'OK' ||
    normalized === 'NORMAL'
  ) {
    return 'capture-status ok'
  }

  if (
    normalized === 'WARNING' ||
    normalized.includes('WARN')
  ) {
    return 'capture-status warning'
  }

  if (
    normalized === 'ERROR' ||
    normalized === 'ALERT' ||
    normalized === 'ALERTA'
  ) {
    return 'capture-status error'
  }

  return 'capture-status neutral'
}

function findMonitor(
  monitors: DashboardMonitor[],
  id: string,
) {
  return monitors.find(
    (monitor) =>
      monitor.id.toLowerCase() === id,
  )
}

function PasarelasCapture({
  monitor,
  run,
}: {
  monitor: DashboardMonitor
  run?: RunDetail
}) {
  const details =
    isStructuredMonitorDetails(
      run?.details,
    )
      ? run.details
      : null

  const summary =
    details?.summary ?? {}

  const groups =
    details?.groups ?? []

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

  const topGroups =
    groups
      .map((group) => {
        const totals =
          group.services.reduce(
            (acc, service) => {
              service.metrics.forEach(
                (metric) => {
                  acc.ok +=
                    metric.cantidad_ok ?? 0
                  acc.total +=
                    metric.cantidad_total ??
                    0
                  acc.failed +=
                    metric.cantidad_fallida ??
                    0
                },
              )

              return acc
            },
            {
              ok: 0,
              total: 0,
              failed: 0,
            },
          )

        const hasAlert =
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
          )

        return {
          group,
          ...totals,
          hasAlert,
        }
      })
      .sort((a, b) => {
        if (a.hasAlert !== b.hasAlert) {
          return a.hasAlert ? -1 : 1
        }

        return b.total - a.total
      })
      .slice(0, 4)

  return (
    <article className="capture-monitor-card pasarelas">
      <header>
        <div className="capture-monitor-title">
          <span className="capture-monitor-icon">
            P
          </span>

          <div>
            <span>Monitor</span>
            <h3>PASARELAS</h3>
          </div>
        </div>

        <span
          className={statusClass(
            monitor.status,
          )}
        >
          {monitor.status}
        </span>
      </header>

      <div className="capture-main-value">
        <span>Aprobadas</span>

        <strong>
          {numberValue(
            summary.cantidad_ok,
          )}
        </strong>

        <small>
          de{' '}
          {numberValue(
            summary.cantidad_total,
          )}{' '}
          transacciones observadas
        </small>
      </div>

      <div className="capture-metrics-row">
        <div>
          <span>Verticales</span>
          <strong>
            {numberValue(
              summary.verticals,
            )}
          </strong>
        </div>

        <div>
          <span>Fallidas</span>
          <strong>
            {numberValue(
              summary.cantidad_fallida,
            )}
          </strong>
        </div>

        <div>
          <span>Con alerta</span>
          <strong>
            {alertGroups.length}
          </strong>
        </div>
      </div>

      {details ? (
        <div className="capture-mini-list">
          {topGroups.map(
            ({
              group,
              ok,
              total,
              failed,
              hasAlert,
            }) => (
              <div
                key={group.id}
                className={
                  hasAlert
                    ? 'capture-mini-row alert'
                    : 'capture-mini-row'
                }
              >
                <div>
                  <strong>
                    {group.code ??
                      group.id}
                  </strong>

                  <span>
                    {group.name.replace(
                      `${group.code} `,
                      '',
                    )}
                  </span>
                </div>

                <div className="capture-mini-values">
                  <span>
                    OK {numberValue(ok)}
                  </span>

                  <span>
                    Total{' '}
                    {numberValue(total)}
                  </span>

                  {failed > 0 && (
                    <strong>
                      {numberValue(failed)}{' '}
                      fallidas
                    </strong>
                  )}
                </div>
              </div>
            ),
          )}
        </div>
      ) : (
        <div className="capture-awaiting">
          Detalle estructurado no disponible.
        </div>
      )}
    </article>
  )
}

function GenericCapture({
  monitor,
  run,
  icon,
  accent,
}: {
  monitor: DashboardMonitor
  run?: RunDetail
  icon: string
  accent: string
}) {
  const details:
    | StructuredMonitorDetails
    | null =
    isStructuredMonitorDetails(
      run?.details,
    )
      ? run.details
      : null

  const summaryEntries =
    details?.summary
      ? Object.entries(
          details.summary,
        )
          .filter(
            (
              entry,
            ): entry is [
              string,
              string | number,
            ] =>
              typeof entry[1] ===
                'string' ||
              typeof entry[1] ===
                'number',
          )
          .slice(0, 5)
      : []

  return (
    <article
      className={`capture-monitor-card ${accent}`}
    >
      <header>
        <div className="capture-monitor-title">
          <span className="capture-monitor-icon">
            {icon}
          </span>

          <div>
            <span>Monitor</span>
            <h3>{monitor.name}</h3>
          </div>
        </div>

        <span
          className={statusClass(
            monitor.status,
          )}
        >
          {monitor.status}
        </span>
      </header>

      <div className="capture-main-value">
        <span>Registros</span>

        <strong>
          {numberValue(
            run?.records ??
              monitor.records,
          )}
        </strong>

        <small>
          Última ejecución:{' '}
          {monitor.last_run_type ??
            '—'}
        </small>
      </div>

      <div className="capture-metrics-row">
        <div>
          <span>Alertas</span>
          <strong>
            {run?.alerts.length ??
              monitor.alerts}
          </strong>
        </div>

        <div>
          <span>Errores</span>
          <strong>
            {run?.errors.length ?? 0}
          </strong>
        </div>

        <div>
          <span>Duración</span>
          <strong>
            {run?.duration_seconds ??
            monitor.duration_seconds
              ? `${Math.round(
                  run?.duration_seconds ??
                    monitor.duration_seconds ??
                    0,
                )}s`
              : '—'}
          </strong>
        </div>
      </div>

      {summaryEntries.length > 0 ? (
        <div className="capture-mini-list">
          {summaryEntries.map(
            ([key, value]) => (
              <div
                className="capture-mini-row"
                key={key}
              >
                <span>
                  {key
                    .replaceAll('_', ' ')
                    .toUpperCase()}
                </span>

                <strong>
                  {typeof value ===
                  'number'
                    ? numberValue(value)
                    : value}
                </strong>
              </div>
            ),
          )}
        </div>
      ) : (
        <div className="capture-awaiting">
          {monitor.last_run_id
            ? 'El run existe. Esperando details estructurado del backend.'
            : 'Sin ejecución disponible para resumir.'}
        </div>
      )}
    </article>
  )
}

export function CaptureOverview({
  monitors,
}: CaptureOverviewProps) {
  const [runs, setRuns] =
    useState<RunMap>({})

  useEffect(() => {
    const ids =
      monitors
        .filter(
          (monitor) =>
            Boolean(
              monitor.last_run_id,
            ),
        )
        .map((monitor) => ({
          id: monitor.id,
          runId:
            monitor.last_run_id as string,
        }))

    if (ids.length === 0) {
      return
    }

    const timer =
      window.setTimeout(() => {
        void Promise.allSettled(
          ids.map(async (item) => {
            const run =
              await api.runDetail(
                item.runId,
              )

            return {
              monitorId: item.id,
              run,
            }
          }),
        ).then((results) => {
          const next: RunMap = {}

          results.forEach((result) => {
            if (
              result.status ===
              'fulfilled'
            ) {
              next[
                result.value.monitorId
              ] = result.value.run
            }
          })

          setRuns(next)
        })
      }, 0)

    return () => {
      window.clearTimeout(timer)
    }
  }, [monitors])

  const aws =
    findMonitor(monitors, 'aws')

  const pasarelas =
    findMonitor(
      monitors,
      'pasarelas',
    )

  const hercules =
    findMonitor(
      monitors,
      'hercules',
    )

  if (
    !aws &&
    !pasarelas &&
    !hercules
  ) {
    return null
  }

  return (
    <section className="capture-overview">
      <header className="capture-overview-heading">
        <div>
          <span className="section-eyebrow">
            Resumen operativo
          </span>

          <h2>
            Vista general capturable
          </h2>

          <p>
            Información esencial para
            lectura rápida y reporte
            operativo.
          </p>
        </div>

        <div className="capture-hint">
          Una sola vista · 3 monitores
        </div>
      </header>

      <div className="capture-monitor-grid">
        {pasarelas && (
          <PasarelasCapture
            monitor={pasarelas}
            run={runs[pasarelas.id]}
          />
        )}

        {aws && (
          <GenericCapture
            monitor={aws}
            run={runs[aws.id]}
            icon="A"
            accent="aws"
          />
        )}

        {hercules && (
          <GenericCapture
            monitor={hercules}
            run={runs[hercules.id]}
            icon="H"
            accent="hercules"
          />
        )}
      </div>
    </section>
  )
}
