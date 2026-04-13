"""
BridgeAuthManager — authenticates mautrix bridges via Matrix DM flow.

How it works
------------
1. The user's Matrix account DMs the bridge bot (e.g. @whatsappbot:beeper.com).
2. The bot receives a "login" command and responds with a QR code.
3. The user scans the QR code with the platform app (WhatsApp, etc.).
4. The bridge bot confirms the connection.

This module handles steps 1-4 programmatically using matrix-nio, and
exposes the QR code as base64 so the sidecar API can return it to a client.

Supported platforms (Beeper hosted):
  whatsapp  →  @whatsappbot:beeper.com
  telegram  →  @telegrambot:beeper.com
  signal    →  @signalbot:beeper.com

For self-hosted bridges, set WHATSAPP_BRIDGE_BOT (or equivalent) in .env.
"""

from __future__ import annotations

import asyncio
import base64
import logging
from typing import Any, Dict, Optional

from nio import (
    AsyncClient,
    InviteMemberEvent,
    MatrixRoom,
    RoomMessageImage,
    RoomMessageText,
    SyncResponse,
)

log = logging.getLogger("bridge.auth")

# Default bridge bot IDs for Beeper-hosted bridges
BEEPER_BRIDGE_BOTS: Dict[str, str] = {
    "whatsapp": "@whatsappbot:beeper.com",
    "telegram": "@telegrambot:beeper.com",
    "signal":   "@signalbot:beeper.com",
    "instagram":"@instagrambot:beeper.com",
    "slack":    "@slackbot:beeper.com",
}


