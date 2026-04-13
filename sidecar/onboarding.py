"""
OnboardingService — manages per-user WhatsApp bridge authentication.

The user-facing flow is exactly two steps:
  1. App calls start_session(user_id)  →  returns a QR code
  2. User scans the QR with their WhatsApp
  3. App polls get_status(session_id)  →  returns "connected"

Everything else (Matrix account creation, bridge bot DM, QR refresh) is
handled transparently inside this service.

Architecture
─────────────
Each Nexa user gets their own Matrix account on the self-hosted Conduit
homeserver.  That Matrix account DMs the mautrix-whatsapp bridge bot, which
creates an isolated WhatsApp session for that user.

Multiple users can onboard concurrently — each has their own session with
its own BridgeAuthManager (nio AsyncClient).

Session lifecycle
─────────────────
  pending_qr  →  user has not yet scanned
  connected   →  WhatsApp confirmed, session kept alive until cleanup
  expired     →  TTL exceeded (5 min), session auto-destroyed
  error       →  something failed during setup
"""

from __future__ import annotations

import asyncio
import logging
import secrets
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

import aiohttp

log = logging.getLogger("sidecar.onboarding")

SESSION_TTL_SECS = 300   # 5 minutes to scan QR before session expires


@dataclass
class OnboardingSession:
    manager: Any                   # BridgeAuthManager
    nexa_user_id: str
    matrix_user_id: str
    matrix_password: str           # stored so we can re-login if needed
    status: str = "pending_qr"
    expires_at: float = field(default_factory=lambda: time.time() + SESSION_TTL_SECS)


