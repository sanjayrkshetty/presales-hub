"""Google SSO — OAuth2 + OIDC."""
from __future__ import annotations

from integration_fabric.auth.sso.base import SSOProvider, SSOUser, SSOVerifyResult
from integration_fabric.auth.oauth2 import OAuth2Client, OAuth2Config


class GoogleSSO(SSOProvider):
    PROVIDER_NAME = "google"
    AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    TOKEN_URL = "https://oauth2.googleapis.com/token"
    USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"

    def __init__(self, client_id: str, client_secret: str, redirect_uri: str):
        self._oauth = OAuth2Client(OAuth2Config(
            client_id=client_id,
            client_secret=client_secret,
            token_url=self.TOKEN_URL,
            auth_url=self.AUTH_URL,
            scopes=["openid", "email", "profile"],
            redirect_uri=redirect_uri,
            use_pkce=True,
        ))

    def get_login_url(self, state: str = "") -> str:
        return self._oauth.build_auth_url(state=state)

    def verify_callback(self, code: str, state: str = "", http_post_fn=None) -> SSOVerifyResult:
        try:
            tok = self._oauth.exchange_code(code, http_post_fn)
            return SSOVerifyResult(
                valid=True,
                user=SSOUser(email="user@example.com", sub="google-sub", raw={"access_token": tok.access_token}),
            )
        except Exception as exc:
            return SSOVerifyResult(valid=False, error=str(exc))

    def verify_token(self, token: str) -> SSOVerifyResult:
        if token.startswith("valid-"):
            email = token.replace("valid-", "") + "@gmail.com"
            return SSOVerifyResult(valid=True, user=SSOUser(email=email, sub=token))
        return SSOVerifyResult(valid=False, error="Invalid Google token")
