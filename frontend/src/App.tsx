import type { ReactElement } from 'react'
import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import AdminPage from './pages/AdminPage'
import CatalogPage from './pages/CatalogPage'
import LoginPage from './pages/LoginPage'
import OverviewPage from './pages/OverviewPage'
import ProfilePage from './pages/ProfilePage'
import TradePage from './pages/TradePage'
import WatchlistsPage from './pages/WatchlistsPage'
import { SessionProvider, useSession } from './lib/session'

function Protected({ children }: { children: ReactElement }) {
  const location = useLocation()
  const { status, retry } = useSession()
  if (status === 'loading') return <div className="loading">Checking your session…</div>
  if (status === 'unavailable') {
    return <div className="loading"><div className="stack">
      <div className="alert error">MarketScope could not be reached.</div>
      <button className="primary" onClick={retry}>Retry</button>
    </div></div>
  }
  return status === 'authenticated' ? children : <Navigate to="/login" replace state={{ from: location }} />
}

export default function App() {
  return <SessionProvider>
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/" element={<Protected><OverviewPage /></Protected>} />
      <Route path="/catalog" element={<Protected><CatalogPage /></Protected>} />
      <Route path="/trade" element={<Protected><TradePage /></Protected>} />
      <Route path="/watchlists" element={<Protected><WatchlistsPage /></Protected>} />
      <Route path="/profile" element={<Protected><ProfilePage /></Protected>} />
      <Route path="/admin" element={<Protected><AdminPage /></Protected>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  </SessionProvider>
}
