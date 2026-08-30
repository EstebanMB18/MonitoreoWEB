import {
  type FormEvent,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from 'react'

import { api } from '../services/api'

import type {
  DailyHistoryItem,
  HistoryFilters,
} from '../types/history'

interface MonitorOption {
  id: string
  name: string
}

function formatDate(value: string) {
  const [year, month, day] =
    value.split('-').map(Number)

  if (!year || !month || !day) {
    return value
  }

  return new Intl.DateTimeFormat(
    'es-CO',
    {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
    },
  ).format(
    new Date(year, month - 1, day),
  )
}

function formatDateTime(
  value: string | null,
) {
  if (!value) {
    return '—'
  }

  const date = new Date(value)

  if (Number.isNaN(date.getTime())) {
    return value
  }

  return new Intl.DateTimeFormat(
    'es-CO',
    {
      day: '2-digit',
      month: 'short',
      hour: '2-digit',
      minute: '2-digit',
    },
  ).format(date)
}

function coverageLabel(
  item: DailyHistoryItem,
) {
  if (
    item.coverage_status ===
    'SIN_EJECUCION'
  ) {
    return 'SIN EJECUCIÓN'
  }

  return 'EJECUTADO'
}

function statusLabel(
  item: DailyHistoryItem,
) {
  if (
    item.coverage_status ===
    'SIN_EJECUCION'
  ) {
    return 'SIN EJECUCIÓN'
  }

  switch (item.overall_status) {
    case 'OK':
      return 'OK'
    case 'WARNING':
      return 'WARNING'
    case 'ERROR':
      return 'ERROR'
    case 'NO_DATA':
      return 'NO DATA'
    default:
      return item.overall_status
  }
}

function statusClass(
  item: DailyHistoryItem,
) {
  if (
    item.coverage_status ===
    'SIN_EJECUCION'
  ) {
    return 'history-status no-run'
  }

  switch (item.overall_status) {
    case 'OK':
      return 'history-status ok'
    case 'WARNING':
      return 'history-status warning'
    case 'ERROR':
      return 'history-status error'
    case 'NO_DATA':
      return 'history-status no-data'
    default:
      return 'history-status neutral'
  }
}

export function HistoryPage() {
  const [items, setItems] =
    useState<DailyHistoryItem[]>([])

  const [monitors, setMonitors] =
    useState<MonitorOption[]>([])

  const [monitor, setMonitor] =
    useState('ALL')

  const [startDate, setStartDate] =
    useState('')

  const [endDate, setEndDate] =
    useState('')

  const [closureDate, setClosureDate] =
    useState('')

  const [loading, setLoading] =
    useState(true)

  const [error, setError] =
    useState<string | null>(null)

  const loadHistory =
    useCallback(
      async (
        filters: HistoryFilters = {},
        monitorOptions?: MonitorOption[],
      ) => {
        setLoading(true)
        setError(null)

        try {
          const selectedMonitor =
            filters.monitor ??
            (monitor !== 'ALL'
              ? monitor
              : null)

          const exactDate =
            filters.closure_date ??
            (closureDate || null)

          const from =
            filters.start_date ??
            (startDate || null)

          const to =
            filters.end_date ??
            (endDate || null)

          if (exactDate) {
            if (selectedMonitor) {
              const response =
                await api.historyMonitor(
                  selectedMonitor,
                  {
                    closure_date:
                      exactDate,
                  },
                )

              setItems(response.items)
              return
            }

            const sourceMonitors =
              monitorOptions?.length
                ? monitorOptions
                : [
                    {
                      id: 'aws',
                      name: 'AWS',
                    },
                    {
                      id: 'pasarelas',
                      name: 'PASARELAS',
                    },
                    {
                      id: 'hercules',
                      name: 'HERCULES',
                    },
                  ]

            const responses =
              await Promise.all(
                sourceMonitors.map(
                  (item) =>
                    api.historyMonitor(
                      item.id,
                      {
                        closure_date:
                          exactDate,
                      },
                    ),
                ),
              )

            setItems(
              responses.flatMap(
                (response) =>
                  response.items,
              ),
            )

            return
          }

          const response =
            await api.historyDaily({
              monitor:
                selectedMonitor,
              start_date: from,
              end_date: to,
            })

          setItems(response.items)
        } catch (err) {
          setItems([])

          setError(
            err instanceof Error
              ? err.message
              : 'No fue posible consultar el histórico.',
          )
        } finally {
          setLoading(false)
        }
      },
      [
        closureDate,
        endDate,
        monitor,
        startDate,
      ],
    )

  useEffect(() => {
    const timer =
      window.setTimeout(() => {
        void (async () => {
          let options: MonitorOption[] = []

          try {
            const response =
              await api.monitors()

            options =
              response.items.map((item) => ({
                id: item.id,
                name: item.name,
              }))

            setMonitors(options)
          } catch {
            // Histórico sigue disponible
            // aunque falle el catálogo auxiliar.
          }

          await loadHistory({}, options)
        })()
      }, 0)

    return () => {
      window.clearTimeout(timer)
    }
  }, [loadHistory])

  const summary = useMemo(() => {
    return items.reduce(
      (acc, item) => {
        if (
          item.coverage_status ===
          'SIN_EJECUCION'
        ) {
          acc.noRun += 1
        } else {
          acc.executed += 1
        }

        acc.officialRuns +=
          item.official_runs

        acc.records +=
          item.total_records

        acc.alerts +=
          item.alerts_count

        acc.errors +=
          item.errors_count

        return acc
      },
      {
        executed: 0,
        noRun: 0,
        officialRuns: 0,
        records: 0,
        alerts: 0,
        errors: 0,
      },
    )
  }, [items])

  const grouped = useMemo(() => {
    const result =
      new Map<
        string,
        DailyHistoryItem[]
      >()

    for (const item of items) {
      const current =
        result.get(
          item.closure_date,
        ) ?? []

      current.push(item)

      result.set(
        item.closure_date,
        current,
      )
    }

    return Array.from(
      result.entries(),
    ).sort(([a], [b]) =>
      b.localeCompare(a),
    )
  }, [items])

  function handleSubmit(
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault()

    void loadHistory()
  }

  function handleClear() {
    setMonitor('ALL')
    setStartDate('')
    setEndDate('')
    setClosureDate('')

    void loadHistory({
      monitor: null,
      start_date: null,
      end_date: null,
      closure_date: null,
    })
  }

  return (
    <div className="history-page">
      <section className="history-heading">
        <div>
          <span className="section-eyebrow">
            Operación
          </span>

          <h1>Histórico diario</h1>

          <p>
            Consulta la cobertura y el
            resultado consolidado de los
            monitores por día.
          </p>
        </div>

        <div className="history-total">
          <span>Registros visibles</span>
          <strong>{items.length}</strong>
        </div>
      </section>

      <form
        className="history-filters"
        onSubmit={handleSubmit}
      >
        <label>
          Monitor
          <select
            value={monitor}
            onChange={(event) =>
              setMonitor(
                event.target.value,
              )
            }
          >
            <option value="ALL">
              Todos
            </option>

            {monitors.map((item) => (
              <option
                key={item.id}
                value={item.id}
              >
                {item.name}
              </option>
            ))}
          </select>
        </label>

        <label>
          Desde
          <input
            type="date"
            value={startDate}
            disabled={
              Boolean(closureDate)
            }
            onChange={(event) =>
              setStartDate(
                event.target.value,
              )
            }
          />
        </label>

        <label>
          Hasta
          <input
            type="date"
            value={endDate}
            disabled={
              Boolean(closureDate)
            }
            onChange={(event) =>
              setEndDate(
                event.target.value,
              )
            }
          />
        </label>

        <label>
          Día exacto
          <input
            type="date"
            value={closureDate}
            onChange={(event) => {
              const value =
                event.target.value

              setClosureDate(value)

              if (value) {
                setStartDate('')
                setEndDate('')
              }
            }}
          />
        </label>

        <div className="history-filter-actions">
          <button
            type="submit"
            className="history-primary"
            disabled={loading}
          >
            {loading
              ? 'Consultando...'
              : 'Consultar'}
          </button>

          <button
            type="button"
            className="history-secondary"
            onClick={handleClear}
            disabled={loading}
          >
            Limpiar
          </button>
        </div>
      </form>

      <section className="history-summary-grid">
        <article>
          <span>Ejecutados</span>
          <strong>
            {summary.executed}
          </strong>
        </article>

        <article>
          <span>Sin ejecución</span>
          <strong>
            {summary.noRun}
          </strong>
        </article>

        <article>
          <span>Ejecuciones oficiales</span>
          <strong>
            {summary.officialRuns}
          </strong>
        </article>

        <article>
          <span>Registros</span>
          <strong>
            {summary.records}
          </strong>
        </article>

        <article>
          <span>Alertas</span>
          <strong>
            {summary.alerts}
          </strong>
        </article>

        <article>
          <span>Errores</span>
          <strong>
            {summary.errors}
          </strong>
        </article>
      </section>

      {error && (
        <div
          className="history-error"
          role="alert"
        >
          {error}
        </div>
      )}

      {!loading &&
        !error &&
        grouped.length === 0 && (
          <section className="history-empty">
            <strong>
              Sin información histórica
            </strong>

            <span>
              No existen cierres que
              coincidan con los filtros
              seleccionados.
            </span>
          </section>
        )}

      <div className="history-days">
        {grouped.map(
          ([date, dayItems]) => (
            <section
              className="history-day"
              key={date}
            >
              <header>
                <div>
                  <span>
                    Cierre diario
                  </span>

                  <h2>
                    {formatDate(date)}
                  </h2>
                </div>

                <span>
                  {dayItems.length}{' '}
                  monitor
                  {dayItems.length === 1
                    ? ''
                    : 'es'}
                </span>
              </header>

              <div className="history-table-wrap">
                <table className="history-table">
                  <thead>
                    <tr>
                      <th>Monitor</th>
                      <th>Cobertura</th>
                      <th>Estado</th>
                      <th>Oficiales</th>
                      <th>Registros</th>
                      <th>Alertas</th>
                      <th>Errores</th>
                      <th>Última ejecución</th>
                    </tr>
                  </thead>

                  <tbody>
                    {dayItems
                      .sort((a, b) =>
                        a.monitor.localeCompare(
                          b.monitor,
                        ),
                      )
                      .map((item) => (
                        <tr
                          key={`${item.monitor}-${item.closure_date}`}
                          className={
                            item.coverage_status ===
                            'SIN_EJECUCION'
                              ? 'history-row no-run'
                              : undefined
                          }
                        >
                          <td>
                            <strong>
                              {item.monitor}
                            </strong>
                          </td>

                          <td>
                            <span
                              className={
                                item.coverage_status ===
                                'SIN_EJECUCION'
                                  ? 'coverage-badge no-run'
                                  : 'coverage-badge executed'
                              }
                            >
                              {coverageLabel(
                                item,
                              )}
                            </span>
                          </td>

                          <td>
                            <span
                              className={statusClass(
                                item,
                              )}
                            >
                              {statusLabel(
                                item,
                              )}
                            </span>
                          </td>

                          <td>
                            {item.official_runs}
                          </td>

                          <td>
                            {item.total_records}
                          </td>

                          <td>
                            {item.alerts_count}
                          </td>

                          <td>
                            {item.errors_count}
                          </td>

                          <td>
                            {formatDateTime(
                              item.last_run_at,
                            )}
                          </td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
            </section>
          ),
        )}
      </div>
    </div>
  )
}
