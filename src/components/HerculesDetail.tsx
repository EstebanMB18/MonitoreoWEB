type HerculesDetailProps = {
  details: any
}

const numberFormatter =
  new Intl.NumberFormat('es-CO')

function formatNumber(
  value: unknown,
): string {
  const numberValue = Number(value)

  if (!Number.isFinite(numberValue)) {
    return '-'
  }

  return numberFormatter.format(numberValue)
}

function getSeries(
  details: any,
  name: string,
): any[] {
  const value = details?.series?.[name]

  return Array.isArray(value)
    ? value
    : []
}

function BarList({
  items,
  labelKey,
}: {
  items: any[]
  labelKey: string
}) {
  const max = Math.max(
    1,
    ...items.map(
      (item) =>
        Number(item.count) || 0,
    ),
  )

  return (
    <div className="hercules-bars">
      {items.map((item, index) => {
        const value =
          Number(item.count) || 0

        const width =
          Math.max(
            2,
            (value / max) * 100,
          )

        const rawLabel =
          item[labelKey]

        const label =
          rawLabel === null ||
          rawLabel === undefined ||
          String(rawLabel).trim() === ''
            ? '(en blanco)'
            : String(rawLabel)

        return (
          <div
            className="hercules-bar-row"
            key={`${label}-${index}`}
          >
            <span>
              {label}
            </span>

            <div className="hercules-bar-track">
              <div
                className="hercules-bar-fill"
                style={{
                  width: `${width}%`,
                }}
              />
            </div>

            <strong>
              {formatNumber(value)}
            </strong>
          </div>
        )
      })}
    </div>
  )
}


function ChannelGroups({
  items,
}: {
  items: any[]
}) {
  const groups =
    new Map<string, any[]>()

  for (const item of items) {
    const rawCanal =
      item?.canal

    const canal =
      rawCanal === null ||
      rawCanal === undefined ||
      String(rawCanal).trim() === ''
        ? 'Otros'
        : String(rawCanal)

    const current =
      groups.get(canal) ?? []

    current.push(item)

    groups.set(
      canal,
      current,
    )
  }

  return (
    <div className="hercules-channel-groups">
      {Array.from(
        groups.entries(),
      ).map(
        ([canal, rows]) => {
          const total =
            rows.reduce(
              (
                sum,
                row,
              ) =>
                sum +
                (Number(
                  row.count,
                ) || 0),
              0,
            )

          return (
            <section
              className="hercules-channel-group"
              key={canal}
            >
              <header>
                <div>
                  <span>
                    Canal
                  </span>

                  <h4>
                    {canal}
                  </h4>
                </div>

                <strong>
                  {formatNumber(
                    total,
                  )}
                </strong>
              </header>

              <div className="hercules-channel-body">
                {rows.map(
                  (
                    row,
                    index,
                  ) => {
                    const rawForma =
                      row?.forma

                    const forma =
                      rawForma === null ||
                      rawForma === undefined ||
                      String(
                        rawForma,
                      ).trim() === ''
                        ? '(en blanco)'
                        : String(
                            rawForma,
                          )

                    return (
                      <div
                        className="hercules-channel-row"
                        key={`${canal}-${forma}-${index}`}
                      >
                        <span>
                          {forma}
                        </span>

                        <strong>
                          {formatNumber(
                            row.count,
                          )}
                        </strong>
                      </div>
                    )
                  },
                )}
              </div>
            </section>
          )
        },
      )}
    </div>
  )
}

