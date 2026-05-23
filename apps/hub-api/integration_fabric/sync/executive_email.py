"""Executive summary → email digest sync."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


@dataclass
class EmailDigestResult:
    emails_sent: int = 0
    recipients: list[str] = None
    errors: list[str] = None

    def __post_init__(self):
        if self.emails_sent is None:
            self.emails_sent = 0
        if self.recipients is None:
            self.recipients = []
        if self.errors is None:
            self.errors = []


def send_executive_digest(
    db: "Session",
    email_connector,
    recipients: list[str],
    period_label: str = "current",
    dry_run: bool = False,
) -> EmailDigestResult:
    from strategic_intelligence.executive.summary_generator import generate_executive_summary
    from dataclasses import asdict

    result = EmailDigestResult()
    summary = generate_executive_summary(db, period_label=period_label)

    subject = f"[PRESALES HUB] Executive Summary — {period_label}"
    body = _format_digest(summary)

    if not dry_run:
        push = email_connector.send_email(to=recipients, subject=subject, body=body, is_html=True)
        if push.success:
            result.emails_sent = 1
            result.recipients = recipients
        else:
            result.errors.append(f"Email send failed: {push.error}")
    else:
        result.emails_sent = 1
        result.recipients = recipients

    return result


def _format_digest(summary) -> str:
    lines = [
        "<h2>Executive Presales Summary</h2>",
        f"<p><b>Period:</b> {summary.period_label}</p>",
        f"<p><b>Pipeline Health:</b> {summary.pipeline_health_label.upper()} "
        f"({summary.pipeline_health_score:.0f}/100)</p>",
        f"<p><b>Forecast:</b> {summary.weighted_forecast_cr:.2f} Cr (weighted)</p>",
        f"<p><b>At-Risk:</b> {summary.at_risk_count} proposals</p>",
        f"<p><b>Delivery Readiness:</b> {summary.delivery_readiness}</p>",
        "<h3>Top Recommendations</h3><ul>",
    ]
    for rec in summary.top_recommendations[:3]:
        lines.append(f"<li>[{rec.get('priority', '').upper()}] {rec.get('title', '')}</li>")
    lines.append("</ul>")
    lines.append(f"<p><i>Generated: {summary.generated_at}</i></p>")
    return "\n".join(lines)
