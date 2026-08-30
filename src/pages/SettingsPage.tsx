import type {
  ThemeMode,
} from '../types/theme'

import {
  resolveTheme,
} from '../utils/theme'

interface SettingsPageProps {
  themeMode: ThemeMode
  onThemeModeChange: (
    mode: ThemeMode,
  ) => void
}

const themeOptions: Array<{
  id: ThemeMode
  label: string
  description: string
}> = [
  {
    id: 'AUTO',
    label: 'Automático',
    description:
      'NEXUS cambia según la hora del día.',
  },
  {
    id: 'LIGHT',
    label: 'Claro',
    description:
      'Superficies claras y alto contraste.',
  },
  {
    id: 'DARK',
    label: 'Oscuro',
    description:
      'Tema tecnológico oscuro permanente.',
  },
  {
    id: 'DAY',
    label: 'Día',
    description:
      'Tonos frescos para la mañana.',
  },
  {
    id: 'AFTERNOON',
    label: 'Tarde',
    description:
      'Ambiente cálido para la tarde.',
  },
  {
    id: 'NIGHT',
    label: 'Noche',
    description:
      'Visual nocturna de mayor profundidad.',
  },
]

const resolvedLabels = {
  light: 'Claro',
  dark: 'Oscuro',
  day: 'Día',
  afternoon: 'Tarde',
  night: 'Noche',
}

export function SettingsPage({
  themeMode,
  onThemeModeChange,
}: SettingsPageProps) {
  const resolved =
    resolveTheme(themeMode)

  return (
    <div className="settings-page">
      <section className="settings-heading">
        <div>
          <span className="section-eyebrow">
            Preferencias
          </span>

          <h1>Configuración</h1>

          <p>
            Personaliza la experiencia
            visual y prepara los ajustes
            operativos de NEXUS.
          </p>
        </div>

        <div className="settings-current-theme">
          <span>Tema activo</span>
          <strong>
            {resolvedLabels[resolved]}
          </strong>
        </div>
      </section>

      <div className="settings-tabs">
        <button
          type="button"
          className="active"
        >
          Apariencia
        </button>

        <button type="button">
          Rutas y salidas
        </button>

        <button type="button">
          Monitores
        </button>

        <button type="button">
          Credenciales
        </button>

        <button type="button">
          Seguridad
        </button>
      </div>

      <section className="settings-layout">
        <article className="settings-card theme-settings-card">
          <header>
            <div>
              <span className="section-eyebrow">
                Apariencia
              </span>

              <h2>
                Tema de la aplicación
              </h2>

              <p>
                Selecciona el ambiente
                visual de NEXUS.
              </p>
            </div>
          </header>

          <div className="theme-option-list">
            {themeOptions.map(
              (option) => (
                <label
                  key={option.id}
                  className={
                    themeMode === option.id
                      ? 'theme-option selected'
                      : 'theme-option'
                  }
                >
                  <input
                    type="radio"
                    name="nexus-theme"
                    value={option.id}
                    checked={
                      themeMode === option.id
                    }
                    onChange={() =>
                      onThemeModeChange(
                        option.id,
                      )
                    }
                  />

                  <div>
                    <strong>
                      {option.label}
                    </strong>

                    <span>
                      {option.description}
                    </span>
                  </div>
                </label>
              ),
            )}
          </div>
        </article>

        <article className="settings-card theme-preview-card">
          <header>
            <span className="section-eyebrow">
              Vista previa
            </span>

            <h2>
              NEXUS ? {resolvedLabels[resolved]}
            </h2>
          </header>

          <div className="theme-preview-surface">
            <div className="theme-preview-top">
              <div>
                <span>Monitor</span>
                <strong>PASARELAS</strong>
              </div>

              <span className="theme-preview-status">
                NORMAL
              </span>
            </div>

            <strong className="theme-preview-value">
              98.6%
            </strong>

            <span className="theme-preview-label">
              Operación estable
            </span>

            <div className="theme-preview-chart">
              <span style={{ height: '30%' }} />
              <span style={{ height: '48%' }} />
              <span style={{ height: '38%' }} />
              <span style={{ height: '66%' }} />
              <span style={{ height: '55%' }} />
              <span style={{ height: '82%' }} />
              <span style={{ height: '70%' }} />
            </div>
          </div>

          <div className="theme-preview-palette">
            <span />
            <span />
            <span />
            <span />
            <span />
          </div>
        </article>
      </section>

      <section className="settings-secondary-grid">
        <article className="settings-card">
          <span className="section-eyebrow">
            Instalación
          </span>

          <h2>Modo de uso</h2>

          <p>
            Preparación visual para los
            dos perfiles de instalación.
          </p>

          <div className="installation-mode-options">
            <button
              type="button"
              className="active"
            >
              <strong>Usuario</strong>
              <span>
                Operación normal
              </span>
            </button>

            <button type="button">
              <strong>
                Desarrollo
              </strong>
              <span>
                Diagnóstico y pruebas
              </span>
            </button>
          </div>

          <small>
            La lógica de instalación
            se implementará posteriormente.
          </small>
        </article>

        <article className="settings-card settings-future-card">
          <span className="section-eyebrow">
            Rutas
          </span>

          <h2>Carpetas de salida</h2>

          <div>
            <span>
              Carpeta de reportes
            </span>
            <strong>
              Pendiente de configurar
            </strong>
          </div>

          <div>
            <span>Histórico</span>
            <strong>
              Pendiente de configurar
            </strong>
          </div>

          <div>
            <span>Exportaciones</span>
            <strong>
              Pendiente de configurar
            </strong>
          </div>
        </article>

        <article className="settings-card settings-future-card">
          <span className="section-eyebrow">
            Seguridad
          </span>

          <h2>Credenciales</h2>

          <div>
            <span>AWS</span>
            <strong>
              Estado protegido
            </strong>
          </div>

          <div>
            <span>Pasarelas</span>
            <strong>
              Estado protegido
            </strong>
          </div>

          <div>
            <span>Hércules</span>
            <strong>
              Estado protegido
            </strong>
          </div>

          <small>
            NEXUS nunca mostrará la
            contraseña almacenada.
          </small>
        </article>
      </section>
    </div>
  )
}
