import logging
from events.redis_client import sync_client, EVENTS_CHANNEL
from events.schema import BaseEvent

logger = logging.getLogger("events.bus")


def publish(event: BaseEvent) -> None:
    """Publish a domain event to Redis. Silently drops if Redis is unavailable."""
    if sync_client is None:
        return
    try:
        sync_client.publish(EVENTS_CHANNEL, event.to_json())
        logger.debug("Published %s entity=%s", event.event_type, event.entity_id)
    except Exception as exc:
        logger.warning("Event publish failed (%s): %s", event.event_type, exc)
