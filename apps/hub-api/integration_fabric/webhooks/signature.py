"""
HMAC-SHA256 webhook signature verification.

Inbound: verify that request body matches X-Hub-Signature-256 header.
Outbound: sign payloads before delivery.
"""
from __future__ import annotations

import hashlib
import hmac


def sign_payload(body: bytes, secret: str) -> str:
    """Returns 'sha256=<hex_digest>'."""
    mac = hmac.new(secret.encode("utf-8"), body, hashlib.sha256)
    return f"sha256={mac.hexdigest()}"


def verify_signature(body: bytes, secret: str, signature_header: str) -> bool:
    """
    Constant-time comparison of expected vs received signature.
    signature_header format: 'sha256=<hex>'
    """
    if not signature_header or not secret:
        return False
    expected = sign_payload(body, secret)
    return hmac.compare_digest(expected, signature_header)


def extract_hex(signature_header: str) -> str:
    """Strip 'sha256=' prefix."""
    if signature_header.startswith("sha256="):
        return signature_header[7:]
    return signature_header