class OnboardingService:
    """
    Creates and tracks WhatsApp onboarding sessions.

    One instance lives for the lifetime of the sidecar process.
    Thread-safety: all public methods are async; nio clients are not
    shared across sessions so there are no data races.
    """

    def __init__(
        self,
        homeserver: str,
        server_name: str,
        admin_token: str,
        bridge_bot_id: str,
    ) -> None:
        self._homeserver   = homeserver.rstrip("/")
        self._server_name  = server_name
        self._admin_token  = admin_token
        self._bridge_bot   = bridge_bot_id
        self._sessions: Dict[str, OnboardingSession] = {}

    # ──────────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────────

    async def start_session(self, nexa_user_id: str) -> Dict[str, Any]:
        """
        Begin WhatsApp onboarding for a Nexa user.

        Steps (all transparent to the caller):
          1. Register a Matrix account on the local Conduit homeserver
          2. DM the mautrix-whatsapp bridge bot with "login"
          3. Receive the QR code from the bridge bot
          4. Return session_id + QR to the caller

        Returns:
          {
            session_id : str        — poll this with get_qr / get_status
            status     : str        — "pending_qr" | "connected" | "error"
            qr         : str | None — base64 data-URI PNG (scan with WhatsApp)
            expires_at : float      — Unix timestamp when session auto-expires
            matrix_user_id : str
          }
        """
        await self._cleanup_expired()

        matrix_username = f"nexa_{_safe_id(nexa_user_id)}"
        matrix_user_id  = f"@{matrix_username}:{self._server_name}"
        matrix_password = secrets.token_urlsafe(24)

        # ── 1. Ensure a Matrix account exists for this user ────────────────
        try:
            access_token = await self._ensure_matrix_account(
                username=matrix_username,
                password=matrix_password,
            )
        except Exception as exc:
            log.error("Matrix account setup failed for %s: %s", nexa_user_id, exc)
            return {"status": "error", "error": f"Account setup failed: {exc}"}

        # ── 2. Start bridge login (DM bot → receive QR) ───────────────────
        from bridge.auth.manager import BridgeAuthManager

        manager = BridgeAuthManager(
            homeserver=self._homeserver,
            user_id=matrix_user_id,
            access_token=access_token,
        )
        result = await manager.start_login(
            bridge_bot_id=self._bridge_bot,
            qr_timeout=30.0,
        )

        if result["status"] == "error":
            await manager.close()
            return result

        # ── 3. Store session ───────────────────────────────────────────────
        session_id = secrets.token_urlsafe(16)
        session = OnboardingSession(
            manager=manager,
            nexa_user_id=nexa_user_id,
            matrix_user_id=matrix_user_id,
            matrix_password=matrix_password,
            status=result["status"],
        )
        self._sessions[session_id] = session

        log.info(
            "Onboarding session %s started for user %s (%s)",
            session_id, nexa_user_id, matrix_user_id,
        )
        return {
            "session_id":     session_id,
            "status":         result["status"],
            "qr":             result.get("qr"),
            "expires_at":     session.expires_at,
            "matrix_user_id": matrix_user_id,
        }

    async def get_qr(self, session_id: str) -> Dict[str, Any]:
        """
        Return the latest QR code for a session.

        mautrix-whatsapp refreshes the QR code every ~20 seconds.
        The client should call this endpoint every 18 seconds and re-render
        the displayed QR code so the user can scan the freshest version.
        """
        session = self._sessions.get(session_id)
        if not session:
            return {"status": "not_found", "qr": None}
        if _is_expired(session):
            await self.cleanup_session(session_id)
            return {"status": "expired", "qr": None}

        await _sync_once(session.manager)
        return {
            "session_id": session_id,
            "status":     session.manager._conn_status or session.status,
            "qr":         session.manager._qr_data,
        }

    async def get_status(self, session_id: str) -> Dict[str, Any]:
        """
        Poll connection status.

        Client should call this every 3 seconds after showing the QR.
        When status == "connected", WhatsApp messages will start flowing
        through the bridge to the sidecar.
        """
        session = self._sessions.get(session_id)
        if not session:
            return {"status": "not_found"}
        if _is_expired(session):
            await self.cleanup_session(session_id)
            return {"status": "expired"}

        await _sync_once(session.manager)

        # Propagate status from the nio callbacks
        live_status = session.manager._conn_status
        if live_status and live_status != "pending":
            session.status = live_status

        return {
            "session_id":     session_id,
            "status":         session.status,
            "nexa_user_id":   session.nexa_user_id,
            "matrix_user_id": session.matrix_user_id,
            "expires_at":     session.expires_at,
        }

    async def cleanup_session(self, session_id: str) -> None:
        """Close the Matrix client and remove the session."""
        session = self._sessions.pop(session_id, None)
        if session:
            await session.manager.close()
            log.info("Session %s removed", session_id)

    # ──────────────────────────────────────────────────────────────────────
    # Matrix account management
    # ──────────────────────────────────────────────────────────────────────

    async def _ensure_matrix_account(
        self, username: str, password: str
    ) -> str:
        """
        Register a Matrix account and return its access token.
        If the username is taken, use the Conduit/Synapse admin API to
        get a token for that existing account instead.
        """
        async with aiohttp.ClientSession() as http:
            # Attempt registration via the standard Matrix client API
            async with http.post(
                f"{self._homeserver}/_matrix/client/v3/register",
                json={
                    "username": username,
                    "password": password,
                    "kind":     "user",
                    "auth":     {"type": "m.login.dummy"},
                },
            ) as resp:
                data = await resp.json()

                if resp.status == 200:
                    log.info("Registered Matrix account %s", username)
                    return data["access_token"]

                if data.get("errcode") == "M_USER_IN_USE":
                    log.info(
                        "Matrix account %s already exists — fetching token via admin API",
                        username,
                    )
                    return await self._admin_impersonate(username, http)

                # Some homeservers require a registration token or dummy UIA
                if data.get("errcode") == "M_UNKNOWN" and "flows" in data:
                    # UIA challenge — try with dummy auth
                    session_key = data.get("session", "")
                    async with http.post(
                        f"{self._homeserver}/_matrix/client/v3/register",
                        json={
                            "username": username,
                            "password": password,
                            "kind":     "user",
                            "auth": {
                                "type":    "m.login.dummy",
                                "session": session_key,
                            },
                        },
                    ) as resp2:
                        data2 = await resp2.json()
                        if resp2.status == 200:
                            return data2["access_token"]
                        raise RuntimeError(
                            f"Registration (UIA) failed: {data2.get('error', data2)}"
                        )

                raise RuntimeError(
                    f"Registration failed ({resp.status}): {data.get('error', data)}"
                )

    async def _admin_impersonate(
        self, username: str, http: aiohttp.ClientSession
    ) -> str:
        """
        Use the homeserver admin API to get a login token for an existing user.
        Works for both Synapse (_synapse/admin) and Conduit (_conduit/admin).
        """
        full_user_id = f"@{username}:{self._server_name}"
        headers = {"Authorization": f"Bearer {self._admin_token}"}

        # Try Synapse admin API first (also supported by some Conduit builds)
        async with http.post(
            f"{self._homeserver}/_synapse/admin/v1/users/{full_user_id}/login",
            headers=headers,
            json={},
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data["access_token"]

        # Fallback: standard password login (requires stored password)
        # This path is taken when the user was registered by us (we know the password)
        async with http.post(
            f"{self._homeserver}/_matrix/client/v3/login",
            json={
                "type":     "m.login.password",
                "user":     full_user_id,
                "password": "",   # blank — will fail, but signals the path
            },
        ) as resp:
            data = await resp.json()
            raise RuntimeError(
                f"Cannot impersonate {full_user_id}. "
                f"Admin API failed. Store the password or use a fresh username. "
                f"Error: {data.get('error', data)}"
            )

    # ──────────────────────────────────────────────────────────────────────
    # Cleanup
    # ──────────────────────────────────────────────────────────────────────

    async def _cleanup_expired(self) -> None:
        expired = [sid for sid, s in self._sessions.items() if _is_expired(s)]
        for sid in expired:
            await self.cleanup_session(sid)
        if expired:
            log.info("Auto-cleaned %d expired session(s)", len(expired))

    async def close_all(self) -> None:
        """Shutdown hook — close all open Matrix clients."""
        for sid in list(self._sessions):
            await self.cleanup_session(sid)


# ──────────────────────────────────────────────────────────────────────────────
# Module-level helpers
# ──────────────────────────────────────────────────────────────────────────────

def _safe_id(user_id: str) -> str:
    """Sanitise a user ID for use as a Matrix localpart (lowercase alphanum + _)."""
    import re
    return re.sub(r"[^a-z0-9_]", "_", user_id.lower())[:24]


def _is_expired(session: OnboardingSession) -> bool:
    return time.time() > session.expires_at


async def _sync_once(manager: Any) -> None:
    """Sync the manager's Matrix client once to pick up new bridge bot events."""
    if manager._client is None:
        return
    try:
        await asyncio.wait_for(manager._client.sync(timeout=2000), timeout=5.0)
    except (asyncio.TimeoutError, Exception) as exc:
        log.debug("sync_once: %s (non-fatal)", exc)
