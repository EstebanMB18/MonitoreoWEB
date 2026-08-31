import type { StructuredMonitorDetails } from '../types/monitorDetails'

interface AwsDetailV2Props {
  details: StructuredMonitorDetails
}

type UnknownRecord = Record<string, unknown>

interface ChartPoint {
  label: string
  primary: number
  secondary?: number
}

function isRecord(value: unknown): value is UnknownRecord {
  return (
    typeof value === 'object' &&
    value !== null &&
    !Array.isArray(value)
  )
}

function asNumber(value: unknown) {
  return typeof value === 'number' &&
    Number.isFinite(value)
    ? value
    : 0
}

function asText(value: unknown) {
  if (
    typeof value === 'string' &&
    value.trim()
  ) {
    return value.trim()
  }

  if (
    typeof value === 'number' &&
    Number.isFinite(value)
  ) {
    return String(value)
  }

  return '-'
}

function formatNumber(value: unknown) {
  if (
    typeof value === 'number' &&
    Number.isFinite(value)
  ) {
    return new Intl.NumberFormat(
      'es-CO',
    ).format(value)
  }

  return asText(value)
}

function formatBucket(value: unknown) {
  const text = asText(value)

  if (text === '-') {
    return text
  }

  if (text.length >= 16) {
    return text.slice(11, 16)
  }

  return text
}

function formatDateTime(value: unknown) {
  const text = asText(value)

  if (text === '-') {
    return text
  }

  return text
    .replace('T', ' ')
    .slice(0, 19)
}

function getSeries(
  details: StructuredMonitorDetails,
  key: string,
): UnknownRecord[] {
  if (!isRecord(details.series)) {
    return []
  }

  const value = details.series[key]

  if (!Array.isArray(value)) {
    return []
  }

  return value.filter(isRecord)
}

function getGroup(
  details: StructuredMonitorDetails,
  id: string,
) {
  return (details.groups ?? []).find(
    (group) =>
      group.id.toUpperCase() ===
      id.toUpperCase(),
  )
}

function getService(
  details: StructuredMonitorDetails,
  groupId: string,
  serviceId: string,
) {
  return getGroup(
    details,
    groupId,
  )?.services.find(
    (service) =>
      service.id.toUpperCase() ===
      serviceId.toUpperCase(),
  )
}

function statusClass(status: string) {
  const normalized =
    status.toUpperCase()

  if (
    normalized.includes('ERROR') ||
    normalized.includes('CRITICAL')
  ) {
    return 'error'
  }

  if (
    normalized.includes('WARNING') ||
    normalized.includes('ALERT')
  ) {
    return 'warning'
  }

  return 'ok'
}

function MetricRows({
  metrics,
}: {
  metrics: NonNullable<
    ReturnType<typeof getService>
  >['metrics']
}) {
  if (metrics.length === 0) {
    return (
      <div className="aws-v2-empty">
        Sin métricas disponibles
      </div>
    )
  }

  return (
    <div className="aws-v2-metric-list">
      {metrics.map((metric) => (
        <div
          key={metric.id}
          className="aws-v2-metric-row"
        >
          <span>{metric.metric}</span>

          <strong>
            {formatNumber(metric.value)}
          </strong>

          <span
            className={`aws-v2-status ${statusClass(
              metric.status,
            )}`}
          >
            {metric.status}
          </span>
        </div>
      ))}
    </div>
  )
}

