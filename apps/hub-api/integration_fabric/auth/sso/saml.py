"""
SAML 2.0 — architecture stub.

Full SAML requires pysaml2 or python3-saml. This module provides the
interface and wiring so any SAML IdP can be plugged in by supplying
a real assertion parser.
"""
from __future__ import annotations

from dataclasses import dataclass
from integration_fabric.auth.sso.base import SSOProvider, SSOUser, SSOVerifyResult


@dataclass
class SAMLConfig:
    idp_metadata_url: str
    sp_entity_id: str
    sp_acs_url: str              # Assertion Consumer Service URL
    idp_sso_url: str = ""
    idp_cert: str = ""
    name_id_format: str = "urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress"


class SAMLProvider(SSOProvider):
    """
    SAML 2.0 SP-initiated SSO.
    Production: integrate python3-saml or pysaml2 behind parse_assertion().
    """
    PROVIDER_NAME = "saml"

    def __init__(self, config: SAMLConfig):
        self.config = config

    def get_login_url(self, state: str = "") -> str:
        params = f"?RelayState={state}" if state else ""
        return self.config.idp_sso_url + params

    def verify_callback(self, saml_response: str, state: str = "") -> SSOVerifyResult:
        return self.parse_assertion(saml_response)

    def verify_token(self, token: str) -> SSOVerifyResult:
        return SSOVerifyResult(valid=False, error="SAML does not use bearer tokens — use verify_callback")

    def parse_assertion(self, saml_response_b64: str) -> SSOVerifyResult:
        """
        Override in production to parse and validate the SAML assertion.
        Stub returns invalid — forces explicit implementation.
        """
        return SSOVerifyResult(valid=False, error="SAML assertion parsing not implemented — plug in python3-saml")

    def generate_metadata(self) -> str:
        """Return SP metadata XML for IdP registration."""
        return f"""<?xml version="1.0"?>
<md:EntityDescriptor xmlns:md="urn:oasis:names:tc:SAML:2.0:metadata"
    entityID="{self.config.sp_entity_id}">
  <md:SPSSODescriptor AuthnRequestsSigned="false" WantAssertionsSigned="true"
      protocolSupportEnumeration="urn:oasis:names:tc:SAML:2.0:protocol">
    <md:AssertionConsumerService
        Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST"
        Location="{self.config.sp_acs_url}" index="1"/>
  </md:SPSSODescriptor>
</md:EntityDescriptor>"""
