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
import hashlib
import hmac as _hmac
import json as _json
import os
import re
import secrets
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path

# Force UTF-8 output on Windows (cp1252 terminal can't encode box-drawing chars)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import aiohttp

_repo_root = Path(__file__).resolve().parents[2]
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

# ─── Config ───────────────────────────────────────────────────────────────────

SERVER_NAME       = os.getenv("MATRIX_SERVER_NAME", "localhost")
CONDUIT_URL       = "http://localhost:6167"           # host port (maps to Dendrite's 8008)
ADMIN_USERNAME    = "admin"
BRIDGE_CONFIG     = _repo_root / "bridge" / "whatsapp" / "config.yaml"
REGISTRATION_FILE = _repo_root / "bridge" / "whatsapp" / "whatsapp-registration.yaml"
ENV_FILE          = _repo_root / ".env"

LINKEDIN_BRIDGE_CONFIG     = _repo_root / "bridge" / "linkedin" / "config.yaml"
LINKEDIN_REGISTRATION_FILE = _repo_root / "bridge" / "linkedin" / "linkedin-registration.yaml"
LINKEDIN_PORT              = 29319


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


def _to_docker_path(path: Path) -> str:
    """
    Convert a local filesystem path to the format Docker expects in -v mounts.

    On Windows:  C:\\Users\\foo\\bar  →  /c/Users/foo/bar
    On Unix/Mac: /home/foo/bar       →  /home/foo/bar  (unchanged)
    """
    if sys.platform != "win32":
        return str(path)
    # Normalise separators and drive letter: C:\Users\... → /c/Users/...
    p = str(path).replace("\\", "/")
    if len(p) >= 2 and p[1] == ":":
        p = "/" + p[0].lower() + p[2:]
    return p


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
    for line in path.read_text(encoding="utf-8").splitlines():
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
    """
    Generate the mautrix-whatsapp appservice registration.

    Phase A  (Docker -e)  Pull a bridgev2-compatible example config.yaml from
                          the bridge image so we get the correct schema.
    Phase B  (Python)     Write whatsapp-registration.yaml directly — no second
                          Docker run needed, which avoids volume-mount failures
                          on Windows / OneDrive paths.
    """
    _print("\n── Step 1: Generate mautrix-whatsapp appservice registration ──")

    bridge_dir   = _repo_root / "bridge" / "whatsapp"
    docker_mount = _to_docker_path(bridge_dir)
    config_file  = bridge_dir / "config.yaml"

    # ── Already done? ────────────────────────────────────────────────────────
    if REGISTRATION_FILE.exists():
        _info("registration.yaml already exists — skipping generation")
        _inject_tokens_into_config()
        return

    # ── Phase A: generate a bridgev2 config.yaml from the bridge image ──────
    # Back up any existing hand-written template first (it uses the legacy
    # pre-bridgev2 schema which the current bridge binary refuses to load).
    if config_file.exists():
        backup = bridge_dir / "config.yaml.bak"
        config_file.rename(backup)
        _info("Backed up existing config.yaml → config.yaml.bak")

    _info("Phase A: generating example config.yaml from bridge image (-e)…")
    result = _run([
        "docker", "run", "--rm",
        "--entrypoint", "mautrix-whatsapp",
        "-v", f"{docker_mount}:/data",
        "dock.mau.dev/mautrix/whatsapp:latest",
        "-c", "/data/config.yaml",
        "-e",
    ])

    if not config_file.exists():
        # Volume mount silently failed (common on Windows/OneDrive paths).
        # Fall back: restore the backup and patch it instead.
        backup = bridge_dir / "config.yaml.bak"
        if backup.exists():
            backup.rename(config_file)
            _warn(
                "Docker volume mount appears to have failed (config not written).\n"
                "  Falling back to existing config.yaml — ensure Docker Desktop\n"
                "  has file sharing enabled for this drive in Settings → Resources."
            )
        else:
            _fail(
                "Example config was not created and no backup exists.\n"
                f"Docker stdout: {result.stdout}\nstderr: {result.stderr}\n"
                "Enable Docker Desktop file sharing for this drive and retry."
            )
    else:
        _ok("Generated bridge-native config.yaml")

    # ── Patch the generated (or restored) config with our settings ───────────
    _patch_generated_config(config_file)

    # ── Phase B: write registration.yaml in Python (no second Docker run) ────
    # This avoids the -g volume-mount issue on Windows and is fully equivalent:
    # the registration format is a Matrix spec (not bridge-specific).
    _info("Phase B: writing whatsapp-registration.yaml…")
    _write_registration_yaml()
    _inject_tokens_into_config()