function SeriesChart({
  title,
  subtitle,
  points,
  secondaryLabel,
  tone = 'blue',
}: {
  title: string
  subtitle?: string
  points: ChartPoint[]
  secondaryLabel?: string
  tone?: 'blue' | 'red'
}) {
  const max = Math.max(
    1,
    ...points.flatMap((point) => [
      point.primary,
      point.secondary ?? 0,
    ]),
  )

  return (
    <section
      className={`aws-v2-chart ${
        tone === 'red'
          ? 'aws-v2-chart-error'
          : ''
      }`}
    >
      <header>
        <div>
          <h4>{title}</h4>

          {subtitle && (
            <p>{subtitle}</p>
          )}
        </div>

        {secondaryLabel && (
          <div className="aws-v2-chart-legend">
            <span>
              <i className="primary" />
              Principal
            </span>

            <span>
              <i className="secondary" />
              {secondaryLabel}
            </span>
          </div>
        )}
      </header>

      {points.length === 0 ? (
        <div className="aws-v2-chart-empty">
          Sin datos para el periodo
        </div>
      ) : (
        <div className="aws-v2-bars">
          {points.map(
            (point, index) => {
              const primaryHeight =
                Math.max(
                  point.primary > 0
                    ? 5
                    : 0,
                  (point.primary / max) *
                    100,
                )

              const secondaryHeight =
                Math.max(
                  (point.secondary ?? 0) >
                    0
                    ? 5
                    : 0,
                  ((point.secondary ?? 0) /
                    max) *
                    100,
                )

              return (
                <div
                  className="aws-v2-bar-column"
                  key={`${point.label}-${index}`}
                >
                  <div className="aws-v2-bar-value">
                    {formatNumber(
                      point.primary,
                    )}
                  </div>

                  <div className="aws-v2-bar-track">
                    <div
                      className="aws-v2-bar primary"
                      style={{
                        height:
                          `${primaryHeight}%`,
                      }}
                    />

                    {point.secondary !==
                      undefined && (
                      <div
                        className="aws-v2-bar secondary"
                        style={{
                          height:
                            `${secondaryHeight}%`,
                        }}
                      />
                    )}
                  </div>

                  <span>
                    {point.label}
                  </span>
                </div>
              )
            },
          )}
        </div>
      )}
    </section>
  )
}

