import {
  useState,
  type ReactNode,
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
  shortLabel: string
  adminOnly?: boolean
}

const navigation: NavigationItem[] = [
  {
    view: 'dashboard',
    label: 'Centro de Monitoreo',
    shortLabel: 'CM',
  },
  {
    view: 'alerts',
    label: 'Alertas',
    shortLabel: 'AL',
  },
  {
    view: 'trends',
    label: 'Tendencias',
    shortLabel: 'TR',
  },
  {
    view: 'history',
    label: 'Histórico',
    shortLabel: 'HI',
  },
  {
    view: 'monitors',
    label: 'Monitores',
    shortLabel: 'MO',
  },
  {
    view: 'admin',
    label: 'Administración',
    shortLabel: 'AD',
    adminOnly: true,
  },
  {
    view: 'settings',
    label: 'Configuración',
    shortLabel: 'CF',
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
  const [sidebarCollapsed, setSidebarCollapsed] =
    useState(false)

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
    <div
      className={
        sidebarCollapsed
          ? 'app-shell sidebar-collapsed'
          : 'app-shell'
      }
    >
      <aside
        className={
          sidebarCollapsed
            ? 'sidebar collapsed'
            : 'sidebar'
        }
      >
        <div className="brand">
          <div className="brand-main">
            <div className="brand-mark">
              N
            </div>

            <div className="brand-copy">
              <strong>NEXUS</strong>
              <span>
                Centro de Monitoreo
              </span>
            </div>
          </div>

          <button
            type="button"
            className="sidebar-toggle"
            aria-label={
              sidebarCollapsed
                ? 'Mostrar men?'
                : 'Ocultar men?'
            }
            title={
              sidebarCollapsed
                ? 'Mostrar men?'
                : 'Ocultar men?'
            }
            onClick={() =>
              setSidebarCollapsed(
                (current) => !current,
              )
            }
          >
            <span />
            <span />
            <span />
          </button>
        </div>

        <nav className="sidebar-nav">
          {visibleNavigation.map(
            (item) => {
              const active =
                activeView === item.view ||
                (item.view === 'dashboard' &&
                  activeView ===
                    'monitor-detail')

              return (
                <button
                  key={item.view}
                  type="button"
                  title={
                    sidebarCollapsed
                      ? item.label
                      : undefined
                  }
                  className={
                    active
                      ? 'nav-item active'
                      : 'nav-item'
                  }
                  onClick={() =>
                    onNavigate(item.view)
                  }
                >
                  <span
                    className="nav-symbol"
                    aria-hidden="true"
                  >
                    {item.shortLabel}
                  </span>

                  <span className="nav-label">
                    {item.label}
                  </span>
                </button>
              )
            },
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
                : 'Backend sin conexión'}
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
              Cerrar sesión
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
