import asyncio
import logging
from fastapi import WebSocket
from events.redis_client import REDIS_URL, EVENTS_CHANNEL

logger = logging.getLogger("events.broadcaster")

_RECONNECT_MAX = 60  # seconds


class WebSocketBroadcaster:
    """Async Redis subscriber that fans out events to all connected WebSocket clients."""

    def __init__(self):
        self._clients: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def register(self, ws: WebSocket) -> None:
        async with self._lock:
            self._clients.add(ws)
        logger.debug("WS registered. Total: %d", len(self._clients))

    async def unregister(self, ws: WebSocket) -> None:
        async with self._lock:
            self._clients.discard(ws)
        logger.debug("WS unregistered. Total: %d", len(self._clients))

    async def fanout(self, message: str) -> None:
        if not self._clients:
            return
        async with self._lock:
            snapshot = set(self._clients)
        dead: set[WebSocket] = set()
        for ws in snapshot:
            try:
                await ws.send_text(message)
            except Exception:
                dead.add(ws)
        if dead:
            async with self._lock:
                self._clients -= dead

    async def start_redis_listener(self) -> None:
        """Long-running coroutine: subscribes to Redis and fans out messages.
        Reconnects with exponential backoff on any failure.
        Designed to run as an asyncio background task from FastAPI lifespan.
        """
        backoff = 1
        while True:
            try:
                import redis.asyncio as aioredis
                r = await aioredis.from_url(REDIS_URL, decode_responses=True)
                pubsub = r.pubsub()
                await pubsub.subscribe(EVENTS_CHANNEL)
                logger.info("Redis subscriber listening on %s", EVENTS_CHANNEL)
                backoff = 1
                async for message in pubsub.listen():
                    if message["type"] == "message":
                        await self.fanout(message["data"])
            except asyncio.CancelledError:
                logger.info("Redis listener cancelled")
                return
            except ImportError:
                logger.warning("redis[asyncio] not installed — WS push disabled")
                return
            except Exception as exc:
                logger.warning(
                    "Redis subscriber disconnected: %s. Reconnecting in %ds…", exc, backoff
                )
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, _RECONNECT_MAX)


broadcaster = WebSocketBroadcaster()
