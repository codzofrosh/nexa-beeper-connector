"""
Returns the HTML string for the frontend developer guide served at GET /dev.
"""


def render() -> str:
    return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Nexa API — Frontend Developer Guide</title>
  <style>
    :root {
      --bg: #0f172a; --surface: #111827; --border: #1e293b;
      --text: #e2e8f0; --muted: #94a3b8; --accent: #3b82f6;
      --green: #22c55e; --yellow: #eab308; --red: #ef4444;
      --code-bg: #020617;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: ui-sans-serif, system-ui, sans-serif; background: var(--bg); color: var(--text);
           line-height: 1.6; display: flex; min-height: 100vh; }

    /* ── Sidebar ── */
    nav { width: 240px; min-width: 240px; background: var(--surface); border-right: 1px solid var(--border);
          padding: 24px 0; position: sticky; top: 0; height: 100vh; overflow-y: auto; }
    nav h2 { font-size: 11px; text-transform: uppercase; letter-spacing: .1em; color: var(--muted);
              padding: 0 20px 8px; }
    nav a { display: block; padding: 7px 20px; color: var(--muted); text-decoration: none; font-size: 14px;
             border-left: 2px solid transparent; }
    nav a:hover, nav a.active { color: var(--text); border-left-color: var(--accent); background: rgba(59,130,246,.06); }
    nav .section-title { padding: 16px 20px 4px; font-size: 11px; text-transform: uppercase;
                          letter-spacing: .08em; color: #475569; }

    /* ── Main ── */
    main { flex: 1; padding: 48px 56px; max-width: 900px; }
    h1 { font-size: 28px; font-weight: 700; margin-bottom: 8px; }
    h2 { font-size: 20px; font-weight: 600; margin: 40px 0 12px; padding-top: 8px;
          border-top: 1px solid var(--border); }
    h3 { font-size: 15px; font-weight: 600; margin: 24px 0 8px; color: #cbd5e1; }
    p  { color: var(--muted); margin-bottom: 12px; }
    a  { color: var(--accent); text-decoration: none; }
    a:hover { text-decoration: underline; }
    ul { color: var(--muted); padding-left: 20px; margin-bottom: 12px; }
    li { margin-bottom: 4px; }

    /* ── Endpoint badge ── */
    .endpoint { display: flex; align-items: flex-start; gap: 12px; margin-bottom: 20px;
                background: var(--surface); border: 1px solid var(--border); border-radius: 10px;
                padding: 14px 16px; }
    .method { font-size: 11px; font-weight: 700; padding: 3px 8px; border-radius: 6px;
               min-width: 52px; text-align: center; flex-shrink: 0; margin-top: 2px; }
    .GET    { background: #14532d; color: #86efac; }
    .POST   { background: #1e3a5f; color: #93c5fd; }
    .DELETE { background: #4c1d20; color: #fca5a5; }
    .endpoint-info { flex: 1; }
    .endpoint-path { font-family: ui-monospace, monospace; font-size: 14px; color: var(--text); }
    .endpoint-desc { font-size: 13px; color: var(--muted); margin-top: 4px; }

    /* ── Code block ── */
    .code-wrap { margin: 12px 0 20px; }
    .code-label { font-size: 11px; color: var(--muted); margin-bottom: 4px; }
    pre { background: var(--code-bg); border: 1px solid var(--border); border-radius: 8px;
           padding: 14px 16px; overflow-x: auto; font-size: 13px; line-height: 1.5; }
    code { font-family: ui-monospace, 'Cascadia Code', monospace; }
    .inline { background: var(--code-bg); padding: 2px 6px; border-radius: 4px;
               font-family: ui-monospace, monospace; font-size: 13px; color: #a5f3fc; }

    /* ── Callout ── */
    .callout { border-radius: 8px; padding: 12px 16px; margin: 16px 0; font-size: 14px; }
    .callout.info   { background: #0c1a2e; border: 1px solid #1e3a5f; color: #93c5fd; }
    .callout.warn   { background: #1c1500; border: 1px solid #713f12; color: #fde68a; }
    .callout.tip    { background: #052e16; border: 1px solid #14532d; color: #86efac; }

    /* ── Status pill ── */
    .pill { display: inline-block; font-size: 11px; font-weight: 600; padding: 2px 8px;
             border-radius: 20px; margin: 2px; }
    .pill-green  { background: #14532d; color: #86efac; }
    .pill-yellow { background: #422006; color: #fde68a; }
    .pill-red    { background: #4c1d20; color: #fca5a5; }

    /* ── Flow diagram ── */
    .flow { display: flex; flex-direction: column; gap: 4px; margin: 16px 0; }
    .flow-step { display: flex; align-items: center; gap: 10px; font-size: 13px; color: var(--muted); }
    .flow-step .num { background: var(--accent); color: white; width: 22px; height: 22px; border-radius: 50%;
                       display: flex; align-items: center; justify-content: center; font-size: 11px;
                       font-weight: 700; flex-shrink: 0; }
    .flow-arrow { color: #475569; padding-left: 10px; font-size: 12px; }

    .swagger-link { display: inline-flex; align-items: center; gap: 8px; background: #1e3a5f;
                     border: 1px solid #2563eb; border-radius: 8px; padding: 10px 16px;
                     color: #93c5fd; font-weight: 600; font-size: 14px; text-decoration: none; margin: 8px 0; }
    .swagger-link:hover { background: #1d4ed8; color: white; text-decoration: none; }
  </style>
</head>
<body>

<nav>
  <div style="padding:0 20px 20px; border-bottom:1px solid var(--border); margin-bottom:12px;">
    <div style="font-size:16px; font-weight:700; color:var(--text);">Nexa API</div>
    <div style="font-size:12px; color:var(--muted);">Frontend Developer Guide</div>
  </div>
  <div class="section-title">Getting Started</div>
  <a href="#overview">Overview</a>
  <a href="#swagger">Swagger UI</a>
  <a href="#auth-model">Auth model</a>
  <div class="section-title">Auth</div>
  <a href="#register-login">Register &amp; Login</a>
  <a href="#oauth">OAuth (Google / GitHub)</a>
  <a href="#logout">Logout</a>
  <div class="section-title">Onboarding</div>
  <a href="#whatsapp-onboard">WhatsApp QR flow</a>
  <div class="section-title">Bridge Management</div>
  <a href="#bridge">Connect / disconnect</a>
  <div class="section-title">Messages</div>
  <a href="#messages">Classify &amp; retrieve</a>
  <div class="section-title">User &amp; System</div>
  <a href="#user-status">User status</a>
  <a href="#system">Health &amp; stats</a>
  <div class="section-title">Reference</div>
  <a href="#errors">Error handling</a>
  <a href="#full-client">Full JS client</a>
</nav>

<main>

  <h1>Nexa API — Frontend Integration Guide</h1>
  <p>Everything a frontend developer needs to integrate with the Nexa sidecar.</p>
  <a class="swagger-link" href="/docs" target="_blank">
    <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 14H9V8h2v8zm4 0h-2V8h2v8z"/></svg>
    Open Swagger UI → /docs
  </a>
  <a class="swagger-link" href="/redoc" target="_blank" style="margin-left:8px;">
    <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8l-6-6zm-1 1.5L18.5 9H13V3.5zM6 20V4h5v7h7v9H6z"/></svg>
    ReDoc → /redoc
  </a>

  <!-- ─── Overview ─── -->
  <h2 id="overview">Overview</h2>
  <p><strong>Base URL:</strong> <span class="inline">http://localhost:8080</span> (local dev) or set by <span class="inline">SIDECAR_URL</span> in production.</p>
  <p>All API responses are JSON. Requests with a body must send <span class="inline">Content-Type: application/json</span>.</p>
  <p>Authentication uses an <strong>HttpOnly session cookie</strong> (<span class="inline">nexa_session</span>). Always include <span class="inline">credentials: 'include'</span> in every <span class="inline">fetch()</span> call so the browser sends the cookie automatically.</p>

  <!-- ─── Swagger ─── -->
  <h2 id="swagger">Using Swagger UI</h2>
  <p>Swagger UI is built into FastAPI and requires no setup. Open <a href="/docs" target="_blank">/docs</a> in your browser while the sidecar is running.</p>
  <div class="callout tip">
    <strong>Tip:</strong> Endpoints are grouped into coloured sections — <em>auth</em>, <em>onboarding</em>, <em>bridge</em>, <em>messages</em>, <em>user</em>, <em>system</em>. Expand any endpoint, click <strong>Try it out</strong>, fill in the JSON body, and click <strong>Execute</strong> to fire a real request.
  </div>
  <div class="callout warn">
    <strong>Cookies in Swagger:</strong> Login via <code>POST /api/auth/login</code> first. The browser will store the <span class="inline">nexa_session</span> cookie automatically and Swagger will include it in all subsequent requests.
  </div>

  <!-- ─── Auth model ─── -->
  <h2 id="auth-model">Auth model</h2>
  <p>After a successful login (email/password or OAuth), the server sets an <span class="inline">HttpOnly</span> cookie named <span class="inline">nexa_session</span> (TTL 24 h, configurable via <span class="inline">AUTH_SESSION_TTL_HOURS</span>). The cookie is automatically sent with every subsequent request — you never read or write it from JavaScript.</p>
  <div class="code-wrap">
    <div class="code-label">Every fetch call must include this option:</div>
    <pre><code>fetch('/api/...', {
  method: 'POST',
  credentials: 'include',          // ← sends nexa_session cookie
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(payload),
});</code></pre>
  </div>

  <!-- ─── Register / Login ─── -->
  <h2 id="register-login">Register &amp; Login</h2>

  <div class="endpoint">
    <span class="method POST">POST</span>
    <div class="endpoint-info">
      <div class="endpoint-path">/api/auth/register</div>
      <div class="endpoint-desc">Create a new account. Sets session cookie on success.</div>
    </div>
  </div>
  <div class="code-wrap">
    <div class="code-label">Request body</div>
    <pre><code>{ "name": "Jane Doe", "email": "jane@example.com", "password": "secret123" }</code></pre>
    <div class="code-label" style="margin-top:10px;">Response 200</div>
    <pre><code>{ "success": true, "user": { "id": 1, "name": "Jane Doe", "email": "jane@example.com" }, "message": "Account created" }</code></pre>
  </div>

  <div class="endpoint">
    <span class="method POST">POST</span>
    <div class="endpoint-info">
      <div class="endpoint-path">/api/auth/login</div>
      <div class="endpoint-desc">Authenticate with email and password. Sets session cookie on success.</div>
    </div>
  </div>
  <div class="code-wrap">
    <div class="code-label">Request body</div>
    <pre><code>{ "email": "jane@example.com", "password": "secret123" }</code></pre>
    <div class="code-label" style="margin-top:10px;">Response 200</div>
    <pre><code>{ "success": true, "user": { "id": 1, "name": "Jane Doe", "email": "jane@example.com" }, "message": "Logged in" }</code></pre>
  </div>

  <div class="endpoint">
    <span class="method GET">GET</span>
    <div class="endpoint-info">
      <div class="endpoint-path">/api/auth/me</div>
      <div class="endpoint-desc">Return the currently authenticated user (reads the session cookie). Use this on app load to check if the user is already signed in.</div>
    </div>
  </div>
  <div class="code-wrap">
    <div class="code-label">Response 200</div>
    <pre><code>{ "authenticated": true, "user": { "id": 1, "name": "Jane Doe", "email": "jane@example.com" } }</code></pre>
    <div class="code-label" style="margin-top:10px;">Response 401 (no/expired session)</div>
    <pre><code>{ "detail": "Not authenticated" }</code></pre>
  </div>
  <div class="code-wrap">
    <div class="code-label">JS example — check session on load</div>
    <pre><code>async function getMe() {
  const res = await fetch('/api/auth/me', { credentials: 'include' });
  if (res.ok) {
    const { user } = await res.json();
    return user; // signed in
  }
  return null;   // redirect to /login
}</code></pre>
  </div>

  <!-- ─── OAuth ─── -->
  <h2 id="oauth">OAuth — Sign in with Google / GitHub</h2>
  <p>OAuth is a browser redirect flow — there is no JSON body to send. Just navigate the user's browser to the start URL.</p>

  <div class="endpoint">
    <span class="method GET">GET</span>
    <div class="endpoint-info">
      <div class="endpoint-path">/api/auth/oauth/{provider}/start</div>
      <div class="endpoint-desc">Redirects to the provider consent screen. <code>provider</code> is <strong>google</strong> or <strong>github</strong>. Returns <strong>503</strong> if the provider's env vars are not configured.</div>
    </div>
  </div>
  <div class="code-wrap">
    <div class="code-label">Usage — simply navigate the browser</div>
    <pre><code>// Full page redirect (simplest)
window.location.href = '/api/auth/oauth/google/start';

// Or open in a popup (advanced)
const popup = window.open('/api/auth/oauth/google/start', 'oauth', 'width=500,height=600');
// After the popup closes, call /api/auth/me to check if login succeeded</code></pre>
  </div>
  <div class="callout info">
    After the user approves access, the provider redirects back to the sidecar's callback URL, the sidecar creates the session, and redirects the browser to <strong>/</strong> (the login page) with the cookie already set. Call <span class="inline">GET /api/auth/me</span> to confirm.
  </div>

  <!-- ─── Logout ─── -->
  <h2 id="logout">Logout</h2>

  <div class="endpoint">
    <span class="method POST">POST</span>
    <div class="endpoint-info">
      <div class="endpoint-path">/api/auth/logout</div>
      <div class="endpoint-desc">Delete the current session. Clears the cookie and removes the DB session token.</div>
    </div>
  </div>
  <div class="code-wrap">
    <div class="code-label">JS example</div>
    <pre><code>await fetch('/api/auth/logout', { method: 'POST', credentials: 'include' });
// Redirect to login
window.location.href = '/login';</code></pre>
  </div>

  <div class="endpoint">
    <span class="method POST">POST</span>
    <div class="endpoint-info">
      <div class="endpoint-path">/api/bridge/{platform}/logout</div>
      <div class="endpoint-desc">Disconnect the WhatsApp or LinkedIn bridge for the admin user. <code>platform</code> is <strong>whatsapp</strong> or <strong>linkedin</strong>.</div>
    </div>
  </div>
  <div class="code-wrap">
    <div class="code-label">JS example — disconnect WhatsApp</div>
    <pre><code>const res = await fetch('/api/bridge/whatsapp/logout', {
  method: 'POST',
  credentials: 'include',
});
const data = await res.json();
// { "status": "logged_out", "bridge_bot": "@whatsappbot:localhost" }</code></pre>
  </div>

  <!-- ─── WhatsApp onboarding ─── -->
  <h2 id="whatsapp-onboard">WhatsApp Onboarding — QR flow</h2>
  <p>This is the main user-facing setup flow. The typical sequence:</p>
  <div class="flow">
    <div class="flow-step"><span class="num">1</span> <code>POST /api/onboard/whatsapp/start</code> → returns <span class="inline">session_id</span> + first QR image</div>
    <div class="flow-arrow">↓</div>
    <div class="flow-step"><span class="num">2</span> Display the QR code as an <code>&lt;img src="data:image/png;base64,..."&gt;</code></div>
    <div class="flow-arrow">↓</div>
    <div class="flow-step"><span class="num">3</span> Poll <code>GET /api/onboard/whatsapp/status/{session_id}</code> every 3 s</div>
    <div class="flow-arrow">↓</div>
    <div class="flow-step"><span class="num">4</span> Refresh QR every 18 s via <code>GET /api/onboard/whatsapp/qr/{session_id}</code> (QR expires ~20 s)</div>
    <div class="flow-arrow">↓</div>
    <div class="flow-step"><span class="num">5</span> When status = <span class="pill pill-green">connected</span> → done. Call DELETE to clean up.</div>
  </div>

  <div class="endpoint">
    <span class="method POST">POST</span>
    <div class="endpoint-info">
      <div class="endpoint-path">/api/onboard/whatsapp/start</div>
      <div class="endpoint-desc">Begin onboarding. Creates a Matrix account for the user and returns the first QR code.</div>
    </div>
  </div>
  <div class="code-wrap">
    <div class="code-label">Request body</div>
    <pre><code>{ "user_id": "alice" }   // any string — your app's user identifier</code></pre>
    <div class="code-label" style="margin-top:10px;">Response 200</div>
    <pre><code>{
  "session_id": "abc123",
  "status": "pending_qr",
  "qr": "data:image/png;base64,iVBOR...",   // render as &lt;img src=...&gt;
  "matrix_user_id": "@nexa_alice:localhost"
}</code></pre>
  </div>

  <div class="endpoint">
    <span class="method GET">GET</span>
    <div class="endpoint-info">
      <div class="endpoint-path">/api/onboard/whatsapp/status/{session_id}</div>
      <div class="endpoint-desc">Poll connection status. Call every 3 s after showing the QR.</div>
    </div>
  </div>
  <div class="code-wrap">
    <div class="code-label">Possible status values</div>
    <pre><code><span class="pill pill-yellow">pending_qr</span>  — waiting for user to scan
<span class="pill pill-green">connected</span>   — WhatsApp authenticated ✓ stop polling
<span class="pill pill-red">expired</span>     — 5 min TTL exceeded, call /start again
<span class="pill pill-red">not_found</span>   — unknown session_id</code></pre>
  </div>

  <div class="endpoint">
    <span class="method GET">GET</span>
    <div class="endpoint-info">
      <div class="endpoint-path">/api/onboard/whatsapp/qr/{session_id}</div>
      <div class="endpoint-desc">Fetch the latest QR code. QR codes expire after ~20 s — refresh every 18 s.</div>
    </div>
  </div>

  <div class="endpoint">
    <span class="method DELETE">DELETE</span>
    <div class="endpoint-info">
      <div class="endpoint-path">/api/onboard/whatsapp/session/{session_id}</div>
      <div class="endpoint-desc">Clean up an onboarding session. Call after connected confirmation or user cancels.</div>
    </div>
  </div>

  <div class="code-wrap">
    <div class="code-label">JS — complete onboarding flow</div>
    <pre><code>async function onboardWhatsApp(userId) {
  // 1. Start session
  const start = await fetch('/api/onboard/whatsapp/start', {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_id: userId }),
  }).then(r => r.json());

  const { session_id, qr } = start;
  document.getElementById('qr-img').src = qr;  // show QR

  // 2. Refresh QR every 18 s
  const qrTimer = setInterval(async () => {
    const { qr: newQr } = await fetch(
      `/api/onboard/whatsapp/qr/${session_id}`,
      { credentials: 'include' }
    ).then(r => r.json());
    if (newQr) document.getElementById('qr-img').src = newQr;
  }, 18_000);

  // 3. Poll status every 3 s
  return new Promise((resolve, reject) => {
    const poll = setInterval(async () => {
      const { status } = await fetch(
        `/api/onboard/whatsapp/status/${session_id}`,
        { credentials: 'include' }
      ).then(r => r.json());

      if (status === 'connected') {
        clearInterval(poll);
        clearInterval(qrTimer);
        await fetch(`/api/onboard/whatsapp/session/${session_id}`, {
          method: 'DELETE', credentials: 'include',
        });
        resolve('connected');
      } else if (status === 'expired' || status === 'not_found') {
        clearInterval(poll);
        clearInterval(qrTimer);
        reject(new Error(`Onboarding failed: ${status}`));
      }
    }, 3_000);
  });
}</code></pre>
  </div>

  <!-- ─── Bridge ─── -->
  <h2 id="bridge">Bridge Management</h2>
  <p>These endpoints manage the admin user's WhatsApp / LinkedIn connection at the Matrix bridge level (separate from per-user onboarding above).</p>

  <div class="endpoint">
    <span class="method GET">GET</span>
    <div class="endpoint-info">
      <div class="endpoint-path">/api/bridge/{platform}/status</div>
      <div class="endpoint-desc">Check if the bridge is connected. <code>platform</code>: <strong>whatsapp</strong> or <strong>linkedin</strong>.</div>
    </div>
  </div>
  <div class="code-wrap">
    <div class="code-label">Response</div>
    <pre><code>{ "status": "connected", "room_id": "!abc:localhost", "bridge_bot": "@whatsappbot:localhost" }</code></pre>
  </div>

  <div class="endpoint">
    <span class="method POST">POST</span>
    <div class="endpoint-info">
      <div class="endpoint-path">/api/bridge/{platform}/login</div>
      <div class="endpoint-desc">Initiate bridge login. For WhatsApp, returns a QR code. For LinkedIn, the bot sends cookie-paste instructions via DM.</div>
    </div>
  </div>
  <div class="code-wrap">
    <div class="code-label">Request body</div>
    <pre><code>{ "platform": "whatsapp" }</code></pre>
  </div>

  <div class="endpoint">
    <span class="method POST">POST</span>
    <div class="endpoint-info">
      <div class="endpoint-path">/api/bridge/{platform}/logout</div>
      <div class="endpoint-desc">Disconnect the bridge. Sends <code>logout</code> to the bridge bot.</div>
    </div>
  </div>

  <!-- ─── Messages ─── -->
  <h2 id="messages">Messages</h2>

  <div class="endpoint">
    <span class="method GET">GET</span>
    <div class="endpoint-info">
      <div class="endpoint-path">/api/messages/recent?limit=20</div>
      <div class="endpoint-desc">Retrieve the most recent classified messages. Default limit: 20, max: any integer.</div>
    </div>
  </div>
  <div class="code-wrap">
    <div class="code-label">Response</div>
    <pre><code>{
  "messages": [
    {
      "id": "msg_001",
      "platform": "whatsapp",
      "sender": "@user_alice:localhost",
      "content": "When is the meeting?",
      "timestamp": 1712345678000,
      "classification": "ENQUIRY",
      "classifier_used": "ollama",
      "confidence": 0.92
    }
  ],
  "count": 1
}</code></pre>
  </div>

  <div class="endpoint">
    <span class="method POST">POST</span>
    <div class="endpoint-info">
      <div class="endpoint-path">/api/messages/classify</div>
      <div class="endpoint-desc">Manually submit a message for classification and action decision. Idempotent — duplicate IDs are ignored.</div>
    </div>
  </div>
  <div class="code-wrap">
    <div class="code-label">Request body</div>
    <pre><code>{
  "id": "unique-msg-id",
  "platform": "whatsapp",
  "sender": "@alice:localhost",
  "content": "Can I schedule a call?",
  "timestamp": 1712345678000,
  "room_id": "!room:localhost"
}</code></pre>
    <div class="code-label" style="margin-top:10px;">Response 200</div>
    <pre><code>{
  "message_id": "unique-msg-id",
  "action_id": 42,
  "action_type": "NOTIFY",
  "priority": "HIGH",
  "classification": { "category": "INTENT", "confidence": 0.95, "classifier_used": "ollama" },
  "status": "success",
  "user_status": "available"
}</code></pre>
  </div>

  <!-- ─── User status ─── -->
  <h2 id="user-status">User Status &amp; Pending Actions</h2>

  <div class="endpoint">
    <span class="method POST">POST</span>
    <div class="endpoint-info">
      <div class="endpoint-path">/api/user/status</div>
      <div class="endpoint-desc">Set user availability. Affects how the AI decides to escalate or suppress messages.</div>
    </div>
  </div>
  <div class="code-wrap">
    <div class="code-label">Request body</div>
    <pre><code>{ "user_id": "alice", "status": "busy", "auto_reply_message": "I'm in a meeting, back in 1 hr." }</code></pre>
    <div class="code-label" style="margin-top:10px;">Allowed status values</div>
    <pre><code>"available"  — normal operation
"busy"       — auto-reply may trigger
"dnd"        — do not disturb</code></pre>
  </div>

  <div class="endpoint">
    <span class="method GET">GET</span>
    <div class="endpoint-info">
      <div class="endpoint-path">/api/user/status?user_id=alice</div>
      <div class="endpoint-desc">Get current user availability. Defaults to <code>user_id=default_user</code>.</div>
    </div>
  </div>

  <div class="endpoint">
    <span class="method GET">GET</span>
    <div class="endpoint-info">
      <div class="endpoint-path">/api/actions/pending?limit=50</div>
      <div class="endpoint-desc">List actions waiting to be executed (NOTIFY, ESCALATE, etc.).</div>
    </div>
  </div>

  <!-- ─── System ─── -->
  <h2 id="system">Health &amp; Statistics</h2>

  <div class="endpoint">
    <span class="method GET">GET</span>
    <div class="endpoint-info">
      <div class="endpoint-path">/health</div>
      <div class="endpoint-desc">Liveness check. Returns 200 when the service is running.</div>
    </div>
  </div>
  <div class="code-wrap">
    <div class="code-label">Response</div>
    <pre><code>{
  "status": "ok",
  "service": "nexa-sidecar",
  "ollama_available": true,
  "ollama_model": "llama3.2:1b",
  "hf_available": false,
  "db_path": "/data/nexa.db"
}</code></pre>
  </div>

  <div class="endpoint">
    <span class="method GET">GET</span>
    <div class="endpoint-info">
      <div class="endpoint-path">/api/stats</div>
      <div class="endpoint-desc">Message and action counts, classifier breakdown.</div>
    </div>
  </div>
  <div class="code-wrap">
    <div class="code-label">Response</div>
    <pre><code>{
  "total_messages": 142,
  "pending_actions": 3,
  "priority_breakdown": { "HIGH": 41, "MEDIUM": 67, "LOW": 34 },
  "classifier_breakdown": { "ollama": 139, "rule-based": 3 },
  "ollama_enabled": true,
  "classifier": "ollama"
}</code></pre>
  </div>

  <!-- ─── Errors ─── -->
  <h2 id="errors">Error Handling</h2>
  <p>All errors follow FastAPI's standard format:</p>
  <div class="code-wrap">
    <pre><code>{ "detail": "Human-readable error message" }</code></pre>
  </div>

  <table style="width:100%; border-collapse:collapse; font-size:13px; margin-bottom:20px;">
    <thead>
      <tr style="background:var(--surface); color:var(--muted);">
        <th style="padding:8px 12px; text-align:left; border:1px solid var(--border);">Status</th>
        <th style="padding:8px 12px; text-align:left; border:1px solid var(--border);">Meaning</th>
        <th style="padding:8px 12px; text-align:left; border:1px solid var(--border);">Common cause</th>
      </tr>
    </thead>
    <tbody>
      <tr><td style="padding:8px 12px; border:1px solid var(--border);">400</td><td style="padding:8px 12px; border:1px solid var(--border);">Bad request</td><td style="padding:8px 12px; border:1px solid var(--border);">Invalid payload, expired OAuth state</td></tr>
      <tr><td style="padding:8px 12px; border:1px solid var(--border);">401</td><td style="padding:8px 12px; border:1px solid var(--border);">Unauthenticated</td><td style="padding:8px 12px; border:1px solid var(--border);">Missing or expired session cookie</td></tr>
      <tr><td style="padding:8px 12px; border:1px solid var(--border);">404</td><td style="padding:8px 12px; border:1px solid var(--border);">Not found</td><td style="padding:8px 12px; border:1px solid var(--border);">Unknown session_id or provider name</td></tr>
      <tr><td style="padding:8px 12px; border:1px solid var(--border);">409</td><td style="padding:8px 12px; border:1px solid var(--border);">Conflict</td><td style="padding:8px 12px; border:1px solid var(--border);">Email already registered</td></tr>
      <tr><td style="padding:8px 12px; border:1px solid var(--border);">422</td><td style="padding:8px 12px; border:1px solid var(--border);">Validation error</td><td style="padding:8px 12px; border:1px solid var(--border);">Missing required fields (FastAPI auto-generated)</td></tr>
      <tr><td style="padding:8px 12px; border:1px solid var(--border);">502</td><td style="padding:8px 12px; border:1px solid var(--border);">Bridge error</td><td style="padding:8px 12px; border:1px solid var(--border);">Matrix bridge or OAuth provider unreachable</td></tr>
      <tr><td style="padding:8px 12px; border:1px solid var(--border);">503</td><td style="padding:8px 12px; border:1px solid var(--border);">Not configured</td><td style="padding:8px 12px; border:1px solid var(--border);">OAuth env vars missing</td></tr>
    </tbody>
  </table>

  <div class="code-wrap">
    <div class="code-label">JS — recommended error handler wrapper</div>
    <pre><code>async function api(path, options = {}) {
  const res = await fetch(path, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw Object.assign(new Error(err.detail), { status: res.status });
  }
  return res.json();
}

// Usage
try {
  const user = await api('/api/auth/me');
} catch (e) {
  if (e.status === 401) router.push('/login');
  else console.error(e.message);
}</code></pre>
  </div>

  <!-- ─── Full client ─── -->
  <h2 id="full-client">Full JavaScript Client (copy-paste)</h2>
  <p>Drop this into your project as <span class="inline">nexa.js</span> and import it anywhere.</p>
  <div class="code-wrap">
    <pre><code>// nexa.js — Nexa sidecar API client
const BASE = 'http://localhost:8080';

async function _req(path, options = {}) {
  const res = await fetch(BASE + path, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw Object.assign(new Error(err.detail), { status: res.status });
  }
  return res.json();
}

export const nexa = {
  // Auth
  register: (name, email, password) =>
    _req('/api/auth/register', { method: 'POST', body: JSON.stringify({ name, email, password }) }),
  login: (email, password) =>
    _req('/api/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) }),
  me: () => _req('/api/auth/me'),
  logout: () => _req('/api/auth/logout', { method: 'POST' }),
  oauthStart: (provider) => { window.location.href = `${BASE}/api/auth/oauth/${provider}/start`; },

  // WhatsApp onboarding
  onboardStart: (userId) =>
    _req('/api/onboard/whatsapp/start', { method: 'POST', body: JSON.stringify({ user_id: userId }) }),
  onboardStatus: (sessionId) => _req(`/api/onboard/whatsapp/status/${sessionId}`),
  onboardQr:     (sessionId) => _req(`/api/onboard/whatsapp/qr/${sessionId}`),
  onboardCancel: (sessionId) => _req(`/api/onboard/whatsapp/session/${sessionId}`, { method: 'DELETE' }),

  // Bridge
  bridgeStatus: (platform) => _req(`/api/bridge/${platform}/status`),
  bridgeLogin:  (platform) =>
    _req(`/api/bridge/${platform}/login`, { method: 'POST', body: JSON.stringify({ platform }) }),
  bridgeLogout: (platform) => _req(`/api/bridge/${platform}/logout`, { method: 'POST' }),

  // Messages
  recentMessages: (limit = 20) => _req(`/api/messages/recent?limit=${limit}`),
  classify: (msg) =>
    _req('/api/messages/classify', { method: 'POST', body: JSON.stringify(msg) }),

  // User
  setStatus: (userId, status, autoReply) =>
    _req('/api/user/status', { method: 'POST',
      body: JSON.stringify({ user_id: userId, status, auto_reply_message: autoReply }) }),
  getStatus: (userId = 'default_user') => _req(`/api/user/status?user_id=${userId}`),
  pendingActions: (limit = 50) => _req(`/api/actions/pending?limit=${limit}`),

  // System
  health: () => _req('/health'),
  stats:  () => _req('/api/stats'),
};
</code></pre>
  </div>

  <div style="margin-top:48px; padding-top:24px; border-top:1px solid var(--border); color:var(--muted); font-size:13px;">
    Nexa Sidecar v1.0 &nbsp;·&nbsp; <a href="/docs">Swagger UI</a> &nbsp;·&nbsp; <a href="/redoc">ReDoc</a>
  </div>
</main>

<script>
  // Highlight active nav link based on scroll position
  const sections = document.querySelectorAll('h2[id]');
  const links = document.querySelectorAll('nav a');
  const obs = new IntersectionObserver(entries => {
    entries.forEach(e => {
      if (e.isIntersecting) {
        links.forEach(l => l.classList.remove('active'));
        const a = document.querySelector(`nav a[href="#${e.target.id}"]`);
        if (a) a.classList.add('active');
      }
    });
  }, { rootMargin: '-20% 0px -70% 0px' });
  sections.forEach(s => obs.observe(s));
</script>
</body>
</html>"""
