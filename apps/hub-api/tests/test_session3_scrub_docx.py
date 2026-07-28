"""Unit tests for Session 3 scrub + docx builder (no auth, no network)."""
from memory_engine.scrub.scrubber import scrub_text
from memory_engine.docx_gen.builder import build_proposal_docx


def test_scrub_replaces_email_phone_amount_org():
    raw = (
        "Contact Mr. Jane Doe at jane.doe@example.com or +1-555-123-4567. "
        "Quote was INR 12,50,000 for SISA retainership. See https://example.com/x"
    )
    result = scrub_text(raw)
    assert result.changed
    assert "{{EMAIL}}" in result.text
    assert "{{PHONE}}" in result.text
    assert "{{AMOUNT}}" in result.text
    assert "{{ORG}}" in result.text
    assert "{{URL}}" in result.text
    assert "jane.doe@example.com" not in result.text


def test_scrub_passthrough_clean_text():
    text = "DFIR retainership covers triage, containment, and forensic imaging."
    result = scrub_text(text)
    assert result.text == text
    assert result.replacements == 0


def test_build_proposal_docx_bytes():
    blob = build_proposal_docx(
        "Demo DFIR Proposal",
        {
            "exec_summary": "Scrubbed grounded summary.",
            "scope": "Triage and containment.",
        },
    )
    assert isinstance(blob, (bytes, bytearray))
    assert len(blob) > 1000
    # DOCX is a zip — starts with PK
    assert blob[:2] == b"PK"
