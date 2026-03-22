"""Helpers for sending messages through Matrix/mautrix bridged rooms.

This module keeps the actual transport details in one place so the bridge
executor can stay focused on idempotency and retries. In practice, sending a
message to a Matrix room that is bridged by mautrix-whatsapp causes the bridge
to forward the message to WhatsApp, so the connector only needs homeserver
credentials and the room id.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import logging
import os
from typing import Optional
from urllib import error, parse, request

log = logging.getLogger("bridge.mautrix")


@dataclass(frozen=True)
class MautrixConfig:
    """Configuration required to send events via a Matrix homeserver."""

    homeserver_url: str
    access_token: str
    sender_user_id: Optional[str] = None
    device_id: Optional[str] = None

    @classmethod
    def from_env(cls) -> "MautrixConfig":
        homeserver_url = (
            os.getenv("MAUTRIX_HOMESERVER")
            or os.getenv("MATRIX_HOMESERVER")
            or ""
        ).strip()
        access_token = (
            os.getenv("MAUTRIX_ACCESS_TOKEN")
            or os.getenv("MATRIX_ACCESS_TOKEN")
            or ""
        ).strip()
        sender_user_id = (
            os.getenv("MAUTRIX_IMPERSONATE_USER_ID")
            or os.getenv("MAUTRIX_USER_ID")
            or os.getenv("MATRIX_USER")
            or None
        )
        device_id = os.getenv("MAUTRIX_DEVICE_ID") or None

        if not homeserver_url:
            raise ValueError(
                "Missing mautrix homeserver URL. Set MAUTRIX_HOMESERVER or MATRIX_HOMESERVER."
            )
        if not access_token:
            raise ValueError(
                "Missing mautrix access token. Set MAUTRIX_ACCESS_TOKEN or MATRIX_ACCESS_TOKEN."
            )

        return cls(
            homeserver_url=homeserver_url.rstrip("/"),
            access_token=access_token,
            sender_user_id=sender_user_id,
            device_id=device_id,
        )


class MautrixSender:
    """Small client for sending messages into mautrix-bridged Matrix rooms."""

    def __init__(self, config: MautrixConfig, timeout: float = 10.0):
        self.config = config
        self.timeout = timeout

    def send_text(self, *, room_id: str, text: str, txn_id: str) -> str:
        """Send a text message into a Matrix room.

        Args:
            room_id: Matrix room id that mautrix-whatsapp is bridging.
            text: Plain text message body.
            txn_id: Matrix transaction id used for idempotent sends.

        Returns:
            The event id returned by the homeserver.
        """
        path = (
            f"/_matrix/client/v3/rooms/"
            f"{parse.quote(room_id, safe='')}/send/m.room.message/"
            f"{parse.quote(txn_id, safe='')}"
        )
        params = {}
        if self.config.sender_user_id:
            params["user_id"] = self.config.sender_user_id
        if self.config.device_id:
            params["device_id"] = self.config.device_id

        url = f"{self.config.homeserver_url}{path}"
        if params:
            url = f"{url}?{parse.urlencode(params)}"

        payload = {
            "msgtype": "m.text",
            "body": text,
        }
        req = request.Request(
            url=url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.config.access_token}",
                "Content-Type": "application/json",
            },
            method="PUT",
        )

        log.info(
            "Sending mautrix bridged message",
            extra={"room_id": room_id, "txn_id": txn_id, "sender_user_id": self.config.sender_user_id},
        )

        try:
            with request.urlopen(req, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8") or "{}"
        except error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"Matrix send failed with HTTP {exc.code}: {body}"
            ) from exc
        except error.URLError as exc:
            raise RuntimeError(f"Matrix send failed: {exc.reason}") from exc

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Matrix send returned invalid JSON: {raw}") from exc

        event_id = parsed.get("event_id")
        if not event_id:
            raise RuntimeError(f"Matrix send response missing event_id: {parsed}")
        return event_id
