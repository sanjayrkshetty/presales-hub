from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger("integration.events")


@dataclass
class IntegrationEvent:
    event_type: str
    tenant_id: str
    platform: str
    payload: dict
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    occurred_at: datetime = field(default_factory=datetime.utcnow)


def emit(event: IntegrationEvent, broadcaster=None) -> None:
    """Emit an integration event.

    In production wire *broadcaster* to the SSE broadcaster for real-time push.
    In test/sync contexts, log only (broadcaster is async, emit is sync).
    """
    logger.info(
        "integration_event",
        extra={
            "event_type": event.event_type,
            "event_id": event.event_id,
            "tenant_id": event.tenant_id,
            "platform": event.platform,
            "occurred_at": event.occurred_at.isoformat(),
        },
    )