def _write_registration_yaml() -> None:
    """
    Create whatsapp-registration.yaml with freshly-generated tokens.

    The appservice registration format is defined by the Matrix spec and is
    identical to what `mautrix-whatsapp -g` would produce.
    """
    as_token = secrets.token_hex(32)
    hs_token = secrets.token_hex(32)

    # Escape the server name for use inside a YAML regex string
    sn = SERVER_NAME.replace(".", r"\.")

    content = (
        "# mautrix-whatsapp appservice registration\n"
        "# Generated by bridge/auth/setup.py — do not edit manually.\n"
        "# Tokens here must match as_token / hs_token in config.yaml.\n"
        f"id: whatsapp\n"
        f"url: http://mautrix-whatsapp:29318\n"
        f'as_token: "{as_token}"\n'
        f'hs_token: "{hs_token}"\n'
        f"sender_localpart: whatsappbot\n"
        f"rate_limited: false\n"
        f"namespaces:\n"
        f"  users:\n"
        f"    - regex: '@whatsapp_.+:{sn}'\n"
        f"      exclusive: true\n"
        f"  aliases: []\n"
        f"  rooms: []\n"
        f"de.sorunome.msc2409.push_ephemeral: true\n"
        f"push_ephemeral: true\n"
    )
    REGISTRATION_FILE.write_text(content, encoding="utf-8")
    _ok(f"Generated {REGISTRATION_FILE.name}")


def _patch_generated_config(config_file: Path) -> None:
    """Overwrite key fields in the bridge-generated config.yaml."""
    text = config_file.read_text(encoding="utf-8")

    patches = {
        # Homeserver — point to our Conduit container (internal Docker network)
        # The generated config may use different example URLs across bridge versions
        r"(^\s*address:\s*)https?://example(?:\.com|\.localhost(?::\d+)?)": r"\g<1>http://conduit:8008",
        r"(^\s*domain:\s*)example(?:\.com|\.localhost)": rf"\g<1>{SERVER_NAME}",
        # Appservice — bridge's own address on the Docker network
        r"(^\s*address:\s*)http://localhost:29318": r"\g<1>http://mautrix-whatsapp:29318",
        # Bind on all interfaces so Synapse can reach the bridge from the Docker network
        r"(^\s*hostname:\s*)127\.0\.0\.1": r"\g<1>0.0.0.0",
        # Database — use SQLite in the bridge data volume (no Postgres needed)
        r"(^\s*type:\s*)postgres":    r"\g<1>sqlite3-fk-wal",
        r"(^\s*uri:\s*)postgres://[^\n]+": r"\g<1>file:/data/mautrix-whatsapp.db?_txlock=immediate",
        # Permissions — allow all users + mark our admin
        r'(\s*"\*"\s*:\s*)relay': r'\g<1>user',
        r'"@admin:example\.com"': f'"@{ADMIN_USERNAME}:{SERVER_NAME}"',
        r'"example\.com"':        f'"{SERVER_NAME}"',
    }
    for pattern, replacement in patches.items():
        text, n = re.subn(pattern, replacement, text, flags=re.MULTILINE)
        if n:
            _info(f"  patched: {pattern[:50]}")

    config_file.write_text(text, encoding="utf-8")
    _ok("Patched config.yaml with homeserver / domain / permissions")


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
    text = BRIDGE_CONFIG.read_text(encoding="utf-8")
    text = text.replace(
        '"@admin:localhost": "admin"',
        f'"@{ADMIN_USERNAME}:{SERVER_NAME}": "admin"',
    )
    BRIDGE_CONFIG.write_text(text, encoding="utf-8")

    _ok("Tokens injected into bridge/whatsapp/config.yaml")


