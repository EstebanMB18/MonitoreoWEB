import { useCallback, useState } from 'react'
import { AppShell } from './layouts/AppShell'
import { DashboardPage } from './pages/DashboardPage'

function App() {
  const [backendOnline, setBackendOnline] = useState(false)

  const handleBackendStatusChange = useCallback((online: boolean) => {
    setBackendOnline(online)
  }, [])

  return (
    <AppShell backendOnline={backendOnline}>
      <DashboardPage
        onBackendStatusChange={handleBackendStatusChange}
      />
    </AppShell>
  )
}

export default App
