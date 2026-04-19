import { useEffect, useRef, useState } from 'react'
import { api } from '../api'

const S: Record<string, React.CSSProperties> = {
  h1:     { fontSize: 22, fontWeight: 700, marginBottom: 8 },
  sub:    { color: '#94a3b8', fontSize: 14, marginBottom: 28 },
  card:   { background: '#111827', border: '1px solid #1e293b', borderRadius: 16, padding: 32, maxWidth: 480 },
  label:  { display: 'block', fontSize: 13, color: '#cbd5e1', marginBottom: 6 },
  input:  { width: '100%', padding: '10px 12px', borderRadius: 8, border: '1px solid #334155',
            background: '#020617', color: '#f8fafc', fontSize: 14, marginBottom: 16, outline: 'none' },
  btn:    { padding: '11px 24px', borderRadius: 8, border: 'none', background: '#2563eb',
            color: 'white', fontWeight: 700, fontSize: 14, cursor: 'pointer' },
  btnGray:{ padding: '11px 24px', borderRadius: 8, border: '1px solid #334155', background: 'transparent',
            color: '#94a3b8', fontWeight: 600, fontSize: 14, cursor: 'pointer', marginLeft: 10 },
  qrWrap: { margin: '20px 0', textAlign: 'center' },
  qr:     { width: 220, height: 220, borderRadius: 12, border: '2px solid #1e293b' },
  status: { fontSize: 14, marginTop: 12, padding: '10px 14px', borderRadius: 8 },
  steps:  { fontSize: 13, color: '#94a3b8', lineHeight: 2, marginBottom: 20 },
  err:    { color: '#f87171', fontSize: 13, marginTop: 12 },
}

type Phase = 'idle' | 'scanning' | 'connected' | 'error'

export default function Onboard() {
  const [userId, setUserId] = useState('')
  const [phase, setPhase] = useState<Phase>('idle')
  const [qr, setQr] = useState<string | null>(null)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [error, setError] = useState('')

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const qrRef   = useRef<ReturnType<typeof setInterval> | null>(null)

  const clear = () => {
    if (pollRef.current) clearInterval(pollRef.current)
    if (qrRef.current)   clearInterval(qrRef.current)
  }

  useEffect(() => () => clear(), [])

  const start = async () => {
    setError(''); setPhase('scanning'); setQr(null)
    try {
      const res = await api.onboardStart(userId || 'default')
      setSessionId(res.session_id)
      if (res.qr) setQr(res.qr)

      // Refresh QR every 18 s
      qrRef.current = setInterval(async () => {
        try {
          const r = await api.onboardQr(res.session_id)
          if (r.qr) setQr(r.qr)
        } catch { /* ignore */ }
      }, 18_000)

      // Poll status every 3 s
      pollRef.current = setInterval(async () => {
        try {
          const r = await api.onboardStatus(res.session_id)
          if (r.status === 'connected') {
            clear(); setPhase('connected')
            await api.onboardCancel(res.session_id).catch(() => {})
          } else if (r.status === 'expired' || r.status === 'not_found') {
            clear(); setPhase('error'); setError(`Session ${r.status} — please try again.`)
          }
        } catch { /* ignore */ }
      }, 3_000)
    } catch (e: unknown) {
      setPhase('error'); setError(e instanceof Error ? e.message : 'Failed to start onboarding')
    }
  }

  const cancel = async () => {
    clear()
    if (sessionId) await api.onboardCancel(sessionId).catch(() => {})
    setPhase('idle'); setQr(null); setSessionId(null)
  }

  return (
    <div>
      <div style={S.h1}>Connect WhatsApp</div>
      <div style={S.sub}>Link a WhatsApp account so Nexa can receive and classify messages.</div>

      <div style={S.card}>
        {phase === 'idle' && (
          <>
            <div style={S.steps}>
              1. Enter a user ID (any label, e.g. your name)<br/>
              2. Click Start — a QR code will appear<br/>
              3. Open WhatsApp on your phone → Linked devices → Link a device<br/>
              4. Scan the QR code
            </div>
            <label style={S.label}>User ID</label>
            <input style={S.input} value={userId} onChange={e => setUserId(e.target.value)} placeholder="e.g. alice" />
            <button style={S.btn} onClick={start}>Start onboarding</button>
          </>
        )}

        {phase === 'scanning' && (
          <>
            <div style={{ color: '#94a3b8', fontSize: 13, marginBottom: 8 }}>
              Scan with WhatsApp → Linked devices → Link a device
            </div>
            {qr
              ? <div style={S.qrWrap}><img style={S.qr} src={qr} alt="QR code" /></div>
              : <div style={{ ...S.status, background: '#1e3a5f', color: '#93c5fd' }}>Waiting for QR code…</div>
            }
            <div style={{ ...S.status, background: '#0c1a2e', color: '#7dd3fc', marginTop: 8 }}>
              Polling for connection… QR refreshes every 18 s
            </div>
            <button style={{ ...S.btnGray, marginLeft: 0, marginTop: 16 }} onClick={cancel}>Cancel</button>
          </>
        )}

        {phase === 'connected' && (
          <div style={{ textAlign: 'center', padding: '16px 0' }}>
            <div style={{ fontSize: 40, marginBottom: 12 }}>✅</div>
            <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 8 }}>WhatsApp connected!</div>
            <div style={{ color: '#94a3b8', fontSize: 13, marginBottom: 20 }}>
              Messages will now be classified automatically.
            </div>
            <button style={S.btn} onClick={() => { setPhase('idle'); setQr(null) }}>Connect another</button>
          </div>
        )}

        {phase === 'error' && (
          <>
            <div style={S.err}>{error}</div>
            <button style={{ ...S.btn, marginTop: 16 }} onClick={() => setPhase('idle')}>Try again</button>
          </>
        )}
      </div>
    </div>
  )
}