# ─── Step 1c: Generate mautrix-linkedin registration ─────────────────────────

def step_generate_linkedin_registration() -> None:
    """
    Generate the mautrix-linkedin appservice registration.

    Mirrors step_generate_registration() for WhatsApp:
    Phase A  (Docker -e)  Pull example config.yaml from the bridge image.
    Phase B  (Python)     Write linkedin-registration.yaml directly.
    """
    _print("\n── Step 1c: Generate mautrix-linkedin appservice registration ──")

    bridge_dir   = _repo_root / "bridge" / "linkedin"
    bridge_dir.mkdir(parents=True, exist_ok=True)
    docker_mount = _to_docker_path(bridge_dir)
    config_file  = bridge_dir / "config.yaml"

    if LINKEDIN_REGISTRATION_FILE.exists():
        _info("linkedin-registration.yaml already exists — skipping generation")
        _inject_tokens_into_linkedin_config()
        return

    if config_file.exists():
        backup = bridge_dir / "config.yaml.bak"
        config_file.rename(backup)
        _info("Backed up existing linkedin config.yaml → config.yaml.bak")

    _info("Phase A: generating example config.yaml from linkedin bridge image (-e)…")
    result = _run([
        "docker", "run", "--rm",
        "--entrypoint", "mautrix-linkedin",
        "-v", f"{docker_mount}:/data",
        "dock.mau.dev/mautrix/linkedin:latest",
        "-c", "/data/config.yaml",
        "-e",
    ])

    if not config_file.exists():
        backup = bridge_dir / "config.yaml.bak"
        if backup.exists():
            backup.rename(config_file)
            _warn(
                "Docker volume mount failed — restored backup linkedin config.yaml.\n"
                "  Ensure Docker Desktop has file sharing enabled for this drive."
            )
        else:
            _fail(
                "LinkedIn bridge config was not created and no backup exists.\n"
                f"Docker stdout: {result.stdout}\nstderr: {result.stderr}"
            )
    else:
        _ok("Generated linkedin bridge-native config.yaml")

    _patch_linkedin_config(config_file)

    _info("Phase B: writing linkedin-registration.yaml…")
    _write_linkedin_registration_yaml()
    _inject_tokens_into_linkedin_config()


def _write_linkedin_registration_yaml() -> None:
    """Create linkedin-registration.yaml with freshly-generated tokens."""
    as_token = secrets.token_hex(32)
    hs_token = secrets.token_hex(32)

    sn = SERVER_NAME.replace(".", r"\.")

    content = (
        "# mautrix-linkedin appservice registration\n"
        "# Generated by bridge/auth/setup.py — do not edit manually.\n"
        "# Tokens here must match as_token / hs_token in config.yaml.\n"
        f"id: linkedin\n"
        f"url: http://mautrix-linkedin:{LINKEDIN_PORT}\n"
        f'as_token: "{as_token}"\n'
        f'hs_token: "{hs_token}"\n'
        f"sender_localpart: linkedinbot\n"
        f"rate_limited: false\n"
        f"namespaces:\n"
        f"  users:\n"
        f"    - regex: '@linkedin_.+:{sn}'\n"
        f"      exclusive: true\n"
        f"  aliases: []\n"
        f"  rooms: []\n"
        f"de.sorunome.msc2409.push_ephemeral: true\n"
        f"push_ephemeral: true\n"
    )
    LINKEDIN_REGISTRATION_FILE.write_text(content, encoding="utf-8")
    _ok(f"Generated {LINKEDIN_REGISTRATION_FILE.name}")


