"""Utilities for authenticating with mautrix-compatible Matrix bridges and storing app integrations."""

import logging
from typing import Dict, Any, Optional

import requests

logger = logging.getLogger(__name__)


class MautrixBridgeService:
    """Encapsulates mautrix bridge auth and integration registration logic."""

    def __init__(self, db_service, timeout_seconds: int = 5):
        self.db = db_service
        self.timeout_seconds = timeout_seconds

    def authenticate(
        self,
        *,
        user_id: str,
        base_url: str,
        mxid: Optional[str] = None,
        password: Optional[str] = None,
        access_token: Optional[str] = None,
        device_name: str = "nexa-connector",
    ) -> Dict[str, Any]:
        """Authenticate against Matrix/mautrix and persist token for this connector user."""
        base_url = base_url.rstrip("/")

        token = access_token
        whoami = None

        if token:
            whoami = self._verify_token(base_url, token)
        else:
            if not mxid or not password:
                raise ValueError("mxid and password are required when access_token is not provided")
            token, whoami = self._login_and_extract_token(
                base_url=base_url,
                mxid=mxid,
                password=password,
                device_name=device_name,
            )

        saved = self.db.upsert_mautrix_session(
            user_id=user_id,
            base_url=base_url,
            access_token=token,
            matrix_user_id=whoami.get("user_id", mxid),
            device_id=whoami.get("device_id"),
        )
        if not saved:
            raise RuntimeError("Failed to save mautrix session")

        return {
            "user_id": user_id,
            "base_url": base_url,
            "matrix_user_id": whoami.get("user_id", mxid),
            "device_id": whoami.get("device_id"),
            "access_token": token,
        }

    def connect_integration(
        self,
        *,
        user_id: str,
        app: str,
        config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Store app integration metadata for future bridge dispatching."""
        session = self.db.get_mautrix_session(user_id)
        if not session:
            raise ValueError("No mautrix session found. Authenticate first.")

        app_name = app.lower().strip()
        if not app_name:
            raise ValueError("app is required")

        metadata = config or {}
        status = "connected"

        if app_name == "whatsapp":
            metadata.setdefault("bridge", "mautrix-whatsapp")
        else:
            metadata.setdefault("bridge", f"mautrix-{app_name}")

        saved = self.db.upsert_app_integration(
            user_id=user_id,
            app=app_name,
            status=status,
            config=metadata,
        )
        if not saved:
            raise RuntimeError("Failed to save app integration")

        return {
            "user_id": user_id,
            "app": app_name,
            "status": status,
            "config": metadata,
        }

    def list_integrations(self, user_id: str):
        return self.db.list_app_integrations(user_id)

    def _login_and_extract_token(
        self,
        *,
        base_url: str,
        mxid: str,
        password: str,
        device_name: str,
    ):
        login_url = f"{base_url}/_matrix/client/v3/login"
        payload = {
            "type": "m.login.password",
            "identifier": {"type": "m.id.user", "user": mxid},
            "password": password,
            "initial_device_display_name": device_name,
        }

        response = requests.post(login_url, json=payload, timeout=self.timeout_seconds)
        if response.status_code >= 300:
            raise RuntimeError(f"Mautrix login failed: {response.status_code} {response.text}")

        data = response.json()
        token = data.get("access_token")
        if not token:
            raise RuntimeError("Mautrix login succeeded but no access_token found")

        whoami = self._verify_token(base_url, token)
        return token, whoami

    def _verify_token(self, base_url: str, access_token: str) -> Dict[str, Any]:
        whoami_url = f"{base_url}/_matrix/client/v3/account/whoami"
        response = requests.get(
            whoami_url,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=self.timeout_seconds,
        )
        if response.status_code >= 300:
            raise RuntimeError(f"Token verification failed: {response.status_code} {response.text}")

        data = response.json()
        if "user_id" not in data:
            logger.warning("whoami response missing user_id: %s", data)
        return data