export function HerculesDetail({
  details,
}: HerculesDetailProps) {
  const summary =
    details?.summary ?? {}

  const estados =
    getSeries(
      details,
      'estados_por_canal',
    )

  const canales =
    getSeries(
      details,
      'totales_por_canal',
    )

  const pagosForma =
    getSeries(
      details,
      'pago_realizado_por_forma_pago',
    )

  const checkoutForma =
    getSeries(
      details,
      'checkout_por_forma_pago',
    )

  const pagosCanalForma =
    getSeries(
      details,
      'pago_realizado_canal_forma_pago',
    )

  const checkoutCanalForma =
    getSeries(
      details,
      'checkout_canal_forma_pago',
    )

  const recaudoCanalForma =
    getSeries(
      details,
      'pendiente_recaudo_canal_forma_pago',
    )

  const alertasWeb =
    getSeries(
      details,
      'alertas_web',
    )

  const checkoutHasAlert =
    alertasWeb.some(
      (item: any) =>
        String(
          item.status ?? '',
        ).toUpperCase() !== 'OK',
    )

  const pendingRecaudoCount =
    Number(
      summary.pendiente_recaudo,
    ) || 0

  const hasPendingRecaudoAlert =
    pendingRecaudoCount > 40

  const estadosAgrupados =
    new Map<
      string,
      any[]
    >()

  for (const item of estados) {
    const estado =
      String(
        item.estado ?? '-',
      )

    const current =
      estadosAgrupados.get(
        estado,
      ) ?? []

    current.push(item)

    estadosAgrupados.set(
      estado,
      current,
    )
  }

  return (
    <div className="hercules-v2">

      <section className="hercules-kpis">

        <article>
          <span>Total</span>
          <strong>
            {formatNumber(
              summary.total_records,
            )}
          </strong>
          <small>
            Registros descargados
          </small>
        </article>

        <article>
          <span>Pago realizado</span>
          <strong>
            {formatNumber(
              summary.pago_realizado,
            )}
          </strong>
          <small>
            Operaciones finalizadas
          </small>
        </article>

        <article>
          <span>Checkout</span>
          <strong>
            {formatNumber(
              summary.checkout,
            )}
          </strong>
          <small>
            Antes de finalizar pago
          </small>
        </article>

        <article>
          <span>Pago pendiente</span>
          <strong>
            {formatNumber(
              summary.pago_pendiente,
            )}
          </strong>
          <small>
            Pendientes de finalizar
          </small>
        </article>

        <article>
          <span>Pendiente recaudo</span>
          <strong>
            {formatNumber(
              summary.pendiente_recaudo,
            )}
          </strong>
          <small>
            Pendientes de recaudo
          </small>
        </article>

        <article>
          <span>Inconsistentes</span>
          <strong>
            {formatNumber(
              summary.inconsistentes,
            )}
          </strong>
          <small>
            Registros inconsistentes
          </small>
        </article>

      </section>

      <section className="hercules-section">

        <div className="hercules-heading">
          <div>
            <span className="section-eyebrow">
              Web
            </span>

            <h2>
              Alertas por forma de pago
            </h2>
          </div>
        </div>

        <div className="hercules-alert-grid">
          {alertasWeb.map(
            (item: any) => (
              <article
                className={`hercules-alert-card ${
                  String(
                    item.status,
                  ).toUpperCase() ===
                  'OK'
                    ? 'is-ok'
                    : 'is-warning'
                }`}
                key={
                  item.forma_pago
                }
              >
                <div className="hercules-alert-top">
                  <div>
                    <span>
                      Web
                    </span>

                    <h3>
                      {item.forma_pago}
                    </h3>
                  </div>

                  <strong>
                    {item.status ?? '-'}
                  </strong>
                </div>

                <div className="hercules-alert-metrics">
                  <div>
                    <span>
                      Pago realizado
                    </span>
                    <strong>
                      {formatNumber(
                        item.pago_realizado,
                      )}
                    </strong>
                  </div>

                  <div>
                    <span>
                      Checkout
                    </span>
                    <strong>
                      {formatNumber(
                        item.checkout,
                      )}
                    </strong>
                  </div>

                  <div>
                    <span>
                      Pendiente recaudo
                    </span>
                    <strong>
                      {formatNumber(
                        item.pendiente_recaudo,
                      )}
                    </strong>
                  </div>

                  <div>
                    <span>
                      Pago pendiente
                    </span>
                    <strong>
                      {formatNumber(
                        item.pago_pendiente,
                      )}
                    </strong>
                  </div>
                </div>
              </article>
            ),
          )}
        </div>

      </section>

      <section className="hercules-section">

        <div className="hercules-heading">
          <div>
            <span className="section-eyebrow">
              Operaci?n
            </span>

            <h2>
              Estados por canal
            </h2>
          </div>
        </div>

        <div className="hercules-state-grid">
          {Array.from(
            estadosAgrupados.entries(),
          ).map(
            ([estado, items]) => {
              const total =
                items.reduce(
                  (
                    acc,
                    item,
                  ) =>
                    acc +
                    (Number(
                      item.count,
                    ) || 0),
                  0,
                )

              return (
                <article
                  key={estado}
                  className="hercules-state-card"
                >
                  <header>
                    <div>
                      <span>
                        Estado
                      </span>

                      <h3>
                        {estado}
                      </h3>
                    </div>

                    <strong>
                      {formatNumber(
                        total,
                      )}
                    </strong>
                  </header>

                  <div className="hercules-state-body">
                    {items.map(
                      (
                        item,
                        index,
                      ) => (
                        <div
                          key={`${item.canal}-${index}`}
                        >
                          <span>
                            {item.canal ??
                              '-'}
                          </span>

                          <strong>
                            {formatNumber(
                              item.count,
                            )}
                          </strong>
                        </div>
                      ),
                    )}
                  </div>
                </article>
              )
            },
          )}
        </div>

      </section>

      <section className="hercules-section">

        <div className="hercules-heading">
          <div>
            <span className="section-eyebrow">
              Distribuci?n
            </span>

            <h2>
              Resumen operativo
            </h2>
          </div>
        </div>

        <div className="hercules-chart-grid">

          <article className="hercules-chart-card">
            <h3>
              {'Canal que cotiz\u00f3'}
            </h3>
            <p>
              Total de registros por canal.
            </p>

            <BarList
              items={canales}
              labelKey="canal"
            />
          </article>

          <article className="hercules-chart-card">
            <h3>
              Pago realizado por forma de pago
            </h3>
            <p>
              Medios de pago finalizados.
            </p>

            <BarList
              items={pagosForma}
              labelKey="forma"
            />
          </article>

          <article className="hercules-chart-card">
            <h3>
              Checkout por forma de pago
            </h3>
            <p>
              Estados previos a finalizar pago.
            </p>

            <BarList
              items={checkoutForma}
              labelKey="forma"
            />
          </article>

        </div>

      </section>

      <section className="hercules-section">

        <div className="hercules-heading">
          <div>
            <span className="section-eyebrow">
              Detalle agregado
            </span>

            <h2>
              Canal y forma de pago
            </h2>
          </div>
        </div>

        <div className="hercules-detail-grid">

          <article className="hercules-detail-card">
            <h3>
              Pago realizado
            </h3>

            <p className="hercules-detail-subtitle">
              Distribuci?n agrupada por canal y forma de pago.
            </p>

            <ChannelGroups
              items={pagosCanalForma}
            />
          </article>

          <article className="hercules-detail-card">
            <div className="hercules-detail-title-row">
              <div>
                <h3>
                  Checkout
                </h3>

                <p className="hercules-detail-subtitle">
                  Distribuci?n agrupada por canal y forma de pago.
                </p>
              </div>

              <span
                className={
                  checkoutHasAlert
                    ? 'hercules-checkout-status is-alert'
                    : 'hercules-checkout-status is-ok'
                }
              >
                {checkoutHasAlert
                  ? 'Revisar'
                  : 'Normal'}
              </span>
            </div>

            <div
              className={
                checkoutHasAlert
                  ? 'hercules-checkout-banner is-alert'
                  : 'hercules-checkout-banner is-ok'
              }
            >
              <strong>
                {formatNumber(
                  summary.checkout,
                )}
              </strong>

              <span>
                {checkoutHasAlert
                  ? 'Checkout requiere revisi?n'
                  : 'Checkout sin alertas activas'}
              </span>
            </div>

            <ChannelGroups
              items={checkoutCanalForma}
            />
          </article>

          <article className="hercules-detail-card">
            <div className="hercules-detail-title-row">
              <div>
                <h3>
                  Pendiente recaudo
                </h3>

                <p className="hercules-detail-subtitle">
                  Distribuci?n agrupada por canal y forma de pago.
                </p>
              </div>

              <span
                className={
                  hasPendingRecaudoAlert
                    ? 'hercules-recaudo-status is-pending'
                    : 'hercules-recaudo-status is-ok'
                }
              >
                {hasPendingRecaudoAlert
                  ? 'Alerta'
                  : 'Normal'}
              </span>
            </div>

            <div
              className={
                hasPendingRecaudoAlert
                  ? 'hercules-recaudo-banner is-pending'
                  : 'hercules-recaudo-banner is-ok'
              }
            >
              <strong>
                {formatNumber(
                  pendingRecaudoCount,
                )}
              </strong>

              <span>
                {hasPendingRecaudoAlert
                  ? 'Volumen de pendiente recaudo superior al umbral de 40'
                  : 'Pendiente recaudo dentro del rango normal'}
              </span>
            </div>

            <ChannelGroups
              items={recaudoCanalForma}
            />
          </article>

        </div>

      </section>

    </div>
  )
}