def _patch_linkedin_config(config_file: Path) -> None:
    """Overwrite key fields in the linkedin bridge-generated config.yaml."""
    text = config_file.read_text(encoding="utf-8")

    patches = {
        # Homeserver — point to Synapse on the internal Docker network
        r"(^\s*address:\s*)https?://example(?:\.com|\.localhost(?::\d+)?)": r"\g<1>http://conduit:8008",
        r"(^\s*domain:\s*)example(?:\.com|\.localhost)": rf"\g<1>{SERVER_NAME}",
        # Appservice — bridge's own address on the Docker network
        r"(^\s*address:\s*)http://localhost:\d+": rf"\g<1>http://mautrix-linkedin:{LINKEDIN_PORT}",
        # Bind on all interfaces so Synapse can reach the bridge
        r"(^\s*hostname:\s*)127\.0\.0\.1": r"\g<1>0.0.0.0",
        # Port
        r"(^\s*port:\s*)29318\b": rf"\g<1>{LINKEDIN_PORT}",
        # Database — use SQLite in the bridge data volume
        r"(^\s*type:\s*)postgres":       r"\g<1>sqlite3-fk-wal",
        r"(^\s*uri:\s*)postgres://[^\n]+": r"\g<1>file:/data/mautrix-linkedin.db?_txlock=immediate",
        # Permissions — allow all users + mark our admin
        r'(\s*"\*"\s*:\s*)relay':  r'\g<1>user',
        r'"@admin:example\.com"':  f'"@{ADMIN_USERNAME}:{SERVER_NAME}"',
        r'"example\.com"':         f'"{SERVER_NAME}"',
    }
    for pattern, replacement in patches.items():
        text, n = re.subn(pattern, replacement, text, flags=re.MULTILINE)
        if n:
            _info(f"  patched: {pattern[:50]}")

    config_file.write_text(text, encoding="utf-8")
    _ok("Patched linkedin config.yaml with homeserver / domain / permissions")


def _inject_tokens_into_linkedin_config() -> None:
    """Copy as_token and hs_token from linkedin-registration.yaml into config.yaml."""
    as_token = _read_yaml_value(LINKEDIN_REGISTRATION_FILE, "as_token")
    hs_token = _read_yaml_value(LINKEDIN_REGISTRATION_FILE, "hs_token")

    if not as_token or not hs_token:
        _warn("Could not read linkedin tokens — config.yaml may need manual update")
        return

    _set_yaml_value(LINKEDIN_BRIDGE_CONFIG, "as_token", as_token)
    _set_yaml_value(LINKEDIN_BRIDGE_CONFIG, "hs_token", hs_token)
    _set_yaml_value(LINKEDIN_BRIDGE_CONFIG, "domain", SERVER_NAME)

    text = LINKEDIN_BRIDGE_CONFIG.read_text(encoding="utf-8")
    text = text.replace(
        '"@admin:localhost": "admin"',
        f'"@{ADMIN_USERNAME}:{SERVER_NAME}": "admin"',
    )
    LINKEDIN_BRIDGE_CONFIG.write_text(text, encoding="utf-8")

    _ok("Tokens injected into bridge/linkedin/config.yaml")


# ─── Step 1b: Generate Synapse homeserver.yaml ───────────────────────────────

