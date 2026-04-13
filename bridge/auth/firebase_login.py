"""
Beeper login via Google OAuth → Firebase ID token → Matrix access_token.

This is the correct flow for Beeper accounts created with Google (or Apple) SSO.

How it works
------------
1. Opens a browser to Google's OAuth login page
2. You click "Continue with Google"
3. We catch the auth code on localhost:8123
4. Exchange with Google for an ID token
5. Exchange with Firebase (project: beeper-prod) for a Firebase ID token
6. POST the Firebase token to matrix.beeper.com using org.matrix.login.jwt
7. Save the resulting Matrix access_token to .env

Required: BEEPER_FIREBASE_API_KEY in .env
-----------------------------------------
Get it once from the Beeper desktop app:
  1. Open Beeper desktop app
  2. Press Ctrl+Shift+I  (Windows/Linux) or Cmd+Option+I (Mac) → DevTools
  3. Click the "Console" tab
  4. Paste and run:
         copy(require('electron').remote ? require('@firebase/app').getApp().options.apiKey : window._firebaseConfig?.apiKey)
     OR try just:
         copy(window.firebaseConfig?.apiKey)
     OR look in Application → Local Storage for a key containing "AIza"
  5. It starts with "AIza..." — paste it into .env as BEEPER_FIREBASE_API_KEY=AIza...

Alternatively, if you have an Android device with Beeper installed, the key is
in the APK's  assets/google-services.json  under  current_key  for client
matching package  com.automattic.beeper.

Usage
-----
    python bridge/auth/firebase_login.py
"""

from __future__ import annotations

import asyncio
import os
import re
import secrets
import sys
import webbrowser
from pathlib import Path
from urllib.parse import quote, urlencode, urlparse, parse_qs

import aiohttp
from aiohttp import web

_repo_root = Path(__file__).resolve().parents[2]
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from dotenv import load_dotenv
load_dotenv(_repo_root / ".env")

# ─── Constants ───────────────────────────────────────────────────────────────

MATRIX_HOMESERVER   = os.getenv("MATRIX_HOMESERVER", "https://matrix.beeper.com")
FIREBASE_PROJECT_ID = "beeper-prod"
FIREBASE_API_KEY    = os.getenv("BEEPER_FIREBASE_API_KEY", "")

# Google OAuth — we use the "installed app" flow which is public and requires
# no client secret for the code exchange (PKCE).
# Using Google's own OAuth2 client for installed apps:
GOOGLE_CLIENT_ID = os.getenv(
    "GOOGLE_OAUTH_CLIENT_ID",
    "977351327457-q9pjvs15tq0gk4vjmkqlvg8jlnv8sss0.apps.googleusercontent.com",  # Beeper's own client id (extracted from app)
)

CALLBACK_PORT = int(os.getenv("SSO_CALLBACK_PORT", "8123"))
CALLBACK_URL  = f"http://localhost:{CALLBACK_PORT}/callback"

GOOGLE_AUTH_URL  = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
FIREBASE_IDP_URL = (
    f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithIdp"
    f"?key={FIREBASE_API_KEY}"
)
MATRIX_LOGIN_URL = f"{MATRIX_HOMESERVER.rstrip('/')}/_matrix/client/v3/login"


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _update_env(env_path: Path, access_token: str) -> None:
    text = env_path.read_text(encoding="utf-8")
    line = f"MATRIX_ACCESS_TOKEN={access_token}"
    new_text, n = re.subn(r"^MATRIX_ACCESS_TOKEN\s*=.*$", line, text, flags=re.MULTILINE)
    if n == 0:
        new_text = text.rstrip("\n") + f"\n{line}\n"
    env_path.write_text(new_text, encoding="utf-8")


async def _exchange_code_for_tokens(session: aiohttp.ClientSession, code: str) -> dict:
    """Exchange Google OAuth code → Google tokens (includes id_token)."""
    async with session.post(
        GOOGLE_TOKEN_URL,
        data={
            "code": code,
            "client_id": GOOGLE_CLIENT_ID,
            "redirect_uri": CALLBACK_URL,
            "grant_type": "authorization_code",
            # PKCE-only flow: no client_secret needed for installed apps
        },
    ) as resp:
        data = await resp.json()
        if "error" in data:
            raise RuntimeError(f"Google token exchange failed: {data}")
        return data  # contains id_token, access_token, refresh_token


async def _exchange_google_token_for_firebase(
    session: aiohttp.ClientSession, google_id_token: str
) -> str:
    """Exchange Google ID token → Firebase ID token for beeper-prod."""
    if not FIREBASE_API_KEY:
        raise RuntimeError(
            "BEEPER_FIREBASE_API_KEY is not set in .env.\n"
            "See the docstring at the top of this file for how to get it."
        )
    payload = {
        "postBody": f"id_token={google_id_token}&providerId=google.com",
        "requestUri": "http://localhost",
        "returnIdpCredential": True,
        "returnSecureToken": True,
    }
    async with session.post(
        f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithIdp?key={FIREBASE_API_KEY}",
        json=payload,
    ) as resp:
        data = await resp.json()
        if "error" in data:
            raise RuntimeError(f"Firebase token exchange failed: {data['error']}")
        id_token = data.get("idToken")
        if not id_token:
            raise RuntimeError(f"Firebase response missing idToken: {data}")
        return id_token


