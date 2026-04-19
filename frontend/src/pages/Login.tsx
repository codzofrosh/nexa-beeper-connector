import { useState } from 'react'
import { api, User } from '../api'

const S: Record<string, React.CSSProperties> = {
  page:   { minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 24 },
  box:    { width: '100%', maxWidth: 400, background: '#111827', border: '1px solid #1e293b', borderRadius: 16, padding: 32 },
  title:  { fontSize: 24, fontWeight: 700, marginBottom: 4 },
  sub:    { color: '#94a3b8', fontSize: 14, marginBottom: 24 },
  label:  { display: 'block', fontSize: 13, color: '#cbd5e1', marginBottom: 6 },
  input:  { width: '100%', padding: '10px 12px', borderRadius: 8, border: '1px solid #334155',
            background: '#020617', color: '#f8fafc', fontSize: 14, marginBottom: 14, outline: 'none' },
  btn:    { width: '100%', padding: '11px 0', borderRadius: 8, border: 'none', background: '#2563eb',
            color: 'white', fontWeight: 700, fontSize: 14, cursor: 'pointer', marginTop: 4 },
  oauthRow: { display: 'flex', gap: 10, marginBottom: 20 },
  oBtn:  { flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
           padding: '10px 0', borderRadius: 8, border: '1px solid #334155', background: '#1e293b',
           color: '#e2e8f0', fontSize: 13, fontWeight: 600, cursor: 'pointer' },
  divider: { display: 'flex', alignItems: 'center', gap: 10, color: '#475569', fontSize: 12, marginBottom: 20 },
  divLine: { flex: 1, height: 1, background: '#1e293b' },
  tabs:   { display: 'flex', marginBottom: 24, borderBottom: '1px solid #1e293b' },
  tab:    { flex: 1, padding: '10px 0', background: 'none', border: 'none', cursor: 'pointer', fontSize: 14, fontWeight: 600 },
  err:    { color: '#f87171', fontSize: 13, marginTop: 8, minHeight: 20 },
}

export default function Login({ onLogin }: { onLogin: (u: User) => void }) {
  const [tab, setTab] = useState<'login' | 'register'>('login')
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(''); setLoading(true)
    try {
      const res = tab === 'login'
        ? await api.login(email, password)
        : await api.register(name, email, password)
      if (res.success && res.user) onLogin(res.user)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Something went wrong')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={S.page}>
      <div style={S.box}>
        <div style={S.title}>Nexa</div>
        <div style={S.sub}>AI message routing for WhatsApp &amp; LinkedIn</div>

        {/* OAuth */}
        <div style={S.oauthRow}>
          <button style={S.oBtn} onClick={() => api.oauthStart('google')}>
            <svg width="16" height="16" viewBox="0 0 48 48"><path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/><path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/><path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"/><path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.18 1.48-4.97 2.29-8.16 2.29-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/></svg>
            Google
          </button>
          <button style={S.oBtn} onClick={() => api.oauthStart('github')}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="#e2e8f0"><path d="M12 0C5.37 0 0 5.37 0 12c0 5.3 3.44 9.8 8.21 11.39.6.11.82-.26.82-.58v-2.03c-3.34.72-4.04-1.61-4.04-1.61-.55-1.39-1.34-1.76-1.34-1.76-1.09-.75.08-.73.08-.73 1.2.08 1.84 1.24 1.84 1.24 1.07 1.83 2.81 1.3 3.5.99.11-.78.42-1.3.76-1.6-2.67-.3-5.47-1.33-5.47-5.93 0-1.31.47-2.38 1.24-3.22-.13-.3-.54-1.52.12-3.17 0 0 1.01-.32 3.3 1.23a11.5 11.5 0 013-.4c1.02 0 2.04.14 3 .4 2.28-1.55 3.29-1.23 3.29-1.23.66 1.65.25 2.87.12 3.17.77.84 1.24 1.91 1.24 3.22 0 4.61-2.81 5.63-5.48 5.92.43.37.81 1.1.81 2.22v3.29c0 .32.22.7.83.58C20.56 21.8 24 17.3 24 12c0-6.63-5.37-12-12-12z"/></svg>
            GitHub
          </button>
        </div>

        <div style={S.divider}><span style={S.divLine}/> or <span style={S.divLine}/></div>

        {/* Tabs */}
        <div style={S.tabs}>
          {(['login', 'register'] as const).map(t => (
            <button key={t} style={{ ...S.tab, color: tab === t ? '#e2e8f0' : '#64748b', borderBottom: tab === t ? '2px solid #3b82f6' : '2px solid transparent' }} onClick={() => { setTab(t); setError('') }}>
              {t === 'login' ? 'Sign in' : 'Create account'}
            </button>
          ))}
        </div>

        <form onSubmit={submit}>
          {tab === 'register' && (
            <>
              <label style={S.label}>Name</label>
              <input style={S.input} value={name} onChange={e => setName(e.target.value)} placeholder="Jane Doe" required />
            </>
          )}
          <label style={S.label}>Email</label>
          <input style={S.input} type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="you@example.com" required />
          <label style={S.label}>Password</label>
          <input style={S.input} type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="••••••••" required />
          <button style={{ ...S.btn, opacity: loading ? 0.6 : 1 }} disabled={loading}>
            {loading ? 'Please wait…' : tab === 'login' ? 'Sign in' : 'Create account'}
          </button>
        </form>
        <div style={S.err}>{error}</div>
      </div>
    </div>
  )
}
