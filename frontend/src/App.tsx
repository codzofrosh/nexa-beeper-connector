import { Routes, Route, Navigate, useNavigate } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { api, User } from './api'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Onboard from './pages/Onboard'
import Bridges from './pages/Bridges'

const S: Record<string, React.CSSProperties> = {
  layout:  { display: 'flex', minHeight: '100vh' },
  nav:     { width: 220, background: '#111827', borderRight: '1px solid #1e293b',
             padding: '24px 0', display: 'flex', flexDirection: 'column', gap: 4 },
  navTop:  { padding: '0 20px 20px', borderBottom: '1px solid #1e293b', marginBottom: 8 },
  navName: { fontSize: 16, fontWeight: 700 },
  navSub:  { fontSize: 12, color: '#94a3b8', marginTop: 2 },
  link:    { display: 'block', padding: '8px 20px', color: '#94a3b8', textDecoration: 'none',
             fontSize: 14, borderLeft: '2px solid transparent', cursor: 'pointer', background: 'none', border: 'none', width: '100%', textAlign: 'left' },
  main:    { flex: 1, padding: '40px 48px', maxWidth: 900 },
}

function NavLink({ to, label, current, onClick }: { to: string; label: string; current: string; onClick: () => void }) {
  const active = current === to
  return (
    <button
      style={{ ...S.link, color: active ? '#e2e8f0' : '#94a3b8', borderLeftColor: active ? '#3b82f6' : 'transparent', background: active ? 'rgba(59,130,246,.06)' : 'none' }}
      onClick={onClick}
    >
      {label}
    </button>
  )
}

export default function App() {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()
  const path = window.location.pathname

  useEffect(() => {
    api.me().then(r => { if (r.authenticated && r.user) setUser(r.user) })
       .catch(() => {}).finally(() => setLoading(false))
  }, [])

  const handleLogout = async () => {
    await api.logout().catch(() => {})
    setUser(null)
    navigate('/login')
  }

  if (loading) return <div style={{ padding: 40, color: '#94a3b8' }}>Loading…</div>

  if (!user) {
    return (
      <Routes>
        <Route path="/login" element={<Login onLogin={setUser} />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    )
  }

  return (
    <div style={S.layout}>
      <nav style={S.nav}>
        <div style={S.navTop}>
          <div style={S.navName}>Nexa</div>
          <div style={S.navSub}>{user.name}</div>
        </div>
        <NavLink to="/"         label="Dashboard"  current={path} onClick={() => navigate('/')} />
        <NavLink to="/onboard"  label="WhatsApp"   current={path} onClick={() => navigate('/onboard')} />
        <NavLink to="/bridges"  label="Bridges"    current={path} onClick={() => navigate('/bridges')} />
        <div style={{ flex: 1 }} />
        <button style={{ ...S.link, color: '#f87171', marginTop: 8 }} onClick={handleLogout}>
          Sign out
        </button>
      </nav>
      <main style={S.main}>
        <Routes>
          <Route path="/"        element={<Dashboard />} />
          <Route path="/onboard" element={<Onboard />} />
          <Route path="/bridges" element={<Bridges />} />
          <Route path="*"        element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  )
}
