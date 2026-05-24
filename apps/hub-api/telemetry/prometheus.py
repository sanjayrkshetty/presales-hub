"""Prometheus metrics for Presales Hub.

Exposes /metrics in Prometheus text format.
Install: prometheus-client (already in requirements if added).

Metrics exposed:
- http_requests_total (counter, by method/path/status)
- http_request_duration_seconds (histogram)
- ws_connections_active (gauge)
- event_publishes_total (counter, by channel/status)
- dlq_events_pending (gauge)
- circuit_breaker_state (gauge, by name)
"""
import time
import logging
from typing import Callable

logger = logging.getLogger("telemetry.prometheus")

try:
    from prometheus_client import (
        Counter, Histogram, Gauge, CollectorRegistry,
        generate_latest, CONTENT_TYPE_LATEST,
    )
    _ENABLED = True
except ImportError:
    _ENABLED = False
    logger.info("prometheus_client not installed — /metrics endpoint disabled")


if _ENABLED:
    _registry = CollectorRegistry(auto_describe=True)

    http_requests_total = Counter(
        "hub_http_requests_total",
        "Total HTTP requests",
        ["method", "path", "status"],
        registry=_registry,
    )
    http_request_duration = Histogram(
        "hub_http_request_duration_seconds",
        "HTTP request latency",
        ["method", "path"],
        buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0],
        registry=_registry,
    )
    ws_connections_active = Gauge(
        "hub_ws_connections_active",
        "Active WebSocket connections",
        registry=_registry,
    )
    event_publishes_total = Counter(
        "hub_event_publishes_total",
        "Event publish attempts",
        ["channel", "status"],  # status: success | dlq | dropped
        registry=_registry,
    )
    dlq_events_pending = Gauge(
        "hub_dlq_events_pending",
        "Unresolved dead-letter queue events",
        registry=_registry,
    )
    circuit_breaker_open = Gauge(
        "hub_circuit_breaker_open",
        "Whether the circuit breaker is open (1) or closed (0)",
        ["name"],
        registry=_registry,
    )

    def get_metrics_response() -> tuple[bytes, str]:
        """Return (body, content_type) for the /metrics endpoint."""
        return generate_latest(_registry), CONTENT_TYPE_LATEST

    def record_request(method: str, path: str, status: int, duration: float) -> None:
        # Normalize path — strip UUIDs to avoid high-cardinality labels
        import re
        normalized = re.sub(r"/[0-9a-f-]{32,36}", "/{id}", path)
        http_requests_total.labels(method=method, path=normalized, status=str(status)).inc()
        http_request_duration.labels(method=method, path=normalized).observe(duration)

    def update_circuit_breaker_gauges() -> None:
        from core.circuit_breaker import all_breaker_statuses
        for s in all_breaker_statuses():
            circuit_breaker_open.labels(name=s["name"]).set(1 if s["state"] == "open" else 0)

else:
    def get_metrics_response() -> tuple[bytes, str]:
        return b"# prometheus_client not installed\n", "text/plain"

    def record_request(*args, **kwargs) -> None:
        pass

    def update_circuit_breaker_gauges() -> None:
        pass

    # Stub objects so import sites don't break
    class _Stub:
        def labels(self, **_): return self
        def inc(self): pass
        def observe(self, _): pass
        def set(self, _): pass

    ws_connections_active = _Stub()
    event_publishes_total = _Stub()
    dlq_events_pending = _Stub()
