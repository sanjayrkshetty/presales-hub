"""
OAuth2 flow support.

Covers:
- Authorization Code flow (user-facing)
- Client Credentials flow (machine-to-machine)
- Token refresh
- PKCE extension (for public clients)
"""
from __future__ import annotations

import base64
import hashlib
import os
import time
import urllib.parse
from dataclasses import dataclass
from typing import Optional


@dataclass
class OAuth2Config:
    client_id: str
    client_secret: str
    token_url: str
    auth_url: str = ""
    scopes: list[str] = None
    redirect_uri: str = ""
    use_pkce: bool = False

    def __post_init__(self):
        if self.scopes is None:
            self.scopes = []


@dataclass
class TokenResponse:
    access_token: str
    token_type: str = "Bearer"
    expires_in: int = 3600
    refresh_token: Optional[str] = None
    scope: str = ""
    issued_at: float = None

    def __post_init__(self):
        if self.issued_at is None:
            self.issued_at = time.time()

    @property
    def expires_at(self) -> float:
        return self.issued_at + self.expires_in

    def is_expired(self, buffer_s: int = 60) -> bool:
        return time.time() >= self.expires_at - buffer_s


class OAuth2Client:
    """Thin OAuth2 client. Does NOT make real HTTP calls — delegates to subclass or test mock."""

    def __init__(self, config: OAuth2Config):
        self.config = config
        self._token: Optional[TokenResponse] = None
        self._pkce_verifier: Optional[str] = None

    # ── Authorization Code flow ────────────────────────────────────────────────

    def build_auth_url(self, state: str = "") -> str:
        params = {
            "client_id": self.config.client_id,
            "redirect_uri": self.config.redirect_uri,
            "response_type": "code",
            "scope": " ".join(self.config.scopes),
            "state": state,
        }
        if self.config.use_pkce:
            verifier = base64.urlsafe_b64encode(os.urandom(32)).rstrip(b"=").decode()
            self._pkce_verifier = verifier
            challenge = base64.urlsafe_b64encode(
                hashlib.sha256(verifier.encode()).digest()
            ).rstrip(b"=").decode()
            params["code_challenge"] = challenge
            params["code_challenge_method"] = "S256"
        return self.config.auth_url + "?" + urllib.parse.urlencode(params)

    def exchange_code(self, code: str, http_post_fn=None) -> TokenResponse:
        """Exchange authorization code for tokens."""
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.config.redirect_uri,
            "client_id": self.config.client_id,
            "client_secret": self.config.client_secret,
        }
        if self._pkce_verifier:
            data["code_verifier"] = self._pkce_verifier
        return self._post_token(data, http_post_fn)

    # ── Client Credentials flow ────────────────────────────────────────────────

    def client_credentials(self, http_post_fn=None) -> TokenResponse:
        data = {
            "grant_type": "client_credentials",
            "client_id": self.config.client_id,
            "client_secret": self.config.client_secret,
            "scope": " ".join(self.config.scopes),
        }
        return self._post_token(data, http_post_fn)

    def refresh(self, refresh_token: str, http_post_fn=None) -> TokenResponse:
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": self.config.client_id,
            "client_secret": self.config.client_secret,
        }
        return self._post_token(data, http_post_fn)

    def _post_token(self, data: dict, http_post_fn) -> TokenResponse:
        """
        If http_post_fn is provided, call it with (url, data) and expect a dict response.
        Otherwise return a stub for offline use / tests.
        """
        if http_post_fn is not None:
            resp = http_post_fn(self.config.token_url, data)
            tok = TokenResponse(
                access_token=resp.get("access_token", ""),
                token_type=resp.get("token_type", "Bearer"),
                expires_in=int(resp.get("expires_in", 3600)),
                refresh_token=resp.get("refresh_token"),
                scope=resp.get("scope", ""),
            )
        else:
            tok = TokenResponse(
                access_token="stub-token",
                expires_in=3600,
                refresh_token="stub-refresh",
            )
        self._token = tok
        return tok

    def get_valid_token(self, http_post_fn=None) -> TokenResponse:
        if self._token and not self._token.is_expired():
            return self._token
        if self._token and self._token.refresh_token:
            return self.refresh(self._token.refresh_token, http_post_fn)
        return self.client_credentials(http_post_fn)
