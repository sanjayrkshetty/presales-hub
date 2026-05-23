"""
SSO provider abstraction.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SSOUser:
    email: str
    sub: str                        # provider-unique subject ID
    name: str = ""
    given_name: str = ""
    family_name: str = ""
    groups: list[str] = field(default_factory=list)
    tenant_id: Optional[str] = None
    raw: dict = field(default_factory=dict)


@dataclass
class SSOVerifyResult:
    valid: bool
    user: Optional[SSOUser] = None
    error: Optional[str] = None


class SSOProvider(ABC):
    """
    Abstract SSO provider.
    Concrete implementations: GoogleSSO, MicrosoftSSO, OktaSSO, SAMLProvider.
    """
    PROVIDER_NAME: str = ""

    @abstractmethod
    def get_login_url(self, state: str = "") -> str:
        """Build the IdP redirect URL for user login."""

    @abstractmethod
    def verify_callback(self, code: str, state: str = "") -> SSOVerifyResult:
        """Exchange authorization code for identity claims."""

    @abstractmethod
    def verify_token(self, token: str) -> SSOVerifyResult:
        """Verify a bearer/ID token and extract identity."""

    def provider_name(self) -> str:
        return self.PROVIDER_NAME
