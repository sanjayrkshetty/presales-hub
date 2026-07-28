"""
Rule-based scrubber for proposal / RFP text.

Removes or replaces emails, phones, amounts, URLs, person titles, and known org markers.
Keeps structure and generic service language for RAG + scrubbed-only cloud chat.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_PHONE = re.compile(
    r"(?:\+?\d{1,3}[-.\s]?)?(?:\(?\d{2,4}\)?[-.\s]?)?\d{3,4}[-.\s]?\d{4}\b"
)
_AMOUNT = re.compile(
    r"(?:(?:INR|USD|EUR|GBP|Rs\.?|₹|\$)\s*)?\d{1,3}(?:,\d{2,3})+(?:\.\d+)?\s*(?:cr|CR|lakh|L|million|M)?",
    re.IGNORECASE,
)
_URL = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
_BRANDS = [
    re.compile(r"\bSISA\b", re.IGNORECASE),
    re.compile(r"\bSISA Information Security\b", re.IGNORECASE),
]
_PERSON = re.compile(
    r"\b(?:Mr|Mrs|Ms|Dr|Prof)\.?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b"
)


@dataclass
class ScrubResult:
    text: str
    replacements: int = 0
    flags: list[str] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return self.replacements > 0


def scrub_text(text: str) -> ScrubResult:
    if not text:
        return ScrubResult(text="")

    out = text
    n = 0
    flags: list[str] = []

    def _sub(pattern: re.Pattern, repl: str, flag: str) -> None:
        nonlocal out, n
        out2, c = pattern.subn(repl, out)
        if c:
            out = out2
            n += c
            if flag not in flags:
                flags.append(flag)

    _sub(_EMAIL, "{{EMAIL}}", "email")
    _sub(_PHONE, "{{PHONE}}", "phone")
    _sub(_AMOUNT, "{{AMOUNT}}", "amount")
    _sub(_URL, "{{URL}}", "url")
    _sub(_PERSON, "{{PERSON}}", "person")
    for brand in _BRANDS:
        _sub(brand, "{{ORG}}", "org")

    return ScrubResult(text=out, replacements=n, flags=flags)
