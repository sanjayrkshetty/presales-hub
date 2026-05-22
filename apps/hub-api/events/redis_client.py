import logging
import os

logger = logging.getLogger("events.redis")

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
EVENTS_CHANNEL = "presales:events"


def _make_sync_client():
    try:
        import redis
        return redis.Redis.from_url(
            REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=1,
        )
    except ImportError:
        logger.warning("redis-py not installed — event publishing disabled")
        return None


# Module-level singleton. redis-py uses a connection pool internally;
# the actual TCP connection is lazy (established on first command).
sync_client = _make_sync_client()
