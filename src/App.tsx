import {
  useCallback,
  useEffect,
  useState,
} from 'react'

import { AppShell } from './layouts/AppShell'
import { AuthPage } from './pages/AuthPage'
import { DashboardPage } from './pages/DashboardPage'
import { HistoryPage } from './pages/HistoryPage'
import { MonitorDetailPage } from './pages/MonitorDetailPage'
import { PlaceholderPage } from './pages/PlaceholderPage'

import { api } from './services/api'
import { clearAccessToken } from './services/authSession'

import type { DashboardMonitor } from './types/api'
import type {
  AuthStatus,
  AuthUser,
} from './types/auth'
import type { AppView } from './types/navigation'

function App() {
  const [authReady, setAuthReady] =
    useState(false)

  const [authStatus, setAuthStatus] =
    useState<AuthStatus | null>(null)

  const [currentUser, setCurrentUser] =
    useState<AuthUser | null>(null)

  const [authError, setAuthError] =
    useState<string | null>(null)

  const [backendOnline, setBackendOnline] =
    useState(false)

  const [activeView, setActiveView] =
    useState<AppView>('dashboard')

  const [selectedMonitor, setSelectedMonitor] =
    useState<DashboardMonitor | null>(null)

  const loadAuthStatus =
    useCallback(async () => {
      setAuthError(null)

      try {
        const status = await api.authStatus()
        setAuthStatus(status)
        setBackendOnline(true)
      } catch (err) {
        setBackendOnline(false)

        setAuthError(
          err instanceof Error
            ? err.message
            : 'No fue posible conectar con NEXUS.',
        )
      } finally {
        setAuthReady(true)
      }
    }, [])

  useEffect(() => {
    const initialAuthLoad =
      window.setTimeout(() => {
        void loadAuthStatus()
      }, 0)

    const handleExpired = () => {
      clearAccessToken()
      setCurrentUser(null)
      setActiveView('dashboard')
      setSelectedMonitor(null)
    }

    window.addEventListener(
      'nexus:auth-expired',
      handleExpired,
    )

    return () => {
      window.clearTimeout(initialAuthLoad)

      window.removeEventListener(
        'nexus:auth-expired',
        handleExpired,
      )
    }
  }, [loadAuthStatus])

  const handleBackendStatusChange =
    useCallback((online: boolean) => {
      setBackendOnline(online)
    }, [])

  const handleNavigate =
    useCallback((view: AppView) => {
      setActiveView(view)

      if (view !== 'monitor-detail') {
        setSelectedMonitor(null)
      }
    }, [])

  const handleViewMonitor =
    useCallback(async (monitorId: string) => {
      try {
        const dashboard =
          await api.dashboard()

        const monitor =
          dashboard.monitors.find(
            (item) =>
              item.id === monitorId,
          ) ?? null

        setSelectedMonitor(monitor)
      } catch {
        setSelectedMonitor(null)
      }

      setActiveView('monitor-detail')
    }, [])

  const handleLogout =
    useCallback(async () => {
      try {
        await api.logout()
      } catch {
        // Limpiar localmente aunque el backend
        // ya haya invalidado o expirado el token.
      } finally {
        clearAccessToken()
        setCurrentUser(null)
        setActiveView('dashboard')
        setSelectedMonitor(null)
      }
    }, [])

  if (!authReady) {
    return (
      <main className="auth-loading-screen">
        <div className="auth-loading-card">
          <strong>NEXUS</strong>
          <span>
            Validando configuración local...
          </span>
        </div>
      </main>
    )
  }

  if (!authStatus) {
    return (
      <main className="auth-loading-screen">
        <div className="auth-loading-card">
          <strong>NEXUS no disponible</strong>
          <span>
            {authError ??
              'No fue posible conectar con el backend.'}
          </span>

          <button
            type="button"
            onClick={() => {
              setAuthReady(false)
              void loadAuthStatus()
            }}
          >
            Reintentar
          </button>
        </div>
      </main>
    )
  }

  if (
    authStatus.bootstrap_required ||
    !currentUser
  ) {
    return (
      <AuthPage
        bootstrapRequired={
          authStatus.bootstrap_required
        }
        onAuthenticated={setCurrentUser}
        onBootstrapComplete={
          loadAuthStatus
        }
      />
    )
  }

  const canExecuteManual =
    currentUser.role !== 'CONSULTA'

  let page

  switch (activeView) {
    case 'alerts':
      page = (
        <PlaceholderPage
          eyebrow="Alertas"
          title="Alertas"
          description="Gestión de alertas activas e históricas."
        />
      )
      break

    case 'trends':
      page = (
        <PlaceholderPage
          eyebrow="Análisis"
          title="Tendencias"
          description="Evolución histórica y comportamiento de los monitores."
        />
      )
      break

    case 'history':
      page = <HistoryPage />
      break

    case 'monitors':
      page = (
        <PlaceholderPage
          eyebrow="Monitores"
          title="Monitores"
          description="Vista consolidada de monitores disponibles."
        />
      )
      break

    case 'admin':
      page =
        currentUser.role === 'ADMIN' ? (
          <PlaceholderPage
            eyebrow="Administración"
            title="Administración"
            description="Usuarios, roles y administración de NEXUS."
          />
        ) : (
          <PlaceholderPage
            eyebrow="Acceso restringido"
            title="Sin permisos"
            description="Tu rol no tiene permisos administrativos."
          />
        )
      break

    case 'settings':
      page = (
        <PlaceholderPage
          eyebrow="Preferencias"
          title="Configuración"
          description="Temas, carpetas, credenciales y preferencias de NEXUS."
        />
      )
      break

    case 'monitor-detail':
      page = (
        <MonitorDetailPage
          monitor={selectedMonitor}
          onBack={() =>
            handleNavigate('dashboard')
          }
        />
      )
      break

    default:
      page = (
        <DashboardPage
          onBackendStatusChange={
            handleBackendStatusChange
          }
          onViewMonitor={
            handleViewMonitor
          }
          canExecuteManual={
            canExecuteManual
          }
        />
      )
  }

  return (
    <AppShell
      backendOnline={backendOnline}
      activeView={activeView}
      onNavigate={handleNavigate}
      currentUser={currentUser}
      onLogout={handleLogout}
    >
      {page}
    </AppShell>
  )
}

export default App
