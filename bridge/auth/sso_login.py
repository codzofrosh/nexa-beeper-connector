"""
SSO login for Beeper accounts created via Google or Apple sign-in.

Usage
-----
    python bridge/auth/sso_login.py

Flow
----
1. Starts a one-shot HTTP server on localhost:8123
2. Opens your browser to the Beeper SSO login page
3. You click "Continue with Google" (or Apple)
4. Beeper redirects back to localhost:8123/callback with a loginToken
5. We exchange that loginToken for a Matrix access_token
6. Token is written to MATRIX_ACCESS_TOKEN in .env automatically
7. Run  python bridge/auth/whatsapp_login.py  to authenticate WhatsApp

Environment variables (read from .env)
---------------------------------------
    MATRIX_HOMESERVER   = https://matrix.beeper.com
    MATRIX_USER         = @you:beeper.com
    SSO_CALLBACK_PORT   = 8123   (optional, default 8123)
"""

from __future__ import annotations

import asyncio
import os
import re
import sys
import webbrowser
from pathlib import Path
from urllib.parse import quote, urlencode

import aiohttp
from aiohttp import web

_repo_root = Path(__file__).resolve().parents[2]
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from dotenv import load_dotenv
load_dotenv(_repo_root / ".env")


def _get_sso_url(homeserver: str, callback_url: str) -> str:
    return (
        f"{homeserver.rstrip('/')}/_matrix/client/v3/login/sso/redirect"
        f"?redirectUrl={quote(callback_url, safe='')}"
    )


async def _exchange_login_token(homeserver: str, login_token: str) -> dict:
    """Exchange a Matrix loginToken for a full access_token."""
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{homeserver.rstrip('/')}/_matrix/client/v3/login",
            json={"type": "m.login.token", "token": login_token},
        ) as resp:
            data = await resp.json()
            if resp.status != 200:
                error = data.get("error", str(data))
                raise RuntimeError(f"Token exchange failed ({resp.status}): {error}")
            return data   # contains access_token, user_id, device_id, ...


def _update_env(env_path: Path, access_token: str) -> None:
    """Write the new token to .env, replacing the existing line if present."""
    text = env_path.read_text(encoding="utf-8")
    line = f"MATRIX_ACCESS_TOKEN={access_token}"
    new_text, n = re.subn(
        r"^MATRIX_ACCESS_TOKEN\s*=.*$", line, text, flags=re.MULTILINE
    )
    if n == 0:
        new_text = text.rstrip("\n") + f"\n{line}\n"
    env_path.write_text(new_text, encoding="utf-8")


async def run() -> None:
    homeserver = os.getenv("MATRIX_HOMESERVER", "https://matrix.beeper.com").strip()
    port = int(os.getenv("SSO_CALLBACK_PORT", "8123"))
    callback_url = f"http://localhost:{port}/callback"

    print()
    print("╔══════════════════════════════════════════════════╗")
    print("║         Nexa — Beeper SSO Login                  ║")
    print("╚══════════════════════════════════════════════════╝")
    print(f"  Homeserver   : {homeserver}")
    print(f"  Callback URL : {callback_url}")
    print()

    # ── state shared between the aiohttp callback handler and the main task ──
    login_token: dict[str, str | None] = {"value": None}
    done = asyncio.Event()

    # ── one-shot aiohttp server ───────────────────────────────────────────────
    async def handle_callback(request: web.Request) -> web.Response:
        token = request.query.get("loginToken")
        if not token:
            return web.Response(
                status=400,
                content_type="text/html",
                text="<h2>Error: no loginToken in callback URL.</h2>",
            )
        login_token["value"] = token
        done.set()
        return web.Response(
            content_type="text/html",
            text=(
                "<html><body style='font-family:sans-serif;padding:40px'>"
                "<h2>✅ Login received!</h2>"
                "<p>You can close this tab and return to the terminal.</p>"
                "</body></html>"
            ),
        )

    app_server = web.Application()
    app_server.router.add_get("/callback", handle_callback)
    runner = web.AppRunner(app_server)
    await runner.setup()
    site = web.TCPSite(runner, "localhost", port)
    await site.start()

    # ── open browser ──────────────────────────────────────────────────────────
    sso_url = _get_sso_url(homeserver, callback_url)
    print("🌐  Opening browser for Beeper SSO login...")
    print(f"    If the browser doesn't open, visit:\n    {sso_url}\n")
    webbrowser.open(sso_url)

    # ── wait for callback (2-minute window) ───────────────────────────────────
    try:
        await asyncio.wait_for(done.wait(), timeout=120)
    except asyncio.TimeoutError:
        print("❌  Timed out waiting for SSO callback (2 minutes).")
        print("    Make sure you completed the login in the browser.")
        await runner.cleanup()
        return
    finally:
        await runner.cleanup()

    token_val = login_token["value"]
    if not token_val:
        print("❌  No login token received.")
        return

    # ── exchange loginToken → access_token ───────────────────────────────────
    print("⏳  Exchanging login token for access token...")
    try:
        result = await _exchange_login_token(homeserver, token_val)
    except RuntimeError as exc:
        print(f"❌  {exc}")
        return

    access_token = result.get("access_token", "")
    user_id      = result.get("user_id", "")
    device_id    = result.get("device_id", "")

    if not access_token:
        print(f"❌  Server response missing access_token: {result}")
        return

    # ── write to .env ─────────────────────────────────────────────────────────
    env_path = _repo_root / ".env"
    _update_env(env_path, access_token)

    masked = access_token[:10] + "..." + access_token[-6:]
    print()
    print(f"✅  Logged in as : {user_id}")
    print(f"✅  Device ID    : {device_id}")
    print(f"✅  Token        : {masked}")
    print(f"✅  Written to   : {env_path}")
    print()
    print("  Next step → python bridge/auth/whatsapp_login.py")


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
