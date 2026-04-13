"""
Fetch a fresh Matrix access token and update .env automatically.

Usage
-----
    python bridge/auth/get_token.py

What it does
------------
Logs in to the Matrix homeserver with your username + password and writes
the new access_token back to MATRIX_ACCESS_TOKEN in .env.

Beeper note
-----------
Beeper accounts use standard Matrix password login. If your Beeper account
was created via Google/Apple SSO (no password), use Option 1 or 2 instead:

  Option 1 — Beeper desktop app:
    Settings → scroll to "Access token" → Copy

  Option 2 — Element web (https://app.element.io):
    Log in → Settings → Help & About → Access Token → Click to reveal → Copy

Then paste the token into .env:
    MATRIX_ACCESS_TOKEN=syt_...
"""

from __future__ import annotations

import asyncio
import getpass
import os
import re
import sys
from pathlib import Path

_repo_root = Path(__file__).resolve().parents[2]
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from dotenv import load_dotenv
load_dotenv(_repo_root / ".env")

from nio import AsyncClient, LoginResponse, LoginError


async def fetch_token(homeserver: str, user_id: str, password: str) -> str:
    """Login and return the access token."""
    client = AsyncClient(homeserver, user_id)
    try:
        resp = await client.login(password, device_name="nexa-bot")
        if isinstance(resp, LoginError):
            raise RuntimeError(f"Login failed: {resp.message} ({resp.status_code})")
        if not isinstance(resp, LoginResponse):
            raise RuntimeError(f"Unexpected login response: {resp}")
        return resp.access_token
    finally:
        await client.close()


def _update_env_file(env_path: Path, new_token: str) -> None:
    """Replace the MATRIX_ACCESS_TOKEN line in .env in-place."""
    text = env_path.read_text(encoding="utf-8")
    pattern = r"^(MATRIX_ACCESS_TOKEN\s*=\s*).*$"
    replacement = f"MATRIX_ACCESS_TOKEN={new_token}"
    new_text, count = re.subn(pattern, replacement, text, flags=re.MULTILINE)
    if count == 0:
        # Line didn't exist — append it
        new_text = text.rstrip("\n") + f"\nMATRIX_ACCESS_TOKEN={new_token}\n"
    env_path.write_text(new_text, encoding="utf-8")


async def run() -> None:
    homeserver = os.getenv("MATRIX_HOMESERVER", "https://matrix.beeper.com").strip()
    user_id    = os.getenv("MATRIX_USER", "").strip()

    print()
    print("╔══════════════════════════════════════════════════╗")
    print("║         Nexa — Refresh Matrix Access Token       ║")
    print("╚══════════════════════════════════════════════════╝")
    print(f"  Homeserver : {homeserver}")

    if not user_id:
        user_id = input("  Matrix user ID (@you:beeper.com): ").strip()
    else:
        print(f"  User       : {user_id}")

    print()
    password = getpass.getpass("  Password (input hidden): ")

    print()
    print("⏳  Logging in...")

    try:
        token = await fetch_token(homeserver, user_id, password)
    except RuntimeError as exc:
        print(f"❌  {exc}")
        print()
        print("  If your account uses Google/Apple SSO (no password), get the token manually:")
        print("  • Beeper app: Settings → Access token → Copy")
        print("  • Element:    Settings → Help & About → Access Token")
        return

    env_path = _repo_root / ".env"
    _update_env_file(env_path, token)

    # Show only first/last 6 chars for safety
    masked = token[:10] + "..." + token[-6:]
    print(f"✅  New token : {masked}")
    print(f"✅  Written to: {env_path}")
    print()
    print("  Now re-run:  python bridge/auth/whatsapp_login.py")


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
