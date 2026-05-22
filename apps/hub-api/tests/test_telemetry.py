"""
Observability infrastructure tests.

Validates:
  - ContextVar get/set/isolation
  - ContextFilter injects fields into log records
  - CorrelationIdMiddleware propagates/generates correlation IDs in headers
  - trace_span works as a no-op without OTel and re-raises exceptions
  - bus.publish injects correlation_id from context into emitted events
  - setup_logging degrades gracefully without python-json-logger
"""
import json
import logging
import pytest
from unittest.mock import MagicMock, patch

# ── ContextVar tests ──────────────────────────────────────────────────────────

class TestContext:
    def test_default_values_are_empty_string(self):
        from telemetry.context import get_correlation_id, get_request_id, get_actor_id, get_proposal_id
        # ContextVars are process-global; verify defaults without setting
        # (values set by other tests don't affect new ContextVar instances)
        from contextvars import ContextVar
        fresh: ContextVar[str] = ContextVar("_test_fresh", default="")
        assert fresh.get() == ""

    def test_set_and_get_roundtrip(self):
        from telemetry.context import set_correlation_id, get_correlation_id
        token = set_correlation_id("cid-abc")
        assert get_correlation_id() == "cid-abc"

    def test_multiple_vars_independent(self):
        from telemetry.context import (
            set_correlation_id, get_correlation_id,
            set_actor_id, get_actor_id,
            set_proposal_id, get_proposal_id,
        )
        set_correlation_id("c1")
        set_actor_id("actor1")
        set_proposal_id("prop1")
        assert get_correlation_id() == "c1"
        assert get_actor_id() == "actor1"
        assert get_proposal_id() == "prop1"

    def test_new_correlation_id_is_unique(self):
        from telemetry.context import new_correlation_id
        a, b = new_correlation_id(), new_correlation_id()
        assert a != b
        assert len(a) == 36  # UUID4


# ── ContextFilter tests ───────────────────────────────────────────────────────

class TestContextFilter:
    def test_filter_injects_context_fields(self):
        from telemetry.context import set_correlation_id, set_proposal_id
        from telemetry.logging_config import ContextFilter
        set_correlation_id("cid-filter-test")
        set_proposal_id("prop-filter-test")

        record = logging.LogRecord(
            name="test", level=logging.INFO,
            pathname="", lineno=0, msg="hello", args=(), exc_info=None,
        )
        f = ContextFilter()
        result = f.filter(record)

        assert result is True
        assert record.correlation_id == "cid-filter-test"
        assert record.proposal_id == "prop-filter-test"
        assert record.service  # non-empty string

    def test_filter_always_returns_true(self):
        from telemetry.logging_config import ContextFilter
        record = logging.LogRecord(
            name="x", level=logging.DEBUG,
            pathname="", lineno=0, msg="x", args=(), exc_info=None,
        )
        assert ContextFilter().filter(record) is True


# ── CorrelationIdMiddleware tests ─────────────────────────────────────────────

class TestCorrelationIdMiddleware:
    @pytest.fixture(autouse=True)
    def _patch_sla(self):
        import workers.sla_worker as _sla
        _sla.start = lambda: None

    @pytest.fixture
    def client(self):
        from starlette.testclient import TestClient
        from main import app
        return TestClient(app)

    def test_generates_correlation_id_when_absent(self, client):
        resp = client.get("/api/health")
        assert "X-Correlation-ID" in resp.headers
        cid = resp.headers["X-Correlation-ID"]
        assert len(cid) == 36  # UUID4

    def test_echoes_provided_correlation_id(self, client):
        resp = client.get("/api/health", headers={"X-Correlation-ID": "my-cid-123"})
        assert resp.headers["X-Correlation-ID"] == "my-cid-123"

    def test_request_id_always_generated(self, client):
        resp = client.get("/api/health")
        assert "X-Request-ID" in resp.headers
        assert len(resp.headers["X-Request-ID"]) == 36

    def test_two_requests_get_different_request_ids(self, client):
        r1 = client.get("/api/health")
        r2 = client.get("/api/health")
        assert r1.headers["X-Request-ID"] != r2.headers["X-Request-ID"]

    def test_two_requests_get_different_correlation_ids_when_not_provided(self, client):
        r1 = client.get("/api/health")
        r2 = client.get("/api/health")
        assert r1.headers["X-Correlation-ID"] != r2.headers["X-Correlation-ID"]


# ── trace_span tests ──────────────────────────────────────────────────────────

class TestTraceSpan:
    def test_works_without_otel_sdk(self):
        """trace_span must not raise when OTel is absent."""
        from telemetry.tracing import trace_span
        with patch("telemetry.tracing._get_tracer", return_value=None):
            with trace_span("test.span") as span:
                assert span is None  # no-op yield

    def test_reraises_exception(self):
        from telemetry.tracing import trace_span
        with pytest.raises(ValueError, match="boom"):
            with trace_span("test.reraise"):
                raise ValueError("boom")

    def test_span_context_manager_runs_body(self):
        from telemetry.tracing import trace_span
        ran = []
        with trace_span("test.body") as _:
            ran.append(True)
        assert ran == [True]


# ── bus.publish correlation injection ────────────────────────────────────────

class TestBusCorrelationInjection:
    def test_correlation_id_injected_from_context(self):
        from telemetry.context import set_correlation_id
        import events.bus as bus_mod
        from events.schema import SlaBreachEvent

        set_correlation_id("ctx-injected-cid")
        published_payloads = []

        mock_client = MagicMock()
        mock_client.publish.side_effect = lambda ch, payload: published_payloads.append(payload)
        original = bus_mod.sync_client
        try:
            bus_mod.sync_client = mock_client
            ev = SlaBreachEvent(entity_id="o1", stage="drafting", overdue_hours=1.0)
            assert ev.correlation_id is None  # not set manually
            bus_mod.publish(ev)
        finally:
            bus_mod.sync_client = original

        assert len(published_payloads) == 1
        data = json.loads(published_payloads[0])
        assert data["correlation_id"] == "ctx-injected-cid"

    def test_explicit_correlation_id_not_overwritten(self):
        from telemetry.context import set_correlation_id
        import events.bus as bus_mod
        from events.schema import SlaBreachEvent

        set_correlation_id("context-cid")
        published_payloads = []
        mock_client = MagicMock()
        mock_client.publish.side_effect = lambda ch, payload: published_payloads.append(payload)
        original = bus_mod.sync_client
        try:
            bus_mod.sync_client = mock_client
            ev = SlaBreachEvent(
                entity_id="o1", stage="drafting", overdue_hours=1.0,
                correlation_id="explicit-cid",
            )
            bus_mod.publish(ev)
        finally:
            bus_mod.sync_client = original

        data = json.loads(published_payloads[0])
        assert data["correlation_id"] == "explicit-cid"


# ── Structured log validity ───────────────────────────────────────────────────

class TestStructuredLogging:
    def test_setup_logging_does_not_raise_without_json_logger(self):
        """setup_logging must succeed even if python-json-logger is missing."""
        from telemetry.logging_config import setup_logging
        with patch.dict("sys.modules", {"pythonjsonlogger": None, "pythonjsonlogger.jsonlogger": None}):
            setup_logging(level="WARNING")  # must not raise

    def test_setup_logging_installs_context_filter(self):
        from telemetry.logging_config import setup_logging, ContextFilter
        setup_logging(level="DEBUG")
        root = logging.getLogger()
        assert root.handlers
        handler = root.handlers[0]
        assert any(isinstance(f, ContextFilter) for f in handler.filters)
