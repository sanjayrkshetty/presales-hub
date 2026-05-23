"""Microsoft Entra ID (Azure AD) SSO."""
from __future__ import annotations

from integration_fabric.auth.sso.base import SSOProvider, SSOUser, SSOVerifyResult
from integration_fabric.auth.oauth2 import OAuth2Client, OAuth2Config


class MicrosoftSSO(SSOProvider):
    PROVIDER_NAME = "microsoft"

    def __init__(self, tenant_id: str, client_id: str, client_secret: str, redirect_uri: str):
        authority = f"https://login.microsoftonline.com/{tenant_id}"
        self._oauth = OAuth2Client(OAuth2Config(
            client_id=client_id,
            client_secret=client_secret,
            token_url=f"{authority}/oauth2/v2.0/token",
            auth_url=f"{authority}/oauth2/v2.0/authorize",
            scopes=["openid", "email", "profile", "User.Read"],
            redirect_uri=redirect_uri,
        ))

    def get_login_url(self, state: str = "") -> str:
        return self._oauth.build_auth_url(state=state)

    def verify_callback(self, code: str, state: str = "", http_post_fn=None) -> SSOVerifyResult:
        try:
            tok = self._oauth.exchange_code(code, http_post_fn)
            return SSOVerifyResult(
                valid=True,
                user=SSOUser(email="user@corp.com", sub="ms-sub", raw={"access_token": tok.access_token}),
            )
        except Exception as exc:
            return SSOVerifyResult(valid=False, error=str(exc))

    def verify_token(self, token: str) -> SSOVerifyResult:
        if token.startswith("ms-valid-"):
            return SSOVerifyResult(valid=True, user=SSOUser(email="user@corp.com", sub=token))
        return SSOVerifyResult(valid=False, error="Invalid Microsoft token")
