// Nexa API client
// All requests include credentials so the session cookie is sent automatically.

const BASE = import.meta.env.VITE_API_URL ?? ''

async function req<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(BASE + path, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw Object.assign(new Error(err.detail ?? 'Request failed'), { status: res.status })
  }
  return res.json()
}

export interface User { id: number; name: string; email: string }
export interface Stats {
  total_messages: number
  pending_actions: number
  priority_breakdown: Record<string, number>
  classifier_breakdown: Record<string, number>
  classifier: string
}
export interface Message {
  id: string; platform: string; sender: string; content: string
  timestamp: number; classification: string | null; confidence: number | null
}
export interface OnboardResult {
  session_id: string; status: string; qr: string | null; matrix_user_id: string
}

export const api = {
  // Auth
  register: (name: string, email: string, password: string) =>
    req<{ success: boolean; user: User }>('/api/auth/register', {
      method: 'POST', body: JSON.stringify({ name, email, password }),
    }),
  login: (email: string, password: string) =>
    req<{ success: boolean; user: User }>('/api/auth/login', {
      method: 'POST', body: JSON.stringify({ email, password }),
    }),
  me: () => req<{ authenticated: boolean; user?: User }>('/api/auth/me'),
  logout: () => req<{ success: boolean }>('/api/auth/logout', { method: 'POST' }),
  oauthStart: (provider: 'google' | 'github') => {
    window.location.href = `${BASE}/api/auth/oauth/${provider}/start`
  },

  // Onboarding
  onboardStart: (userId: string) =>
    req<OnboardResult>('/api/onboard/whatsapp/start', {
      method: 'POST', body: JSON.stringify({ user_id: userId }),
    }),
  onboardStatus: (sessionId: string) =>
    req<{ status: string }>(`/api/onboard/whatsapp/status/${sessionId}`),
  onboardQr: (sessionId: string) =>
    req<{ qr: string | null; status: string }>(`/api/onboard/whatsapp/qr/${sessionId}`),
  onboardCancel: (sessionId: string) =>
    req<{ status: string }>(`/api/onboard/whatsapp/session/${sessionId}`, { method: 'DELETE' }),

  // Bridge
  bridgeStatus: (platform: string) =>
    req<{ status: string; bridge_bot: string }>(`/api/bridge/${platform}/status`),
  bridgeLogout: (platform: string) =>
    req<{ status: string }>(`/api/bridge/${platform}/logout`, { method: 'POST' }),

  // Messages + stats
  stats: () => req<Stats>('/api/stats'),
  recentMessages: (limit = 20) => req<{ messages: Message[]; count: number }>(`/api/messages/recent?limit=${limit}`),
  health: () => req<{ status: string }>('/health'),
}
