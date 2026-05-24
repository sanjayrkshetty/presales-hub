"""Simple circuit breaker for external AI/service calls.

States: CLOSED (normal) → OPEN (failing) → HALF_OPEN (testing recovery)

Usage:
    breaker = CircuitBreaker("anthropic", failure_threshold=5, recovery_timeout=60)

    async with breaker.guard():
        response = await anthropic_client.complete(...)
"""
import asyncio
import logging
import time
from contextlib import asynccontextmanager
from enum import Enum
from fastapi import HTTPException

logger = logging.getLogger("core.circuit_breaker")


class State(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        half_open_max_calls: int = 1,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls

        self._state = State.CLOSED
        self._failures = 0
        self._last_failure_time: float = 0
        self._half_open_calls = 0
        self._lock = asyncio.Lock()

    @property
    def state(self) -> State:
        return self._state

    async def _transition(self, new_state: State) -> None:
        if self._state != new_state:
            logger.info("Circuit '%s': %s → %s", self.name, self._state.value, new_state.value)
            self._state = new_state

    async def _on_success(self) -> None:
        async with self._lock:
            self._failures = 0
            self._half_open_calls = 0
            await self._transition(State.CLOSED)

    async def _on_failure(self, exc: Exception) -> None:
        async with self._lock:
            self._failures += 1
            self._last_failure_time = time.monotonic()
            logger.warning("Circuit '%s' failure #%d: %s", self.name, self._failures, exc)
            if self._failures >= self.failure_threshold:
                await self._transition(State.OPEN)

    async def _check_state(self) -> None:
        async with self._lock:
            if self._state == State.OPEN:
                elapsed = time.monotonic() - self._last_failure_time
                if elapsed >= self.recovery_timeout:
                    await self._transition(State.HALF_OPEN)
                    self._half_open_calls = 0
                else:
                    raise HTTPException(
                        status_code=503,
                        detail=f"Service '{self.name}' temporarily unavailable (circuit open). "
                               f"Retry in {int(self.recovery_timeout - elapsed)}s.",
                    )
            if self._state == State.HALF_OPEN:
                if self._half_open_calls >= self.half_open_max_calls:
                    raise HTTPException(
                        status_code=503,
                        detail=f"Service '{self.name}' recovering. Please retry shortly.",
                    )
                self._half_open_calls += 1

    @asynccontextmanager
    async def guard(self):
        await self._check_state()
        try:
            yield
            await self._on_success()
        except HTTPException:
            raise
        except Exception as exc:
            await self._on_failure(exc)
            raise

    def status(self) -> dict:
        return {
            "name": self.name,
            "state": self._state.value,
            "failures": self._failures,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout_s": self.recovery_timeout,
        }


# Singleton breakers for known external providers
_breakers: dict[str, CircuitBreaker] = {}


def get_breaker(name: str, **kwargs) -> CircuitBreaker:
    if name not in _breakers:
        _breakers[name] = CircuitBreaker(name, **kwargs)
    return _breakers[name]


def all_breaker_statuses() -> list[dict]:
    return [b.status() for b in _breakers.values()]


# Pre-register known providers
ai_breaker     = get_breaker("anthropic",      failure_threshold=5, recovery_timeout=60)
openai_breaker = get_breaker("openai",         failure_threshold=5, recovery_timeout=60)
groq_breaker   = get_breaker("groq",           failure_threshold=5, recovery_timeout=30)
temporal_breaker = get_breaker("temporal",     failure_threshold=3, recovery_timeout=30)