function AwsMessaging({
  details,
}: AwsDetailV2Props) {
  const successRows =
    getSeries(
      details,
      'mensajeria_exitos',
    )

  const errorRows =
    getSeries(
      details,
      'mensajeria_errores',
    )

  const successHourly =
    getSeries(
      details,
      'mensajeria_200_por_hora',
    )

  const errorHourly =
    getSeries(
      details,
      'mensajeria_errores_por_hora',
    )

  return (
    <section className="aws-v2-messaging">
      <div className="aws-v2-section-title">
        <div>
          <span className="section-eyebrow">
            AWS · MENSAJERÍA
          </span>

          <h2>
            Mensajería
          </h2>

          <p>
            Volumen exitoso y detalle
            agregado de errores.
          </p>
        </div>

        <div className="aws-v2-messaging-counts">
          <span>
            Exitosos
            <strong>
              {formatNumber(
                successRows.reduce(
                  (total, row) =>
                    total +
                    asNumber(row.count),
                  0,
                ),
              )}
            </strong>
          </span>

          <span>
            Errores
            <strong>
              {formatNumber(
                errorRows.reduce(
                  (total, row) =>
                    total +
                    asNumber(row.count),
                  0,
                ),
              )}
            </strong>
          </span>
        </div>
      </div>

      <div className="aws-v2-chart-grid">
        <SeriesChart
          title="Exitosos HTTP 200 por hora"
          subtitle="Mensajes procesados correctamente"
          points={successHourly.map(
            (row) => ({
              label: formatBucket(
                row.hora,
              ),
              primary: asNumber(
                row.count,
              ),
            }),
          )}
        />

        <SeriesChart
          title="Errores de mensajería por hora"
          subtitle="Todos los errores agregados"
          points={errorHourly.map(
            (row) => ({
              label: formatBucket(
                row.hora,
              ),
              primary: asNumber(
                row.count,
              ),
            }),
          )}
          tone="red"
        />
      </div>

      <div className="aws-v2-message-tables">
        <section className="aws-v2-table-card">
          <header>
            <div>
              <h3>Exitosos 200</h3>

              <p>
                Distribución por consumer,
                broker y operación.
              </p>
            </div>

            <strong>
              {successRows.length}
            </strong>
          </header>

          {successRows.length === 0 ? (
            <div className="aws-v2-table-empty">
              Sin datos para el periodo
            </div>
          ) : (
            <div className="aws-v2-table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Consumer</th>
                    <th>Broker</th>
                    <th>HTTP</th>
                    <th>Operación</th>
                    <th>Cantidad</th>
                  </tr>
                </thead>

                <tbody>
                  {successRows.map(
                    (row, index) => (
                      <tr key={index}>
                        <td>
                          {asText(
                            row.id_consumer,
                          )}
                        </td>

                        <td>
                          {asText(
                            row.broker,
                          )}
                        </td>

                        <td>
                          {asText(
                            row.httpcode,
                          )}
                        </td>

                        <td>
                          {asText(
                            row.operacion,
                          )}
                        </td>

                        <td>
                          <strong>
                            {formatNumber(
                              row.count,
                            )}
                          </strong>
                        </td>
                      </tr>
                    ),
                  )}
                </tbody>
              </table>
            </div>
          )}
        </section>

        <section className="aws-v2-table-card aws-v2-error-table">
          <header>
            <div>
              <h3>
                Detalle de errores
              </h3>

              <p>
                Información sanitizada
                entregada por Backend.
              </p>
            </div>

            <strong>
              {errorRows.length}
            </strong>
          </header>

          {errorRows.length === 0 ? (
            <div className="aws-v2-table-empty success">
              Sin errores para el periodo
            </div>
          ) : (
            <div className="aws-v2-table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Consumer</th>
                    <th>Broker</th>
                    <th>HTTP</th>
                    <th>Operación</th>
                    <th>Cantidad</th>
                    <th>Desde</th>
                    <th>Hasta</th>
                  </tr>
                </thead>

                <tbody>
                  {errorRows.map(
                    (row, index) => (
                      <tr key={index}>
                        <td>
                          {asText(
                            row.id_consumer,
                          )}
                        </td>

                        <td>
                          {asText(
                            row.broker,
                          )}
                        </td>

                        <td>
                          {asText(
                            row.httpcode,
                          )}
                        </td>

                        <td>
                          {asText(
                            row.operacion,
                          )}
                        </td>

                        <td>
                          <strong>
                            {formatNumber(
                              row.count,
                            )}
                          </strong>
                        </td>

                        <td>
                          {formatDateTime(
                            row.desde,
                          )}
                        </td>

                        <td>
                          {formatDateTime(
                            row.hasta,
                          )}
                        </td>
                      </tr>
                    ),
                  )}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>
    </section>
  )
}


export function AwsDetailV2({
  details,
}: AwsDetailV2Props) {
  const interop =
    getGroup(
      details,
      'INTEROPPROD',
    )

  const paymentService =
    interop?.services.find(
      (service) =>
        service.id ===
        'api_orquestador_pagos',
    ) ??
    interop?.services.find(
      (service) =>
        service.name
          .toUpperCase()
          .includes('PAGOS'),
    )

  const mongo =
    interop?.services.find(
      (service) =>
        service.name
          .toUpperCase()
          .includes('MONGO'),
    )

  const paymentNormal =
    paymentService?.metrics.filter(
      (metric) =>
        metric.id.startsWith(
          'aprob_',
        ),
    ) ?? []

  const paymentErrors =
    paymentService?.metrics.filter(
      (metric) =>
        !metric.id.startsWith(
          'aprob_',
        ),
    ) ?? []

  const csc =
    getGroup(details, 'CSC')

  const subsidy =
    getGroup(
      details,
      'API SUBSIDIOS',
    )

  const tupTen =
    getSeries(
      details,
      'tup_10m_ultima_hora',
    )

  const tupSummary =
    getSeries(
      details,
      'tup_resumen',
    )[0]

  const tupErrorPoints =
    tupTen.map((row) => ({
      label: formatBucket(
        row.hora,
      ),
      primary: asNumber(
        row.errores,
      ),
    }))

  const hasTupErrors =
    tupErrorPoints.some(
      (point) =>
        point.primary > 0,
    )

  const redSummary =
    getSeries(
      details,
      'serviciosred_resumen',
    )[0]

  const redLastHour =
    getSeries(
      details,
      'serviciosred_ultima_hora',
    )[0]

  const redTen =
    getSeries(
      details,
      'serviciosred_10m_ultima_hora',
    )

  const businessAlerts =
    Array.isArray(
      details.business_alerts,
    )
      ? details.business_alerts.length
      : 0

  const technicalErrors =
    Array.isArray(
      details.technical_errors,
    )
      ? details.technical_errors.length
      : 0

  return (
    <div className="aws-v2">
      <div className="aws-v2-columns">
        <main className="aws-v2-column">
          <section className="aws-v2-panel">
            <div className="aws-v2-section-title">
              <div>
                <span className="section-eyebrow">
                  Operación
                </span>

                <h2>
                  APIs y transaccionalidad
                </h2>

                <p>
                  Consultas exitosas y volumen
                  operativo.
                </p>
              </div>
            </div>

            <MetricRows
              metrics={paymentNormal}
            />
          </section>

          <section className="aws-v2-panel">
            <div className="aws-v2-section-title">
              <div>
                <span className="section-eyebrow">
                  Tarjeta TUP
                </span>

                <h2>
                  Comportamiento transaccional
                </h2>
              </div>
            </div>

            <div className="aws-v2-kpis">
              <article>
                <span>Aprobadas</span>
                <strong>
                  {formatNumber(
                    tupSummary?.aprobadas,
                  )}
                </strong>
              </article>

              <article>
                <span>Errores</span>
                <strong>
                  {formatNumber(
                    tupSummary?.errores,
                  )}
                </strong>
              </article>

              <article>
                <span>Pico</span>
                <strong>
                  {formatNumber(
                    tupSummary?.pico,
                  )}
                </strong>
              </article>

              <article>
                <span>Hora pico</span>
                <strong className="small">
                  {formatDateTime(
                    tupSummary?.hora_pico,
                  )}
                </strong>
              </article>

              <article>
                <span>
                  Última transacción
                </span>
                <strong className="small">
                  {formatDateTime(
                    tupSummary?.ultima_transaccion,
                  )}
                </strong>
              </article>
            </div>

            {hasTupErrors ? (
              <SeriesChart
                title="Errores TUP · últimos 60 minutos"
                subtitle="Bloques de 10 minutos"
                points={tupErrorPoints}
                tone="red"
              />
            ) : (
              <div className="aws-v2-no-errors">
                <span>✓</span>

                <div>
                  <strong>
                    Sin errores TUP
                  </strong>

                  <p>
                    No se registraron errores
                    durante los Últimos 60 minutos.
                  </p>
                </div>
              </div>
            )}
          </section>

          
        </main>

        <aside className="aws-v2-column">
          <section className="aws-v2-panel aws-v2-problem-panel">
            <div className="aws-v2-section-title">
              <div>
                <span className="section-eyebrow">
                  Atención
                </span>

                <h2>
                  Errores y controles técnicos
                </h2>
              </div>

              <div className="aws-v2-alert-counter">
                {businessAlerts +
                  technicalErrors}
              </div>
            </div>

            <div className="aws-v2-control-block">
              <h3>
                API Orquestador Pagos
              </h3>

              <MetricRows
                metrics={paymentErrors}
              />
            </div>

            {mongo && (
              <div className="aws-v2-control-block">
                <h3>MongoDB</h3>

                <MetricRows
                  metrics={mongo.metrics}
                />
              </div>
            )}

            {csc?.services.map(
              (service) => (
                <div
                  className="aws-v2-control-block"
                  key={service.id}
                >
                  <h3>CSC</h3>

                  <MetricRows
                    metrics={
                      service.metrics
                    }
                  />
                </div>
              ),
            )}

            {subsidy?.services.map(
              (service) => (
                <div
                  className="aws-v2-control-block"
                  key={service.id}
                >
                  <h3>
                    API Subsidios
                  </h3>

                  <MetricRows
                    metrics={
                      service.metrics
                    }
                  />
                </div>
              ),
            )}
          </section>

          
        </aside>
      </div>

<section className="aws-v2-panel aws-v2-services-red">
            <div className="aws-v2-section-title">
              <div>
                <span className="section-eyebrow">
                  Servicios Red
                </span>

                <h2>
                  Actividad de notificaciones
                </h2>

                <p>
                  Lectura temporal para identificar
                  huecos de notificación.
                </p>
              </div>
            </div>

            <div className="aws-v2-kpis">
              <article>
                <span>
                  Notificaciones corte
                </span>

                <strong>
                  {formatNumber(
                    redSummary?.count,
                  )}
                </strong>
              </article>

              <article>
                <span>
                  Última hora
                </span>

                <strong>
                  {formatNumber(
                    redLastHour?.count,
                  )}
                </strong>
              </article>

              <article>
                <span>
                  Última notificación
                </span>

                <strong className="small">
                  {formatDateTime(
                    redSummary
                      ?.ultima_notificacion,
                  )}
                </strong>
              </article>
            </div>

            <SeriesChart
              title="Notificaciones cada 10 minutos"
              subtitle="Últimos 60 minutos"
              points={redTen.map(
                (row) => ({
                  label:
                    formatBucket(
                      row.hora,
                    ),
                  primary:
                    asNumber(
                      row.count,
                    ),
                }),
              )}
            />
          </section>


      <AwsMessaging
        details={details}
      />
    </div>
  )
}
