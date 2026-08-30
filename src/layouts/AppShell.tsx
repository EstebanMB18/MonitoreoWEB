import type {
  ReactNode,
} from 'react'

import type { AuthUser } from '../types/auth'
import type { AppView } from '../types/navigation'

interface AppShellProps {
  children: ReactNode
  backendOnline: boolean
  activeView: AppView
  onNavigate: (view: AppView) => void
  currentUser: AuthUser
  onLogout: () => void
}

interface NavigationItem {
  view: AppView
  label: string
  adminOnly?: boolean
}

const navigation: NavigationItem[] = [
  {
    view: 'dashboard',
    label: 'Centro de Monitoreo',
  },
  {
    view: 'alerts',
    label: 'Alertas',
  },
  {
    view: 'trends',
    label: 'Tendencias',
  },
  {
    view: 'history',
    label: 'Hist?rico',
  },
  {
    view: 'monitors',
    label: 'Monitores',
  },
  {
    view: 'admin',
    label: 'Administraci?n',
    adminOnly: true,
  },
  {
    view: 'settings',
    label: 'Configuraci?n',
  },
]

const roleLabels = {
  ADMIN: 'Administrador',
  MONITOR_OFICIAL: 'Monitor oficial',
  OPERADOR: 'Operador',
  CONSULTA: 'Consulta',
}

export function AppShell({
  children,
  backendOnline,
  activeView,
  onNavigate,
  currentUser,
  onLogout,
}: AppShellProps) {
  const visibleNavigation =
    navigation.filter(
      (item) =>
        !item.adminOnly ||
        currentUser.role === 'ADMIN',
    )

  const now = new Date()

  const dateLabel =
    new Intl.DateTimeFormat('es-CO', {
      weekday: 'long',
      day: '2-digit',
      month: 'long',
      year: 'numeric',
    }).format(now)

  const timeLabel =
    new Intl.DateTimeFormat('es-CO', {
      hour: '2-digit',
      minute: '2-digit',
    }).format(now)

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">N</div>

          <div>
            <strong>NEXUS</strong>
            <span>
              Centro de Monitoreo
            </span>
          </div>
        </div>

        <nav className="sidebar-nav">
          {visibleNavigation.map(
            (item) => (
              <button
                key={item.view}
                type="button"
                className={
                  activeView === item.view ||
                  (item.view ===
                    'dashboard' &&
                    activeView ===
                      'monitor-detail')
                    ? 'nav-item active'
                    : 'nav-item'
                }
                onClick={() =>
                  onNavigate(item.view)
                }
              >
                {item.label}
              </button>
            ),
          )}
        </nav>

        <div className="sidebar-footer">
          <span
            className={
              backendOnline
                ? 'backend-dot online'
                : 'backend-dot'
            }
          />

          <div>
            <strong>
              {backendOnline
                ? 'Backend conectado'
                : 'Backend sin conexi?n'}
            </strong>
            <span>Modo local</span>
          </div>
        </div>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div className="topbar-date">
            <strong>{dateLabel}</strong>
            <span>{timeLabel}</span>
          </div>

          <div className="topbar-user">
            <div>
              <strong>
                {currentUser.display_name ||
                  currentUser.email}
              </strong>

              <span>
                {roleLabels[currentUser.role]}
              </span>
            </div>

            <button
              type="button"
              className="logout-button"
              onClick={onLogout}
            >
              Cerrar sesi?n
            </button>
          </div>
        </header>

        <div className="workspace-content">
          {children}
        </div>
      </section>
    </div>
  )
}
