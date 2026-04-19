import { useEffect, useState } from 'react'
import { api, Stats, Message } from '../api'

const S: Record<string, React.CSSProperties> = {
  h1:    { fontSize: 22, fontWeight: 700, marginBottom: 24 },
  cards: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 16, marginBottom: 32 },
  card:  { background: '#111827', border: '1px solid #1e293b', borderRadius: 12, padding: '20px 20px' },
  num:   { fontSize: 32, fontWeight: 700, color: '#3b82f6' },
  lbl:   { fontSize: 13, color: '#94a3b8', marginTop: 4 },
  table: { width: '100%', borderCollapse: 'collapse', fontSize: 13 },
  th:    { padding: '10px 12px', textAlign: 'left', color: '#64748b', borderBottom: '1px solid #1e293b', fontWeight: 500 },
  td:    { padding: '10px 12px', borderBottom: '1px solid #0f172a', color: '#cbd5e1', verticalAlign: 'top' },
  pill:  { display: 'inline-block', padding: '2px 8px', borderRadius: 20, fontSize: 11, fontWeight: 600 },
  sec:   { marginBottom: 32 },
  secH:  { fontSize: 15, fontWeight: 600, color: '#94a3b8', marginBottom: 12 },
  muted: { color: '#475569', fontSize: 13, padding: '20px 0' },
  badge: { display: 'inline-block', padding: '2px 8px', borderRadius: 6, fontSize: 11,
           fontWeight: 600, background: '#1e3a5f', color: '#93c5fd' },
}

function pillColor(c: string | null) {
  if (!c) return { background: '#1e293b', color: '#94a3b8' }
  const map: Record<string, { background: string; color: string }> = {
    ENQUIRY:   { background: '#1e3a5f', color: '#93c5fd' },
    INTENT:    { background: '#14532d', color: '#86efac' },
    PROMOTION: { background: '#422006', color: '#fde68a' },
    SOCIAL:    { background: '#2e1065', color: '#d8b4fe' },
  }
  return map[c] ?? { background: '#1e293b', color: '#94a3b8' }
}

export default function Dashboard() {
  const [stats, setStats] = useState<Stats | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([api.stats(), api.recentMessages(10)])
      .then(([s, m]) => { setStats(s); setMessages(m.messages) })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div style={{ color: '#94a3b8' }}>Loading…</div>

  return (
    <div>
      <div style={S.h1}>Dashboard</div>

      <div style={S.cards}>
        <div style={S.card}>
          <div style={S.num}>{stats?.total_messages ?? 0}</div>
          <div style={S.lbl}>Total messages</div>
        </div>
        <div style={S.card}>
          <div style={{ ...S.num, color: '#f59e0b' }}>{stats?.pending_actions ?? 0}</div>
          <div style={S.lbl}>Pending actions</div>
        </div>
        <div style={S.card}>
          <div style={{ ...S.num, color: '#22c55e', fontSize: 18, marginTop: 6 }}>{stats?.classifier ?? '—'}</div>
          <div style={S.lbl}>AI classifier</div>
        </div>
      </div>

      {stats && Object.keys(stats.priority_breakdown).length > 0 && (
        <div style={S.sec}>
          <div style={S.secH}>Priority breakdown</div>
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
            {Object.entries(stats.priority_breakdown).map(([k, v]) => (
              <div key={k} style={{ ...S.card, padding: '12px 16px', minWidth: 100 }}>
                <div style={{ fontSize: 22, fontWeight: 700 }}>{v}</div>
                <div style={S.lbl}>{k}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div style={S.sec}>
        <div style={S.secH}>Recent messages</div>
        {messages.length === 0
          ? <div style={S.muted}>No messages yet.</div>
          : (
          <table style={S.table}>
            <thead>
              <tr>
                <th style={S.th}>Sender</th>
                <th style={S.th}>Content</th>
                <th style={S.th}>Platform</th>
                <th style={S.th}>Classification</th>
              </tr>
            </thead>
            <tbody>
              {messages.map(m => (
                <tr key={m.id}>
                  <td style={{ ...S.td, color: '#64748b', fontSize: 12 }}>{m.sender.split(':')[0]}</td>
                  <td style={S.td}>{m.content.length > 80 ? m.content.slice(0, 80) + '…' : m.content}</td>
                  <td style={S.td}><span style={S.badge}>{m.platform}</span></td>
                  <td style={S.td}>
                    {m.classification
                      ? <span style={{ ...S.pill, ...pillColor(m.classification) }}>{m.classification}</span>
                      : <span style={{ color: '#475569' }}>—</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
