import type { ReactNode } from 'react'

interface AppShellProps {
  children: ReactNode
  backendOnline: boolean
}

const navigation = [
  'Centro de Monitoreo',
  'Alertas',
  'Tendencias',
  'Histórico',
  'Monitores',
  'Administración',
  'Configuración',
]

export function AppShell({
  children,
  backendOnline,
}: AppShellProps) {
  const now = new Date()

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">N</div>

          <div>
            <strong>NEXUS</strong>
            <span>Centro de Monitoreo</span>
          </div>
        </div>

        <nav className="navigation">
          {navigation.map((item, index) => (
            <button
              key={item}
              type="button"
              className={index === 0 ? 'nav-item active' : 'nav-item'}
            >
              <span className="nav-symbol">{index + 1}</span>
              {item}
            </button>
          ))}
        </nav>

        <div className="sidebar-status">
          <span>Estado del sistema</span>

          <strong className={backendOnline ? 'online' : 'offline'}>
            <span className="connection-dot" />
            {backendOnline ? 'Backend conectado' : 'Backend sin conexión'}
          </strong>
        </div>
      </aside>

      <main className="main-area">
        <header className="topbar">
          <div>
            <p className="topbar-kicker">NEXUS / OPERACIÓN</p>
            <h1>Centro de Monitoreo</h1>
          </div>

          <div className="topbar-meta">
            <div>
              <span>Fecha</span>
              <strong>
                {now.toLocaleDateString('es-CO', {
                  day: '2-digit',
                  month: 'short',
                  year: 'numeric',
                })}
              </strong>
            </div>

            <div>
              <span>Hora</span>
              <strong>
                {now.toLocaleTimeString('es-CO', {
                  hour: '2-digit',
                  minute: '2-digit',
                })}
              </strong>
            </div>

            <div className="operator">
              <span className="operator-avatar">E</span>
              <div>
                <strong>Operador</strong>
                <span>Modo local</span>
              </div>
            </div>
          </div>
        </header>

        <div className="content-area">{children}</div>
      </main>
    </div>
  )
}