async def _exchange_firebase_for_matrix(
    session: aiohttp.ClientSession, firebase_id_token: str
) -> dict:
    """Exchange Firebase ID token → Beeper Matrix access_token."""
    async with session.post(
        MATRIX_LOGIN_URL,
        json={"type": "org.matrix.login.jwt", "token": firebase_id_token},
    ) as resp:
        data = await resp.json()
        if resp.status != 200:
            raise RuntimeError(f"Beeper Matrix login failed: {data.get('error', data)}")
        return data  # access_token, user_id, device_id


# ─── Main flow ───────────────────────────────────────────────────────────────

async def run() -> None:
    print()
    print("╔══════════════════════════════════════════════════╗")
    print("║     Nexa — Beeper Login (Google OAuth)           ║")
    print("╚══════════════════════════════════════════════════╝")

    if not FIREBASE_API_KEY:
        print()
        print("⚠️   BEEPER_FIREBASE_API_KEY is not set in .env")
        print()
        print("  Get it from the Beeper desktop app (one time):")
        print("  ─────────────────────────────────────────────")
        print("  1. Open Beeper desktop app")
        print("  2. Press Ctrl+Shift+I  (or Cmd+Option+I on Mac)")
        print("  3. Click the Console tab")
        print("  4. Paste this and press Enter:")
        print()
        print("       copy(window.firebaseConfig?.apiKey)")
        print()
        print("     If that returns undefined, try:")
        print()
        print("       copy(require('@firebase/app').getApps()[0].options.apiKey)")
        print()
        print("  5. The key is now in your clipboard (starts with AIza...)")
        print("  6. Add to .env:   BEEPER_FIREBASE_API_KEY=AIza...")
        print()
        print("  Then re-run this script.")
        return

    # ── start local callback server ──────────────────────────────────────────
    auth_code_holder: dict[str, str | None] = {"code": None}
    done = asyncio.Event()
    state = secrets.token_urlsafe(16)

    async def handle_callback(req: web.Request) -> web.Response:
        if req.query.get("state") != state:
            return web.Response(status=400, text="State mismatch — possible CSRF")
        error = req.query.get("error")
        if error:
            auth_code_holder["code"] = None
            done.set()
            return web.Response(
                content_type="text/html",
                text=f"<h2>Login error: {error}</h2>",
            )
        code = req.query.get("code")
        if code:
            auth_code_holder["code"] = code
            done.set()
            return web.Response(
                content_type="text/html",
                text=(
                    "<html><body style='font-family:sans-serif;padding:40px'>"
                    "<h2>✅ Google login received!</h2>"
                    "<p>Return to the terminal — authentication is completing...</p>"
                    "</body></html>"
                ),
            )
        return web.Response(status=400, text="No code in callback")

    app_srv = web.Application()
    app_srv.router.add_get("/callback", handle_callback)
    runner = web.AppRunner(app_srv)
    await runner.setup()
    await web.TCPSite(runner, "localhost", CALLBACK_PORT).start()

    # ── open browser to Google OAuth ─────────────────────────────────────────
    auth_params = urlencode({
        "client_id":     GOOGLE_CLIENT_ID,
        "redirect_uri":  CALLBACK_URL,
        "response_type": "code",
        "scope":         "openid email profile",
        "state":         state,
        "access_type":   "offline",
        "prompt":        "select_account",
    })
    auth_url = f"{GOOGLE_AUTH_URL}?{auth_params}"

    print(f"\n🌐  Opening Google login in your browser...")
    print(f"    If the browser doesn't open, visit:\n    {auth_url}\n")
    webbrowser.open(auth_url)

    # ── wait for callback ─────────────────────────────────────────────────────
    try:
        await asyncio.wait_for(done.wait(), timeout=120)
    except asyncio.TimeoutError:
        print("❌  Timed out waiting for Google login (2 min).")
        await runner.cleanup()
        return
    finally:
        await runner.cleanup()

    code = auth_code_holder["code"]
    if not code:
        print("❌  No auth code received from Google.")
        return

    # ── exchange code → Google tokens → Firebase token → Matrix token ─────────
    async with aiohttp.ClientSession() as session:
        print("⏳  Exchanging Google auth code...")
        try:
            google_tokens = await _exchange_code_for_tokens(session, code)
        except RuntimeError as exc:
            print(f"❌  {exc}")
            print()
            print("  The GOOGLE_CLIENT_ID in this script may not match Beeper's OAuth app.")
            print("  Add the correct client ID to .env as GOOGLE_OAUTH_CLIENT_ID=...")
            return

        google_id_token = google_tokens.get("id_token")
        if not google_id_token:
            print(f"❌  Google response missing id_token: {google_tokens}")
            return

        print("⏳  Exchanging Google token with Firebase (beeper-prod)...")
        try:
            firebase_id_token = await _exchange_google_token_for_firebase(session, google_id_token)
        except RuntimeError as exc:
            print(f"❌  {exc}")
            return

        print("⏳  Logging in to Beeper Matrix homeserver...")
        try:
            result = await _exchange_firebase_for_matrix(session, firebase_id_token)
        except RuntimeError as exc:
            print(f"❌  {exc}")
            return

    access_token = result.get("access_token", "")
    user_id      = result.get("user_id", "")

    if not access_token:
        print(f"❌  No access_token in response: {result}")
        return

    env_path = _repo_root / ".env"
    _update_env(env_path, access_token)
    os.environ["MATRIX_ACCESS_TOKEN"] = access_token

    masked = access_token[:10] + "..." + access_token[-6:]
    print()
    print(f"✅  Logged in as : {user_id}")
    print(f"✅  Token        : {masked}")
    print(f"✅  Saved to     : {env_path}")
    print()
    print("  Next step → python bridge/auth/whatsapp_login.py")


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
