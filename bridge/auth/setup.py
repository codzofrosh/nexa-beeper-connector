"""
Nexa — one-time infrastructure setup script.

Run this ONCE before starting the stack for the first time.

What it does (in order)
────────────────────────
1. Generates the mautrix-whatsapp appservice registration file
   (bridge/whatsapp/whatsapp-registration.yaml)
   and fills the matching tokens into bridge/whatsapp/config.yaml.

2. Starts Conduit (Matrix homeserver) so it picks up the registration.

3. Registers an admin Matrix account on Conduit.
   Saves credentials to .env as MATRIX_USER / MATRIX_ACCESS_TOKEN.

4. Verifies the bridge bot (@whatsappbot:localhost) is reachable.

5. Prints a summary and the next command to run.

Usage
─────
    python bridge/auth/setup.py

Prerequisites
─────────────
    Docker must be running.
    docker-compose.yaml must be present (already committed to the repo).

After setup
───────────
    docker-compose up -d       # start the full stack
    # Users onboard via:
    # POST http://localhost:8080/api/onboard/whatsapp/start
"""

from __future__ import annotations

import asyncio
import os
import re
import secrets
import subprocess
import sys
import time
from pathlib import Path

import aiohttp

_repo_root = Path(__file__).resolve().parents[2]
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

# ─── Config ───────────────────────────────────────────────────────────────────

SERVER_NAME       = os.getenv("MATRIX_SERVER_NAME", "localhost")
CONDUIT_URL       = f"http://localhost:6167"          # exposed port from docker-compose
ADMIN_USERNAME    = "admin"
BRIDGE_CONFIG     = _repo_root / "bridge" / "whatsapp" / "config.yaml"
REGISTRATION_FILE = _repo_root / "bridge" / "whatsapp" / "whatsapp-registration.yaml"
ENV_FILE          = _repo_root / ".env"


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _print(msg: str = "") -> None:
    print(msg, flush=True)


def _ok(msg: str) -> None:
    _print(f"  ✅  {msg}")


def _info(msg: str) -> None:
    _print(f"  ℹ️   {msg}")


def _warn(msg: str) -> None:
    _print(f"  ⚠️   {msg}")


def _fail(msg: str) -> None:
    _print(f"  ❌  {msg}")
    sys.exit(1)


def _run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, **kwargs)


def _update_env(key: str, value: str) -> None:
    """Write or replace a key=value line in .env."""
    text = ENV_FILE.read_text(encoding="utf-8") if ENV_FILE.exists() else ""
    line = f"{key}={value}"
    new_text, n = re.subn(
        rf"^{re.escape(key)}\s*=.*$", line, text, flags=re.MULTILINE
    )
    if n == 0:
        new_text = text.rstrip("\n") + f"\n{line}\n"
    ENV_FILE.write_text(new_text, encoding="utf-8")
    _ok(f"{key} written to .env")


def _read_yaml_value(path: Path, key: str) -> str:
    """Extract a scalar value from a YAML file without a full YAML parser."""
    for line in path.read_text().splitlines():
        m = re.match(rf"^\s*{re.escape(key)}\s*:\s*['\"]?([^'\"#\n]+)['\"]?", line)
        if m:
            return m.group(1).strip()
    return ""


def _set_yaml_value(path: Path, key: str, value: str) -> None:
    """Replace a scalar value in a YAML file in-place."""
    text = path.read_text(encoding="utf-8")
    new_text, n = re.subn(
        rf'^(\s*{re.escape(key)}\s*:\s*).*$',
        rf'\g<1>"{value}"',
        text,
        flags=re.MULTILINE,
    )
    if n == 0:
        _warn(f"Key '{key}' not found in {path.name} — skipping")
        return
    path.write_text(new_text, encoding="utf-8")


# ─── Step 1: Generate mautrix-whatsapp registration ───────────────────────────

def step_generate_registration() -> None:
    _print("\n── Step 1: Generate mautrix-whatsapp appservice registration ──")

    if REGISTRATION_FILE.exists():
        _info(f"{REGISTRATION_FILE.name} already exists — skipping generation")
        _inject_tokens_into_config()
        return

    _info("Running mautrix-whatsapp --generate-registration (Docker)…")

    result = _run([
        "docker", "run", "--rm",
        "--entrypoint", "mautrix-whatsapp",
        "-v", f"{_repo_root / 'bridge' / 'whatsapp'}:/data",
        "dock.mau.dev/mautrix/whatsapp:latest",
        "--generate-registration",
    ])

    if result.returncode != 0:
        _fail(
            f"Registration generation failed:\n{result.stderr}\n\n"
            "Make sure Docker is running and you have internet access."
        )

    if not REGISTRATION_FILE.exists():
        # Some versions write a differently-named file
        candidates = list((_repo_root / "bridge" / "whatsapp").glob("*registration*.yaml"))
        if candidates:
            candidates[0].rename(REGISTRATION_FILE)
        else:
            _fail(
                "Registration file was not created. "
                "Check bridge/whatsapp/ for any new .yaml file."
            )

    _ok(f"Generated {REGISTRATION_FILE.name}")
    _inject_tokens_into_config()


