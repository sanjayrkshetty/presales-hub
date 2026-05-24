import logging
from events.redis_client import sync_client, EVENTS_CHANNEL
from events.schema import BaseEvent
from telemetry.context import get_correlation_id
from telemetry.tracing import trace_span
from telemetry.prometheus import event_publishes_total

logger = logging.getLogger("events.bus")


def publish(event: BaseEvent) -> None:
    """
    Publish a domain event to Redis.

    Behaviour:
    - Injects current correlation_id from context if the event doesn't carry one
    - Wraps the Redis publish call in an OTel child span for event lineage
    - Falls back to DLQ persistence if Redis is unavailable
    """
    if not event.correlation_id:
        cid = get_correlation_id()
        if cid:
            event = event.model_copy(update={"correlation_id": cid})

    if sync_client is None:
        event_publishes_total.labels(channel=EVENTS_CHANNEL, status="dropped").inc()
        return

    with trace_span(
        "redis.publish",
        event_type=event.event_type,
        entity_id=event.entity_id,
        entity_type=event.entity_type,
    ):
        try:
            sync_client.publish(EVENTS_CHANNEL, event.to_json())
            event_publishes_total.labels(channel=EVENTS_CHANNEL, status="success").inc()
            logger.debug(
                "Event published",
                extra={
                    "event_type": event.event_type,
                    "entity_id": event.entity_id,
                    "correlation_id": event.correlation_id,
                },
            )
        except Exception as exc:
            event_publishes_total.labels(channel=EVENTS_CHANNEL, status="dlq").inc()
            logger.warning(
                "Event publish failed — persisting to DLQ",
                extra={"event_type": event.event_type, "error": str(exc)},
            )
            # Late import avoids circular dependency at module load
            from events.dead_letter import persist_failed_event
            persist_failed_event(EVENTS_CHANNEL, event.to_json(), str(exc))