def step_generate_synapse_config() -> None:
    """
    Write bridge/synapse/homeserver.yaml with fresh random secrets.
    Synapse requires this file to be present before it can start.
    The signing key is auto-generated by Synapse on first boot.
    """
    _print("\n── Step 1b: Generate Synapse homeserver.yaml ──")

    synapse_dir = _repo_root / "bridge" / "synapse"
    synapse_dir.mkdir(parents=True, exist_ok=True)
    config_file = synapse_dir / "homeserver.yaml"

    # Always regenerate so secrets are fresh on each full setup
    reg_secret    = secrets.token_hex(32)
    macaroon_key  = secrets.token_hex(32)
    form_secret   = secrets.token_hex(32)

    config = f"""\
# Synapse Matrix homeserver configuration for Nexa
# Generated by bridge/auth/setup.py — do not edit manually.

server_name: "{SERVER_NAME}"
pid_file: /data/homeserver.pid

listeners:
  - port: 8008
    tls: false
    type: http
    x_forwarded: true
    resources:
      - names: [client]
        compress: false

database:
  name: sqlite3
  args:
    database: /data/homeserver.db

log_config: /config/logging.yaml
media_store_path: /data/media_store

# Open registration (no captcha) — this is a local, private homeserver
enable_registration: true
enable_registration_without_verification: true
registration_shared_secret: "{reg_secret}"

report_stats: false
macaroon_secret_key: "{macaroon_key}"
form_secret: "{form_secret}"
signing_key_path: /data/{SERVER_NAME}.signing.key

# No federation — local bridge only
federation_domain_whitelist: []
trusted_key_servers: []
suppress_key_server_warning: true

app_service_config_files:
  - /config/whatsapp-registration.yaml
  - /config/linkedin-registration.yaml
"""
    config_file.write_text(config, encoding="utf-8")
    _update_env("SYNAPSE_REGISTRATION_SECRET", reg_secret)
    _ok(f"Generated {config_file.relative_to(_repo_root)}")


# ─── Step 2: Start homeserver (Synapse) ──────────────────────────────────────

def step_start_conduit() -> None:
    _print("\n── Step 2: Start Matrix homeserver (Synapse) ──")

    result = _run(["docker-compose", "up", "-d", "conduit"],
                  cwd=str(_repo_root))
    if result.returncode != 0:
        # Try docker compose (v2 syntax)
        result = _run(["docker", "compose", "up", "-d", "conduit"],
                      cwd=str(_repo_root))
    if result.returncode != 0:
        _fail(f"Could not start Synapse:\n{result.stderr}")

    _ok("Synapse container started")
    _info("Waiting for Synapse to be ready (up to 90 s — first boot generates signing key)…")

    import urllib.request
    for attempt in range(90):
        try:
            urllib.request.urlopen(f"{CONDUIT_URL}/_matrix/client/versions", timeout=2)
            _ok("Synapse is ready")
            return
        except Exception:
            if attempt % 10 == 9:
                _info(f"  still waiting… ({attempt + 1}s)")
            time.sleep(1)

    _fail("Synapse did not become ready within 90 seconds.\n"
          "  Check: docker logs nexa-matrix")


# ─── Step 3: Register admin Matrix account ────────────────────────────────────

