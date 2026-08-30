import { useCallback, useState } from 'react'

import { AppShell } from './layouts/AppShell'
import { DashboardPage } from './pages/DashboardPage'
import { MonitorDetailPage } from './pages/MonitorDetailPage'
import { PlaceholderPage } from './pages/PlaceholderPage'

import type { DashboardMonitor } from './types/api'
import type { AppView } from './types/navigation'

function App() {
  const [backendOnline, setBackendOnline] = useState(false)
  const [activeView, setActiveView] =
    useState<AppView>('dashboard')

  const [selectedMonitor, setSelectedMonitor] =
    useState<DashboardMonitor | null>(null)

  const handleBackendStatusChange = useCallback(
    (online: boolean) => {
      setBackendOnline(online)
    },
    [],
  )

  const handleNavigate = useCallback((view: AppView) => {
    setActiveView(view)

    if (view !== 'monitor-detail') {
      setSelectedMonitor(null)
    }
  }, [])

  const handleViewMonitor = useCallback(
    async (monitorId: string) => {
      try {
        const response = await fetch(
          'http://127.0.0.1:8000/api/dashboard',
        )

        const dashboard = (await response.json()) as {
          monitors: DashboardMonitor[]
        }

        const monitor =
          dashboard.monitors.find(
            (item) => item.id === monitorId,
          ) ?? null

        setSelectedMonitor(monitor)
        setActiveView('monitor-detail')
      } catch {
        setSelectedMonitor(null)
        setActiveView('monitor-detail')
      }
    },
    [],
  )

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
      page = (
        <PlaceholderPage
          eyebrow="Histórico"
          title="Histórico"
          description="Consulta de ejecuciones y resultados anteriores."
        />
      )
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
      page = (
        <PlaceholderPage
          eyebrow="Administración"
          title="Administración"
          description="Configuración administrativa de NEXUS."
        />
      )
      break

    case 'settings':
      page = (
        <PlaceholderPage
          eyebrow="Preferencias"
          title="Configuración"
          description="Temas y preferencias de la aplicación."
        />
      )
      break

    case 'monitor-detail':
      page = (
        <MonitorDetailPage
          monitor={selectedMonitor}
          onBack={() => handleNavigate('dashboard')}
        />
      )
      break

    default:
      page = (
        <DashboardPage
          onBackendStatusChange={
            handleBackendStatusChange
          }
          onViewMonitor={handleViewMonitor}
        />
      )
  }

  return (
    <AppShell
      backendOnline={backendOnline}
      activeView={activeView}
      onNavigate={handleNavigate}
    >
      {page}
    </AppShell>
  )
}

export default App
