import { useEffect, useState } from 'react'
import { api } from '../api'

const S: Record<string, React.CSSProperties> = {
  h1:     { fontSize: 22, fontWeight: 700, marginBottom: 8 },
  sub:    { color: '#94a3b8', fontSize: 14, marginBottom: 28 },
  card:   { background: '#111827', border: '1px solid #1e293b', borderRadius: 16, padding: 28, marginBottom: 20 },
  row:    { display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 },
  name:   { fontSize: 16, fontWeight: 700 },
  desc:   { fontSize: 13, color: '#94a3b8', marginTop: 2 },
  btn:    { padding: '8px 20px', borderRadius: 8, border: 'none', background: '#2563eb',
            color: 'white', fontWeight: 600, fontSize: 13, cursor: 'pointer' },
  btnRed: { padding: '8px 20px', borderRadius: 8, border: 'none', background: '#991b1b',
            color: '#fca5a5', fontWeight: 600, fontSize: 13, cursor: 'pointer' },
  btnGray:{ padding: '8px 20px', borderRadius: 8, border: '1px solid #334155', background: 'transparent',
            color: '#64748b', fontWeight: 600, fontSize: 13, cursor: 'not-allowed' },
  dot:    { width: 8, height: 8, borderRadius: '50%', display: 'inline-block', marginRight: 8 },
  status: { display: 'flex', alignItems: 'center', fontSize: 13, marginTop: 4 },
  err:    { color: '#f87171', fontSize: 13, marginTop: 8 },
  ok:     { color: '#86efac', fontSize: 13, marginTop: 8 },
}

interface BridgeState {
  loading: boolean
  status: string | null
  error: string
  actionMsg: string
  acting: boolean
}

function statusColor(s: string | null) {
  if (!s) return '#475569'
  if (s === 'connected') return '#22c55e'
  if (s === 'logged_out' || s === 'disconnected') return '#f59e0b'
  return '#64748b'
}

function statusLabel(s: string | null) {
  if (!s) return 'Unknown'
  return s.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}

function BridgeCard({
  platform,
  displayName,
  description,
  connectPath,
}: {
  platform: string
  displayName: string
  description: string
  connectPath: string
}) {
  const [state, setState] = useState<BridgeState>({
    loading: true, status: null, error: '', actionMsg: '', acting: false,
  })

  const set = (patch: Partial<BridgeState>) => setState(p => ({ ...p, ...patch }))

  useEffect(() => {
    api.bridgeStatus(platform)
      .then(r => set({ loading: false, status: r.status }))
      .catch(() => set({ loading: false, status: null, error: 'Could not reach bridge' }))
  }, [platform])

  const disconnect = async () => {
    set({ acting: true, actionMsg: '', error: '' })
    try {
      await api.bridgeLogout(platform)
      set({ acting: false, status: 'logged_out', actionMsg: 'Disconnected successfully.' })
    } catch (e: unknown) {
      set({ acting: false, error: e instanceof Error ? e.message : 'Logout failed' })
    }
  }

  const isConnected = state.status === 'connected'

  return (
    <div style={S.card}>
      <div style={S.row}>
        <div>
          <div style={S.name}>{displayName}</div>
          <div style={S.desc}>{description}</div>
          {!state.loading && (
            <div style={S.status}>
              <span style={{ ...S.dot, background: statusColor(state.status) }} />
              <span style={{ color: statusColor(state.status) }}>{statusLabel(state.status)}</span>
            </div>
          )}
          {state.loading && <div style={{ ...S.status, color: '#475569' }}>Checking…</div>}
        </div>
        <div style={{ display: 'flex', gap: 10 }}>
          {isConnected
            ? <button style={{ ...S.btnRed, opacity: state.acting ? 0.6 : 1 }} onClick={disconnect} disabled={state.acting}>
                {state.acting ? 'Disconnecting…' : 'Disconnect'}
              </button>
            : <button style={S.btn} onClick={() => window.location.href = connectPath}>
                Connect
              </button>
          }
        </div>
      </div>
      {state.error   && <div style={S.err}>{state.error}</div>}
      {state.actionMsg && <div style={S.ok}>{state.actionMsg}</div>}
    </div>
  )
}

export default function Bridges() {
  return (
    <div>
      <div style={S.h1}>Bridges</div>
      <div style={S.sub}>Manage connected messaging platforms.</div>

      <BridgeCard
        platform="whatsapp"
        displayName="WhatsApp"
        description="Receive and classify WhatsApp messages via mautrix-whatsapp"
        connectPath="/onboard"
      />

      <BridgeCard
        platform="linkedin"
        displayName="LinkedIn"
        description="Receive and classify LinkedIn messages via mautrix-linkedin"
        connectPath="/onboard-linkedin"
      />
    </div>
  )
}
