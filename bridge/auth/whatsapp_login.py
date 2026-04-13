"""
Standalone CLI tool for authenticating the mautrix-whatsapp bridge.

Usage
-----
    python -m bridge.auth.whatsapp_login
    # or
    python bridge/auth/whatsapp_login.py

What it does
------------
1. Reads your Matrix credentials from .env
2. DMs the WhatsApp bridge bot (@whatsappbot:beeper.com by default)
3. Sends the "login" command
4. Waits for the bridge bot to send a QR code
5. Displays the QR code in the terminal (or saves as PNG)
6. Waits for you to scan with WhatsApp on your phone
7. Confirms when authenticated

Environment variables read from .env
-------------------------------------
    MATRIX_HOMESERVER      = https://matrix.beeper.com
    MATRIX_USER            = @you:beeper.com
    MATRIX_ACCESS_TOKEN    = syt_...
    WHATSAPP_BRIDGE_BOT    = @whatsappbot:beeper.com   (optional, has default)
"""

import asyncio
import base64
import logging
import os
import sys
from pathlib import Path

# Allow running as both `python bridge/auth/whatsapp_login.py`
# and `python -m bridge.auth.whatsapp_login`
_repo_root = Path(__file__).resolve().parents[2]
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from dotenv import load_dotenv
load_dotenv(_repo_root / ".env")

from bridge.auth.manager import BridgeAuthManager, BEEPER_BRIDGE_BOTS

logging.basicConfig(
    level=logging.WARNING,   # suppress nio noise; we use print() for user output
    format="%(levelname)s | %(name)s | %(message)s",
)
log = logging.getLogger("whatsapp_login")


# ──────────────────────────────────────────────────────────────────────────────
# QR code rendering helpers
# ──────────────────────────────────────────────────────────────────────────────

def _render_qr_terminal(qr_data: str) -> None:
    """Print the QR code to the terminal."""
    if qr_data.startswith("data:image"):
        # Base64 PNG — try to decode and re-render as ASCII in the terminal
        b64_part = qr_data.split(",", 1)[1]
        img_bytes = base64.b64decode(b64_part)

        # Try qrcode + Pillow for ASCII render
        try:
            from PIL import Image
            import io, sys

            img = Image.open(io.BytesIO(img_bytes)).convert("1")  # 1-bit b/w
            w, h = img.size

            print("\n" + "─" * (w + 4))
            # Print every other row (2:1 aspect ratio correction)
            for y in range(0, h, 2):
                row = "  "
                for x in range(w):
                    pixel = img.getpixel((x, y))
                    row += "█" if pixel == 0 else " "
                print(row)
            print("─" * (w + 4) + "\n")
            return
        except ImportError:
            pass

        # Pillow not available — save PNG to disk instead
        qr_path = _repo_root / "data" / "qr_code.png"
        qr_path.parent.mkdir(parents=True, exist_ok=True)
        qr_path.write_bytes(img_bytes)
        print(f"\n📁 QR code saved to: {qr_path}")
        print("   Open it and scan with WhatsApp.\n")

    else:
        # Raw text QR code (older bridge versions emit Unicode block chars)
        print("\n" + "═" * 60)
        print("   SCAN THIS QR CODE WITH WHATSAPP:")
        print("═" * 60)
        print(qr_data)
        print("═" * 60 + "\n")


# ──────────────────────────────────────────────────────────────────────────────
# Main flow
# ──────────────────────────────────────────────────────────────────────────────

async def run() -> None:
    homeserver   = os.getenv("MATRIX_HOMESERVER", "").strip()
    user_id      = os.getenv("MATRIX_USER", "").strip()
    access_token = os.getenv("MATRIX_ACCESS_TOKEN", "").strip()
    bridge_bot   = os.getenv("WHATSAPP_BRIDGE_BOT", BEEPER_BRIDGE_BOTS["whatsapp"]).strip()

    # ── validation ────────────────────────────────────────────────────────────
    missing = [k for k, v in {
        "MATRIX_HOMESERVER":    homeserver,
        "MATRIX_USER":          user_id,
        "MATRIX_ACCESS_TOKEN":  access_token,
    }.items() if not v]
    if missing:
        print(f"❌  Missing required .env variables: {', '.join(missing)}")
        sys.exit(1)

    # ── banner ────────────────────────────────────────────────────────────────
    print()
    print("╔══════════════════════════════════════════════════╗")
    print("║         Nexa — WhatsApp Bridge Login             ║")
    print("╚══════════════════════════════════════════════════╝")
    print(f"  Homeserver : {homeserver}")
    print(f"  User       : {user_id}")
    print(f"  Bridge bot : {bridge_bot}")
    print()

    manager = BridgeAuthManager(
        homeserver=homeserver,
        user_id=user_id,
        access_token=access_token,
    )

    try:
        # ── step 1: send login command and wait for QR ────────────────────────
        print("⏳  Connecting to Matrix and sending 'login' to bridge bot...")
        result = await manager.start_login(bridge_bot_id=bridge_bot, qr_timeout=35.0)

        if result["status"] == "error":
            err = result.get("error", "")
            print(f"❌  Login failed: {err}")
            if "M_UNKNOWN_TOKEN" in err or "Invalid access token" in err:
                print()
                print("  Your MATRIX_ACCESS_TOKEN in .env has expired or been revoked.")
                print("  Get a fresh token using one of these methods:")
                print()
                print("  Option 1 — Beeper desktop app:")
                print("    Settings → scroll to 'Access token' → Copy")
                print()
                print("  Option 2 — Element web / desktop:")
                print("    Settings → Help & About → Access Token → Click to reveal → Copy")
                print()
                print("  Option 3 — login script (needs your Beeper password):")
                print("    python bridge/auth/get_token.py")
                print()
                print("  Then update MATRIX_ACCESS_TOKEN in .env and re-run this script.")
            return

        if result["status"] == "connected":
            print("✅  Bridge is already authenticated — you're good to go!")
            return

        if result["status"] == "no_response":
            print("⚠️   Bridge bot did not respond within 35 seconds.")
            print(f"    Room: {result.get('room_id')}")
            print("    Try opening the room in Element/Beeper and sending 'login' manually.")
            return

        # ── step 2: display QR code ───────────────────────────────────────────
        print("📱  QR code received! Scan it with WhatsApp:\n")
        _render_qr_terminal(result["qr"])
        print("⏳  Waiting for you to scan (up to 2 minutes)...\n")

        # ── step 3: keep syncing until bridge confirms authentication ─────────
        client = manager._client
        timeout_secs = 120
        elapsed = 0
        interval = 5

        while elapsed < timeout_secs:
            try:
                await asyncio.wait_for(client.sync(timeout=interval * 1000), timeout=interval + 2)
            except asyncio.TimeoutError:
                pass

            if manager._conn_status == "connected":
                print("\n✅  WhatsApp connected! Bridge is authenticated.")
                print("    Your bot will now receive WhatsApp messages via Beeper.\n")
                return

            elapsed += interval
            print(f"   Waiting... {elapsed}s / {timeout_secs}s", end="\r")

        print("\n⚠️   Timed out. You may need to rescan.")
        print("    If you scanned the QR code, the bridge may still confirm shortly.")
        print(f"    Check the DM with {bridge_bot} in Element or the Beeper app.\n")

    except KeyboardInterrupt:
        print("\n\n👋  Cancelled by user.")
    finally:
        await manager.close()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
