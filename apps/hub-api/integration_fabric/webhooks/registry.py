"""
Webhook subscription registry.

Subscriptions are persisted in the DB (WebhookSubscription model).
This module provides CRUD + filtering by event type.
"""
from __future__ import annotations

import secrets
import uuid
from datetime import datetime
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def generate_secret() -> str:
    return secrets.token_hex(32)


def create_subscription(
    db: "Session",
    tenant_id: str,
    target_url: str,
    event_types: list[str],
    secret: Optional[str] = None,
) -> "WebhookSubscription":
    from models.integration import WebhookSubscription
    sub = WebhookSubscription(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        target_url=target_url,
        event_types=event_types,
        secret=secret or generate_secret(),
        active=True,
        created_at=datetime.utcnow(),
    )
    db.add(sub)
    db.flush()
    return sub


def get_subscription(db: "Session", subscription_id: str) -> Optional["WebhookSubscription"]:
    from models.integration import WebhookSubscription
    return db.get(WebhookSubscription, subscription_id)


def list_subscriptions(db: "Session", tenant_id: str, active_only: bool = True) -> list:
    from sqlalchemy import select
    from models.integration import WebhookSubscription
    q = select(WebhookSubscription).where(WebhookSubscription.tenant_id == tenant_id)
    if active_only:
        q = q.where(WebhookSubscription.active == True)  # noqa: E712
    return list(db.scalars(q).all())


def subscriptions_for_event(db: "Session", tenant_id: str, event_type: str) -> list:
    """Return active subscriptions that listen to event_type."""
    subs = list_subscriptions(db, tenant_id)
    return [s for s in subs if not s.event_types or event_type in s.event_types]


def deactivate_subscription(db: "Session", subscription_id: str) -> bool:
    from models.integration import WebhookSubscription
    sub = db.get(WebhookSubscription, subscription_id)
    if sub:
        sub.active = False
        db.flush()
        return True
    return False


def rotate_secret(db: "Session", subscription_id: str) -> Optional[str]:
    from models.integration import WebhookSubscription
    sub = db.get(WebhookSubscription, subscription_id)
    if sub:
        new_secret = generate_secret()
        sub.secret = new_secret
        db.flush()
        return new_secret
    return None