async def step_register_admin() -> None:
    """
    Register the admin user as a Synapse server admin using the shared-secret
    registration API.  Server admin status is required so the sidecar can later
    call /_synapse/admin/v1/users/{user_id}/login to impersonate regular users
    during WhatsApp onboarding.
    """
    _print("\n── Step 3: Register Matrix admin account (Synapse server admin) ──")

    reg_secret    = _read_env_value("SYNAPSE_REGISTRATION_SECRET")
    admin_password = secrets.token_urlsafe(20)

    async with aiohttp.ClientSession() as http:

        # ── Check if admin already exists ────────────────────────────────────
        async with http.post(
            f"{CONDUIT_URL}/_matrix/client/v3/login",
            json={
                "type":     "m.login.password",
                "user":     f"@{ADMIN_USERNAME}:{SERVER_NAME}",
                "password": _read_env_value("MATRIX_ADMIN_PASSWORD") or "",
            },
        ) as lr:
            ldata = await lr.json()

        if lr.status == 200:
            access_token = ldata["access_token"]
            _ok(f"Admin account already exists — logged in as @{ADMIN_USERNAME}:{SERVER_NAME}")
            _update_env("MATRIX_USER",         f"@{ADMIN_USERNAME}:{SERVER_NAME}")
            _update_env("MATRIX_ACCESS_TOKEN", access_token)
            _update_env("MATRIX_SERVER_NAME",  SERVER_NAME)
            _update_env("MATRIX_HOMESERVER",   CONDUIT_URL)
            _update_env("WHATSAPP_BRIDGE_BOT", f"@whatsappbot:{SERVER_NAME}")
            return

        # ── Fresh registration via Synapse shared-secret API (admin: true) ──
        if not reg_secret:
            _fail("SYNAPSE_REGISTRATION_SECRET not in .env — re-run setup from scratch.")

        # Step 1: get nonce
        async with http.get(
            f"{CONDUIT_URL}/_synapse/admin/v1/register"
        ) as resp:
            nonce_data = await resp.json()
            if resp.status != 200:
                _fail(f"Could not get registration nonce: {nonce_data}")
        nonce = nonce_data["nonce"]

        # Step 2: compute HMAC-SHA1 per Synapse spec
        mac = _hmac.new(reg_secret.encode(), digestmod=hashlib.sha1)
        mac.update(nonce.encode())
        mac.update(b"\x00")
        mac.update(ADMIN_USERNAME.encode())
        mac.update(b"\x00")
        mac.update(admin_password.encode())
        mac.update(b"\x00")
        mac.update(b"admin")
        digest = mac.hexdigest()

        # Step 3: register as server admin
        async with http.post(
            f"{CONDUIT_URL}/_synapse/admin/v1/register",
            json={
                "nonce":    nonce,
                "username": ADMIN_USERNAME,
                "password": admin_password,
                "admin":    True,
                "mac":      digest,
            },
        ) as resp:
            data = await resp.json()
            if resp.status == 200:
                access_token = data["access_token"]
                _ok(f"Registered @{ADMIN_USERNAME}:{SERVER_NAME} as Synapse server admin")
            elif data.get("errcode") == "M_USER_IN_USE":
                # Registered by a previous run — log in
                stored_pw = _read_env_value("MATRIX_ADMIN_PASSWORD")
                if not stored_pw:
                    _fail(
                        "Admin account exists but MATRIX_ADMIN_PASSWORD is not in .env.\n"
                        "Delete the synapse_data volume and re-run setup to start fresh."
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
                _fail(f"Admin registration failed ({resp.status}): {data.get('error', data)}")

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


# ─── Step 3b: Register appservice via Conduit admin room ─────────────────────

async def step_register_appservice() -> None:
    """
    Register the WhatsApp appservice with Conduit via its admin room.

    Conduit's `appservice_config_files` config key is silently ignored in
    current builds.  The admin room command is the only reliable alternative:
    we send compact JSON (no spaces → single shell word) as the yaml argument
    so Conduit's shell_words parser treats it as one value.
    """
    _print("\n── Step 3b: Register WhatsApp appservice in Conduit ──")

    admin_token = _read_env_value("MATRIX_ACCESS_TOKEN")
    if not admin_token:
        _fail("MATRIX_ACCESS_TOKEN not in .env — step 3 must succeed first")

    as_token  = _read_yaml_value(REGISTRATION_FILE, "as_token")
    hs_token  = _read_yaml_value(REGISTRATION_FILE, "hs_token")
    sender_lp = _read_yaml_value(REGISTRATION_FILE, "sender_localpart") or "whatsappbot"

    sn_re = SERVER_NAME.replace(".", r"\.")
    reg = {
        "id": "whatsapp",
        "url": "http://mautrix-whatsapp:29318",
        "as_token": as_token,
        "hs_token": hs_token,
        "sender_localpart": sender_lp,
        "rate_limited": False,
        "namespaces": {
            "users": [
                {"regex": f"^@whatsappbot:{sn_re}$",   "exclusive": True},
                {"regex": f"^@whatsapp_.*:{sn_re}$",   "exclusive": True},
            ],
            "aliases": [],
            "rooms": [],
        },
        "de.sorunome.msc2409.push_ephemeral": True,
        "receive_ephemeral": True,
    }

    # Compact JSON has no spaces → shell_words treats it as a single argument
    # Single-quoted so any special chars are safe
    reg_compact = _json.dumps(reg, separators=(",", ":"))
    cmd = f"!admin appservices register '{reg_compact}'"

    headers = {"Authorization": f"Bearer {admin_token}"}

    async with aiohttp.ClientSession() as http:
        # Find all rooms this admin has joined
        async with http.get(
            f"{CONDUIT_URL}/_matrix/client/v3/joined_rooms",
            headers=headers,
        ) as resp:
            rooms_data = await resp.json()

        # Locate the Conduit admin room via its canonical alias #admins:<server>
        admin_room_id = None
        for room_id in rooms_data.get("joined_rooms", []):
            safe_id = urllib.parse.quote(room_id, safe="")
            async with http.get(
                f"{CONDUIT_URL}/_matrix/client/v3/rooms/{safe_id}/state/m.room.canonical_alias/",
                headers=headers,
            ) as resp:
                if resp.status == 200:
                    state = await resp.json()
                    if state.get("alias") == f"#admins:{SERVER_NAME}":
                        admin_room_id = room_id
                        break

        # Fallback: use the first joined room if alias lookup failed
        if not admin_room_id:
            joined = rooms_data.get("joined_rooms", [])
            if not joined:
                _fail("Admin has no joined rooms — cannot register appservice")
            admin_room_id = joined[0]
            _warn(f"Admin room alias not found, using {admin_room_id} as fallback")

        _info(f"Sending registration command to {admin_room_id}…")
        txn_id = secrets.token_hex(8)
        safe_room = urllib.parse.quote(admin_room_id, safe="")
        async with http.put(
            f"{CONDUIT_URL}/_matrix/client/v3/rooms/{safe_room}/send/m.room.message/{txn_id}",
            headers=headers,
            json={"msgtype": "m.text", "body": cmd},
        ) as resp:
            if resp.status != 200:
                _fail(f"Send failed ({resp.status}): {await resp.text()}")

        # Give Conduit a moment to process the command
        await asyncio.sleep(3)

    _ok("Appservice registration command sent to Conduit")


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


# ─── Step 4b: Start LinkedIn bridge ──────────────────────────────────────────

def step_start_linkedin_bridge() -> None:
    _print("\n── Step 4b: Start mautrix-linkedin bridge ──")

    result = _run(
        ["docker-compose", "up", "-d", "mautrix-linkedin"],
        cwd=str(_repo_root),
    )
    if result.returncode != 0:
        result = _run(
            ["docker", "compose", "up", "-d", "mautrix-linkedin"],
            cwd=str(_repo_root),
        )
    if result.returncode != 0:
        _fail(f"Could not start linkedin bridge:\n{result.stderr}")

    _ok("mautrix-linkedin bridge container started")
    _info("Giving the bridge 5 seconds to connect to Synapse…")
    time.sleep(5)

    r = _run(["docker", "ps", "--filter", "name=nexa-linkedin-bridge", "--format", "{{.Status}}"])
    if "Up" in r.stdout:
        _ok("LinkedIn bridge container is running")
    else:
        _warn(
            "LinkedIn bridge container may have exited.\n"
            "  Check: docker logs nexa-linkedin-bridge\n"
            "  Common cause: as_token / hs_token mismatch between config.yaml and registration.yaml"
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
    step_generate_linkedin_registration()
    step_generate_synapse_config()
    step_start_conduit()
    await step_register_admin()
    step_start_bridge()
    step_start_linkedin_bridge()
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
    _print("  To connect a user's LinkedIn:")
    _print()
    _print('    DM @linkedinbot:localhost in Matrix')
    _print('    Send: login')
    _print('    → Bridge replies with instructions to paste a cURL command')
    _print('    → In browser DevTools (Network tab), find a LinkedIn GraphQL XHR request')
    _print('    → Right-click → Copy as cURL → paste to the bridge bot')
    _print()
    _print("  Full stack logs:")
    _print("    docker-compose logs -f")
    _print()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
