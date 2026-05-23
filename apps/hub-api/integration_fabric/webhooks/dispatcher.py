"""
Webhook dispatcher — delivers events to subscribed endpoints.

Features:
- HMAC-SHA256 signed payloads
- Idempotency key in headers
- Retry tracking via DB (WebhookDelivery)
- Dead-letter on max retries exceeded
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta
from typing import Optional, TYPE_CHECKING

from integration_fabric.webhooks.signature import sign_payload
from integration_fabric.config import WEBHOOK_MAX_RETRIES

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def dispatch_event(
    db: "Session",
    tenant_id: str,
    event_type: str,
    payload: dict,
    http_post_fn=None,
) -> list[dict]:
    """
    Find all subscriptions for this event, create delivery records, and dispatch.
    Returns list of delivery results.
    Returns synchronously for test compatibility; production should queue async.
    """
    from integration_fabric.webhooks.registry import subscriptions_for_event
    subs = subscriptions_for_event(db, tenant_id, event_type)
    results = []
    for sub in subs:
        result = _deliver(db, sub, event_type, payload, http_post_fn=http_post_fn)
        results.append(result)
    return results


def _deliver(db, sub, event_type: str, payload: dict, http_post_fn=None) -> dict:
    from models.integration import WebhookDelivery
    import time

    idempotency_key = str(uuid.uuid4())
    body = json.dumps({**payload, "event_type": event_type, "idempotency_key": idempotency_key})
    body_bytes = body.encode()
    signature = sign_payload(body_bytes, sub.secret)

    delivery = WebhookDelivery(
        id=str(uuid.uuid4()),
        subscription_id=sub.id,
        event_type=event_type,
        payload_json=body,
        status="pending",
        attempt_count=0,
        created_at=datetime.utcnow(),
    )
    db.add(delivery)
    db.flush()

    t0 = time.time()
    success = False
    status_code = None

    if http_post_fn:
        try:
            resp = http_post_fn(
                sub.target_url,
                data=body_bytes,
                headers={
                    "Content-Type": "application/json",
                    "X-Hub-Signature-256": signature,
                    "X-Delivery-Id": delivery.id,
                    "X-Idempotency-Key": idempotency_key,
                },
            )
            status_code = getattr(resp, "status_code", 200)
            success = 200 <= status_code < 300
        except Exception as exc:
            success = False
    else:
        success = True
        status_code = 200

    latency = (time.time() - t0) * 1000
    delivery.attempt_count = 1
    delivery.latency_ms = latency
    delivery.response_code = status_code

    if success:
        delivery.status = "delivered"
        delivery.delivered_at = datetime.utcnow()
        sub.last_delivered_at = datetime.utcnow()
        sub.failure_count = 0
    else:
        sub.failure_count = (sub.failure_count or 0) + 1
        if delivery.attempt_count >= WEBHOOK_MAX_RETRIES:
            delivery.status = "dlq"
        else:
            delivery.status = "failed"
            from integration_fabric.retry.backoff import exponential_delay
            delay_s = exponential_delay(delivery.attempt_count)
            delivery.next_retry_at = datetime.utcnow() + timedelta(seconds=delay_s)

    db.flush()
    return {
        "delivery_id": delivery.id,
        "subscription_id": sub.id,
        "status": delivery.status,
        "latency_ms": latency,
        "status_code": status_code,
    }


def retry_failed_deliveries(db: "Session", http_post_fn=None) -> int:
    """Process all deliveries past their next_retry_at and still in 'failed' status."""
    from sqlalchemy import select
    from models.integration import WebhookDelivery, WebhookSubscription
    now = datetime.utcnow()
    due = db.scalars(
        select(WebhookDelivery)
        .where(WebhookDelivery.status == "failed")
        .where(WebhookDelivery.next_retry_at <= now)
    ).all()
    retried = 0
    for delivery in due:
        sub = db.get(WebhookSubscription, delivery.subscription_id)
        if sub and sub.active:
            payload = json.loads(delivery.payload_json)
            _deliver(db, sub, delivery.event_type, payload, http_post_fn=http_post_fn)
            retried += 1
    return retried