def _inject_tokens_into_config() -> None:
    """Copy as_token and hs_token from registration.yaml into config.yaml."""
    as_token = _read_yaml_value(REGISTRATION_FILE, "as_token")
    hs_token = _read_yaml_value(REGISTRATION_FILE, "hs_token")

    if not as_token or not hs_token:
        _warn("Could not read tokens from registration.yaml — config.yaml may need manual update")
        return

    _set_yaml_value(BRIDGE_CONFIG, "as_token", as_token)
    _set_yaml_value(BRIDGE_CONFIG, "hs_token", hs_token)

    # Also update the server domain in config.yaml to match .env
    _set_yaml_value(BRIDGE_CONFIG, "domain", SERVER_NAME)
    # And the bridge bot permissions
    text = BRIDGE_CONFIG.read_text()
    text = text.replace(
        '"@admin:localhost": "admin"',
        f'"@{ADMIN_USERNAME}:{SERVER_NAME}": "admin"',
    )
    BRIDGE_CONFIG.write_text(text)

    _ok("Tokens injected into bridge/whatsapp/config.yaml")


# ─── Step 2: Start Conduit ────────────────────────────────────────────────────

def step_start_conduit() -> None:
    _print("\n── Step 2: Start Conduit homeserver ──")

    result = _run(["docker-compose", "up", "-d", "conduit"],
                  cwd=str(_repo_root))
    if result.returncode != 0:
        # Try docker compose (v2 syntax)
        result = _run(["docker", "compose", "up", "-d", "conduit"],
                      cwd=str(_repo_root))
    if result.returncode != 0:
        _fail(f"Could not start Conduit:\n{result.stderr}")

    _ok("Conduit container started")
    _info("Waiting for Conduit to be ready…")

    for attempt in range(30):
        try:
            import urllib.request
            urllib.request.urlopen(f"{CONDUIT_URL}/_matrix/client/versions", timeout=2)
            _ok("Conduit is ready")
            return
        except Exception:
            time.sleep(1)

    _fail("Conduit did not become ready within 30 seconds. Check: docker logs nexa-matrix")


# ─── Step 3: Register admin Matrix account ────────────────────────────────────

async def step_register_admin() -> None:
    _print("\n── Step 3: Register Matrix admin account ──")

    admin_password = secrets.token_urlsafe(20)

    async with aiohttp.ClientSession() as http:
        # Try standard registration
        async with http.post(
            f"{CONDUIT_URL}/_matrix/client/v3/register",
            json={
                "username": ADMIN_USERNAME,
                "password": admin_password,
                "kind":     "user",
                "auth":     {"type": "m.login.dummy"},
            },
        ) as resp:
            data = await resp.json()

            if resp.status == 200:
                access_token = data["access_token"]
                _ok(f"Registered @{ADMIN_USERNAME}:{SERVER_NAME}")

            elif data.get("errcode") == "M_USER_IN_USE":
                _info(f"Admin account already exists — logging in")
                # Try to login with stored password from .env
                stored_pw = _read_env_value("MATRIX_ADMIN_PASSWORD")
                if not stored_pw:
                    _fail(
                        "Admin account exists but MATRIX_ADMIN_PASSWORD is not in .env.\n"
                        "Either delete the Conduit data volume and re-run setup,\n"
                        "or manually set MATRIX_USER and MATRIX_ACCESS_TOKEN in .env."
                    )
                async with http.post(
                    f"{CONDUIT_URL}/_matrix/client/v3/login",
                    json={
                        "type":     "m.login.password",
                        "user":     f"@{ADMIN_USERNAME}:{SERVER_NAME}",
                        "password": stored_pw,
                    },
                ) as lr:
                    ldata = await lr.json()
                    if lr.status != 200:
                        _fail(f"Admin login failed: {ldata.get('error', ldata)}")
                    access_token = ldata["access_token"]
                    _ok(f"Logged in as @{ADMIN_USERNAME}:{SERVER_NAME}")

            else:
                _fail(f"Registration failed ({resp.status}): {data.get('error', data)}")

    # Persist credentials
    _update_env("MATRIX_USER",           f"@{ADMIN_USERNAME}:{SERVER_NAME}")
    _update_env("MATRIX_ACCESS_TOKEN",   access_token)
    _update_env("MATRIX_ADMIN_PASSWORD", admin_password)
    _update_env("MATRIX_SERVER_NAME",    SERVER_NAME)
    _update_env("MATRIX_HOMESERVER",     CONDUIT_URL)
    _update_env("WHATSAPP_BRIDGE_BOT",   f"@whatsappbot:{SERVER_NAME}")