class BridgeAuthManager:
    """
    Manages authentication of a mautrix bridge by DMing its bot account.

    Usage (one-shot login):

        manager = BridgeAuthManager(homeserver, user_id, access_token)
        result  = await manager.start_login("whatsapp")
        # result["qr"]  → base64 PNG (or None if not yet received)
        # result["status"] → "pending_qr" | "connected" | "no_response" | "error"

    Lifecycle:
        Call close() when done to release the Matrix client connection.
    """

    def __init__(
        self,
        homeserver: str,
        user_id: str,
        access_token: str,
        bridge_bot_id: Optional[str] = None,
    ) -> None:
        self.homeserver = homeserver.rstrip("/")
        self.user_id = user_id
        self.access_token = access_token
        self.bridge_bot_id = bridge_bot_id

        self._client: Optional[AsyncClient] = None
        self._dm_room_id: Optional[str] = None
        self._qr_ready = asyncio.Event()
        self._qr_data: Optional[str] = None   # base64 PNG data-URI or raw text QR
        self._conn_status: str = "disconnected"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def start_login(
        self,
        platform: str = "whatsapp",
        bridge_bot_id: Optional[str] = None,
        qr_timeout: float = 30.0,
    ) -> Dict[str, Any]:
        """
        Initiate bridge login for the given platform.

        Returns a dict:
          status      : "pending_qr" | "connected" | "no_response" | "error"
          qr          : base64 data-URI PNG string, or raw text QR, or None
          room_id     : Matrix room ID of the DM with the bridge bot
          bridge_bot  : bridge bot's Matrix ID
        """
        bot_id = bridge_bot_id or self.bridge_bot_id or BEEPER_BRIDGE_BOTS.get(platform)
        if not bot_id:
            return {"status": "error", "error": f"No bridge bot ID for platform '{platform}'. "
                    "Set WHATSAPP_BRIDGE_BOT in .env or pass bridge_bot_id explicitly."}

        self.bridge_bot_id = bot_id
        self._qr_ready.clear()
        self._qr_data = None
        self._conn_status = "pending"

        try:
            client = await self._ensure_client()
            self._dm_room_id = await self._find_or_create_dm(client, bot_id)

            # Send the login command to the bridge bot
            await client.room_send(
                room_id=self._dm_room_id,
                message_type="m.room.message",
                content={"msgtype": "m.text", "body": "login"},
            )
            log.info("Sent 'login' to %s in room %s", bot_id, self._dm_room_id)

            # Poll sync until we get a QR code or timeout
            try:
                await asyncio.wait_for(self._sync_until_qr(client), timeout=qr_timeout)
            except asyncio.TimeoutError:
                log.warning("Timed out waiting for QR code (%.0fs)", qr_timeout)

            if self._conn_status == "connected":
                status = "connected"
            elif self._qr_data:
                status = "pending_qr"
            else:
                status = "no_response"

            return {
                "status": status,
                "qr": self._qr_data,
                "room_id": self._dm_room_id,
                "bridge_bot": bot_id,
            }

        except Exception as exc:
            log.error("Login initiation failed: %s", exc, exc_info=True)
            return {"status": "error", "error": str(exc)}

    async def get_status(
        self,
        platform: str = "whatsapp",
        bridge_bot_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Ask the bridge bot for its status and return the result.

        Sends "help" to the bot and waits briefly for a status response.
        """
        bot_id = bridge_bot_id or self.bridge_bot_id or BEEPER_BRIDGE_BOTS.get(platform)
        if not bot_id:
            return {"status": "unknown", "error": "No bridge bot ID configured"}

        try:
            client = await self._ensure_client()
            dm_room = self._dm_room_id or await self._find_or_create_dm(client, bot_id)
            self._dm_room_id = dm_room
            self.bridge_bot_id = bot_id

            await client.room_send(
                room_id=dm_room,
                message_type="m.room.message",
                content={"msgtype": "m.text", "body": "help"},
            )
            # Give the bridge bot a moment to reply
            await client.sync(timeout=4000)

            return {
                "status": self._conn_status,
                "room_id": dm_room,
                "bridge_bot": bot_id,
            }

        except Exception as exc:
            log.error("Status check failed: %s", exc)
            return {"status": "error", "error": str(exc)}

    async def logout(
        self,
        platform: str = "whatsapp",
        bridge_bot_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send 'logout' to the bridge bot."""
        bot_id = bridge_bot_id or self.bridge_bot_id or BEEPER_BRIDGE_BOTS.get(platform)
        if not bot_id:
            return {"status": "error", "error": "No bridge bot ID configured"}

        try:
            client = await self._ensure_client()
            dm_room = self._dm_room_id or await self._find_or_create_dm(client, bot_id)

            await client.room_send(
                room_id=dm_room,
                message_type="m.room.message",
                content={"msgtype": "m.text", "body": "logout"},
            )
            self._conn_status = "disconnected"
            log.info("Sent 'logout' to %s", bot_id)
            return {"status": "logged_out", "bridge_bot": bot_id}

        except Exception as exc:
            log.error("Logout failed: %s", exc)
            return {"status": "error", "error": str(exc)}

    async def close(self) -> None:
        """Close the underlying Matrix client."""
        if self._client is not None:
            await self._client.close()
            self._client = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _ensure_client(self) -> AsyncClient:
        """Return a connected, synced AsyncClient (creates one if needed)."""
        if self._client is None:
            client = AsyncClient(self.homeserver, self.user_id)
            client.access_token = self.access_token
            client.user_id = self.user_id

            # Register event callbacks
            client.add_event_callback(self._on_text_message, RoomMessageText)
            client.add_event_callback(self._on_image_message, RoomMessageImage)
            client.add_event_callback(self._on_invite, InviteMemberEvent)

            # Initial sync so the client knows about existing rooms
            resp = await client.sync(timeout=15000)
            if not isinstance(resp, SyncResponse):
                log.warning("Initial sync returned unexpected response: %s", resp)

            self._client = client
        return self._client

    async def _find_or_create_dm(self, client: AsyncClient, bot_id: str) -> str:
        """
        Return the room_id of the DM with bot_id, creating the room if needed.
        Only considers rooms with exactly two members (the user + the bot).
        """
        for room_id, room in client.rooms.items():
            members = list(room.users.keys())
            if bot_id in members and len(members) == 2:
                log.info("Found existing DM room with %s: %s", bot_id, room_id)
                return room_id

        # No DM found — create one
        resp = await client.room_create(
            invite=[bot_id],
            is_direct=True,
        )
        if hasattr(resp, "room_id"):
            log.info("Created new DM room with %s: %s", bot_id, resp.room_id)
            # Sync so the room appears in client.rooms
            await client.sync(timeout=5000)
            return resp.room_id

        raise RuntimeError(f"Failed to create DM room with {bot_id}: {resp}")

    async def _sync_until_qr(self, client: AsyncClient) -> None:
        """Sync in a loop until the QR ready event fires."""
        while not self._qr_ready.is_set():
            await client.sync(timeout=5000)

    # ------------------------------------------------------------------
    # Matrix event callbacks
    # ------------------------------------------------------------------

    async def _on_text_message(self, room: MatrixRoom, event: RoomMessageText) -> None:
        """
        Handle text messages from the bridge bot.

        The bridge bot may send:
        - A text-based QR code (older bridge versions) — lines of Unicode blocks
        - A status confirmation: "Successfully logged in as +1234..."
        - Error messages
        """
        if event.sender != self.bridge_bot_id:
            return
        if self._dm_room_id and room.room_id != self._dm_room_id:
            return

        body = event.body
        lower = body.lower()
        log.debug("Bridge bot text: %.120s", body)

        # Detect successful authentication
        success_phrases = [
            "successfully logged in",
            "logged in as",
            "connected to whatsapp",
            "whatsapp connection",
            "you are now logged in",
        ]
        if any(phrase in lower for phrase in success_phrases):
            self._conn_status = "connected"
            self._qr_ready.set()
            log.info("Bridge reported successful connection")
            return

        # Detect disconnection
        disconnect_phrases = ["logged out", "disconnected", "connection lost"]
        if any(phrase in lower for phrase in disconnect_phrases):
            self._conn_status = "disconnected"
            return

        # Detect text-based QR code (older mautrix versions emit blocks of ░█▄▀)
        qr_indicators = ["scan", "qr", "▄", "█", "░"]
        if any(ind in body for ind in qr_indicators) and "\n" in body:
            self._qr_data = body
            self._qr_ready.set()
            log.info("Received text QR code from bridge bot")

    async def _on_image_message(self, room: MatrixRoom, event: RoomMessageImage) -> None:
        """
        Handle image messages from the bridge bot.
        Newer mautrix-whatsapp sends the QR code as a PNG image event.
        """
        if event.sender != self.bridge_bot_id:
            return
        if self._dm_room_id and room.room_id != self._dm_room_id:
            return

        log.info("Received image from bridge bot — downloading QR code")
        try:
            resp = await self._client.download(event.url)
            if hasattr(resp, "body") and resp.body:
                b64 = base64.b64encode(resp.body).decode("utf-8")
                self._qr_data = f"data:image/png;base64,{b64}"
                self._qr_ready.set()
                log.info("QR code image downloaded (%d bytes)", len(resp.body))
            else:
                log.warning("Image download returned empty body")
        except Exception as exc:
            log.error("Failed to download QR image: %s", exc)

    async def _on_invite(self, room: MatrixRoom, event: InviteMemberEvent) -> None:
        """Auto-accept invites so the bot can join bridge-created rooms."""
        if event.state_key == self.user_id:
            log.info("Auto-accepting invite to room %s", room.room_id)
            await self._client.join(room.room_id)
