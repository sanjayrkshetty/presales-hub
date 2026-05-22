import logging
from events.redis_client import sync_client, EVENTS_CHANNEL
from events.schema import BaseEvent
from telemetry.context import get_correlation_id
from telemetry.tracing import trace_span

logger = logging.getLogger("events.bus")


def publish(event: BaseEvent) -> None:
    """
    Publish a domain event to Redis.

    Behaviour:
    - Injects current correlation_id from context if the event doesn't carry one
    - Wraps the Redis publish call in an OTel child span for event lineage
    - Silently drops if Redis is unavailable (no exception propagation)
    """
    if not event.correlation_id:
        cid = get_correlation_id()
        if cid:
            event = event.model_copy(update={"correlation_id": cid})

    if sync_client is None:
        return

    with trace_span(
        "redis.publish",
        event_type=event.event_type,
        entity_id=event.entity_id,
        entity_type=event.entity_type,
    ):
        try:
            sync_client.publish(EVENTS_CHANNEL, event.to_json())
            logger.debug(
                "Event published",
                extra={
                    "event_type": event.event_type,
                    "entity_id": event.entity_id,
                    "correlation_id": event.correlation_id,
                },
            )
        except Exception as exc:
            logger.warning(
                "Event publish failed",
                extra={"event_type": event.event_type, "error": str(exc)},
            )