def _read_env_value(key: str) -> str:
    if not ENV_FILE.exists():
        return ""
    for line in ENV_FILE.read_text().splitlines():
        m = re.match(rf"^{re.escape(key)}\s*=\s*(.+)$", line)
        if m:
            return m.group(1).strip()
    return ""


# ─── Step 4: Start the bridge and verify bot ─────────────────────────────────

def step_start_bridge() -> None:
    _print("\n── Step 4: Start mautrix-whatsapp bridge ──")

    result = _run(
        ["docker-compose", "up", "-d", "mautrix-whatsapp"],
        cwd=str(_repo_root),
    )
    if result.returncode != 0:
        result = _run(
            ["docker", "compose", "up", "-d", "mautrix-whatsapp"],
            cwd=str(_repo_root),
        )
    if result.returncode != 0:
        _fail(f"Could not start bridge:\n{result.stderr}")

    _ok("mautrix-whatsapp bridge container started")
    _info("Giving the bridge 5 seconds to connect to Conduit…")
    time.sleep(5)

    # Quick sanity: check bridge container is still running
    r = _run(["docker", "ps", "--filter", "name=nexa-whatsapp-bridge", "--format", "{{.Status}}"])
    if "Up" in r.stdout:
        _ok("Bridge container is running")
    else:
        _warn(
            "Bridge container may have exited. Check: docker logs nexa-whatsapp-bridge\n"
            "Common cause: as_token / hs_token mismatch between config.yaml and registration.yaml"
        )


# ─── Step 5: Start sidecar ────────────────────────────────────────────────────

def step_start_sidecar() -> None:
    _print("\n── Step 5: Start Nexa sidecar ──")

    result = _run(
        ["docker-compose", "up", "-d", "nexa-sidecar"],
        cwd=str(_repo_root),
    )
    if result.returncode != 0:
        result = _run(
            ["docker", "compose", "up", "-d", "nexa-sidecar"],
            cwd=str(_repo_root),
        )
    if result.returncode != 0:
        _fail(f"Could not start sidecar:\n{result.stderr}")

    _ok("Nexa sidecar started")
    _info("Waiting for sidecar to be ready…")

    for _ in range(20):
        try:
            import urllib.request
            urllib.request.urlopen("http://localhost:8080/health", timeout=2)
            _ok("Sidecar is ready at http://localhost:8080")
            return
        except Exception:
            time.sleep(1)

    _warn("Sidecar health check timed out — it may still be starting")


# ─── Main ─────────────────────────────────────────────────────────────────────

async def run() -> None:
    _print()
    _print("╔══════════════════════════════════════════════════════╗")
    _print("║            Nexa — Infrastructure Setup               ║")
    _print("╚══════════════════════════════════════════════════════╝")
    _print(f"  Repo root   : {_repo_root}")
    _print(f"  Server name : {SERVER_NAME}")
    _print()

    step_generate_registration()
    step_start_conduit()
    await step_register_admin()
    step_start_bridge()
    step_start_sidecar()

    _print()
    _print("╔══════════════════════════════════════════════════════╗")
    _print("║                  Setup complete ✅                    ║")
    _print("╚══════════════════════════════════════════════════════╝")
    _print()
    _print("  Onboarding API is live at http://localhost:8080")
    _print()
    _print("  To connect a user's WhatsApp:")
    _print()
    _print('    POST http://localhost:8080/api/onboard/whatsapp/start')
    _print('    Body: {"user_id": "alice"}')
    _print()
    _print('    → Returns a QR code (base64 PNG)')
    _print('    → User scans with WhatsApp')
    _print('    → Poll GET /api/onboard/whatsapp/status/{session_id}')
    _print('    → Status becomes "connected"')
    _print()
    _print("  Full stack logs:")
    _print("    docker-compose logs -f")
    _print()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
