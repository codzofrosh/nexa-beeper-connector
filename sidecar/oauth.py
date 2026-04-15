"""
OAuth2 provider integrations for Nexa user authentication.

Supports Google and GitHub (Authorization Code flow, server-side secret exchange).
State tokens are kept in memory — safe for a single-worker sidecar process.
"""

from __future__ import annotations

import os
import secrets
import time
import urllib.parse
from typing import Optional

import aiohttp

# ── CSRF state store ───────────────────────────────────────────────────────────
# state token → (provider, created_at_monotonic)
# Pruned on every generate/consume call.

_STATE_TTL = 300  # seconds
_state_store: dict[str, tuple[str, float]] = {}


def _prune_states() -> None:
    now = time.monotonic()
    expired = [k for k, (_, ts) in _state_store.items() if now - ts > _STATE_TTL]
    for k in expired:
        del _state_store[k]


def generate_state(provider: str) -> str:
    """Create a random state token bound to a provider and store it."""
    _prune_states()
    state = secrets.token_urlsafe(24)
    _state_store[state] = (provider, time.monotonic())
    return state


def consume_state(state: str) -> Optional[str]:
    """
    Validate and remove a state token (one-time use).
    Returns the provider name, or None if the state is invalid / expired.
    """
    _prune_states()
    entry = _state_store.pop(state, None)
    if entry is None:
        return None
    provider, ts = entry
    if time.monotonic() - ts > _STATE_TTL:
        return None
    return provider


# ── Helpers ────────────────────────────────────────────────────────────────────

def _require_env(key: str) -> str:
    val = os.getenv(key, "")
    if not val:
        raise RuntimeError(f"OAuth env var {key!r} is not set")
    return val


# ── Google ─────────────────────────────────────────────────────────────────────

_GOOGLE_AUTH_URL  = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
_GOOGLE_USER_URL  = "https://www.googleapis.com/oauth2/v3/userinfo"


def google_configured() -> bool:
    return bool(os.getenv("GOOGLE_CLIENT_ID") and os.getenv("GOOGLE_CLIENT_SECRET"))


def google_auth_url(redirect_uri: str, state: str) -> str:
    params = {
        "client_id":     _require_env("GOOGLE_CLIENT_ID"),
        "redirect_uri":  redirect_uri,
        "response_type": "code",
        "scope":         "openid email profile",
        "state":         state,
        "access_type":   "online",
        "prompt":        "select_account",
    }
    return f"{_GOOGLE_AUTH_URL}?{urllib.parse.urlencode(params)}"


async def exchange_google_code(code: str, redirect_uri: str) -> dict:
    """Exchange an auth code for {email, name, sub}."""
    async with aiohttp.ClientSession() as http:
        async with http.post(_GOOGLE_TOKEN_URL, data={
            "code":          code,
            "client_id":     _require_env("GOOGLE_CLIENT_ID"),
            "client_secret": _require_env("GOOGLE_CLIENT_SECRET"),
            "redirect_uri":  redirect_uri,
            "grant_type":    "authorization_code",
        }) as resp:
            token_data = await resp.json()
            if resp.status != 200 or "access_token" not in token_data:
                raise ValueError(
                    f"Google token exchange failed: "
                    f"{token_data.get('error_description', token_data)}"
                )
            access_token = token_data["access_token"]

        async with http.get(
            _GOOGLE_USER_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        ) as resp:
            user_data = await resp.json()

    return {
        "email": user_data.get("email", ""),
        "name":  user_data.get("name") or user_data.get("given_name") or "Google User",
        "sub":   user_data.get("sub", ""),
    }


# ── GitHub ─────────────────────────────────────────────────────────────────────

_GITHUB_AUTH_URL  = "https://github.com/login/oauth/authorize"
_GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
_GITHUB_USER_URL  = "https://api.github.com/user"
_GITHUB_EMAIL_URL = "https://api.github.com/user/emails"


def github_configured() -> bool:
    return bool(os.getenv("GITHUB_CLIENT_ID") and os.getenv("GITHUB_CLIENT_SECRET"))


def github_auth_url(redirect_uri: str, state: str) -> str:
    params = {
        "client_id":    _require_env("GITHUB_CLIENT_ID"),
        "redirect_uri": redirect_uri,
        "scope":        "read:user user:email",
        "state":        state,
    }
    return f"{_GITHUB_AUTH_URL}?{urllib.parse.urlencode(params)}"


async def exchange_github_code(code: str, redirect_uri: str) -> dict:
    """Exchange an auth code for {email, name, sub}."""
    async with aiohttp.ClientSession() as http:
        async with http.post(
            _GITHUB_TOKEN_URL,
            data={
                "code":          code,
                "client_id":     _require_env("GITHUB_CLIENT_ID"),
                "client_secret": _require_env("GITHUB_CLIENT_SECRET"),
                "redirect_uri":  redirect_uri,
            },
            headers={"Accept": "application/json"},
        ) as resp:
            token_data = await resp.json()
            if "access_token" not in token_data:
                raise ValueError(
                    f"GitHub token exchange failed: "
                    f"{token_data.get('error_description', token_data)}"
                )
            access_token = token_data["access_token"]

        gh_headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept":        "application/vnd.github+json",
        }

        async with http.get(_GITHUB_USER_URL, headers=gh_headers) as resp:
            user_data = await resp.json()

        # GitHub may hide the email on the user endpoint — fetch the emails list
        email: Optional[str] = user_data.get("email")
        if not email:
            async with http.get(_GITHUB_EMAIL_URL, headers=gh_headers) as resp:
                emails = await resp.json()
            email = next(
                (e["email"] for e in emails if e.get("primary") and e.get("verified")),
                next((e["email"] for e in emails if e.get("verified")), None),
            )

    if not email:
        raise ValueError("GitHub account has no verified email address")

    return {
        "email": email,
        "name":  user_data.get("name") or user_data.get("login") or "GitHub User",
        "sub":   str(user_data.get("id", "")),
    }
