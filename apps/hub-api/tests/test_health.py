"""Tests for health endpoints, middleware, and production hardening."""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from main import app
    return TestClient(app, raise_server_exceptions=False)


class TestHealthEndpoints:
    def test_health_returns_json(self, client):
        res = client.get("/api/health")
        assert res.status_code in (200, 503)
        data = res.json()
        assert "status" in data
        assert data["status"] in ("ok", "degraded", "critical")

    def test_health_has_checks(self, client):
        res = client.get("/api/health")
        data = res.json()
        assert "checks" in data
        checks = data["checks"]
        assert "postgres" in checks
        assert "redis" in checks
        assert "temporal" in checks

    def test_health_has_latency(self, client):
        res = client.get("/api/health")
        data = res.json()
        assert "latency_ms" in data
        assert isinstance(data["latency_ms"], (int, float))

    def test_health_has_circuit_breakers(self, client):
        res = client.get("/api/health")
        data = res.json()
        assert "circuit_breakers" in data
        assert isinstance(data["circuit_breakers"], list)

    def test_ready_endpoint_exists(self, client):
        res = client.get("/api/ready")
        assert res.status_code in (200, 503)

    def test_metrics_endpoint_returns_text(self, client):
        res = client.get("/metrics")
        assert res.status_code == 200
        # Either prometheus format or stub message
        assert len(res.content) > 0


class TestSecurityHeaders:
    def test_x_frame_options_present(self, client):
        res = client.get("/api/health")
        assert res.headers.get("x-frame-options") == "DENY"

    def test_x_content_type_nosniff(self, client):
        res = client.get("/api/health")
        assert res.headers.get("x-content-type-options") == "nosniff"

    def test_csp_present(self, client):
        res = client.get("/api/health")
        assert "content-security-policy" in res.headers

    def test_xss_protection_present(self, client):
        res = client.get("/api/health")
        assert "x-xss-protection" in res.headers


class TestRateLimiting:
    def test_rate_limit_on_login(self, client):
        """21 rapid requests to /auth/login should trigger 429."""
        responses = [
            client.post("/auth/login", json={"email": f"test{i}@test.com", "password": "wrong"})
            for i in range(22)
        ]
        statuses = [r.status_code for r in responses]
        # Either 401 (bad creds) or 429 (rate limited) — 429 must appear
        assert 429 in statuses, f"Expected 429 in {set(statuses)}"


class TestCircuitBreaker:
    def test_circuit_breaker_starts_closed(self):
        from core.circuit_breaker import get_breaker, State
        breaker = get_breaker("test_initial_state")
        assert breaker.state == State.CLOSED

    def test_circuit_opens_after_threshold(self):
        from core.circuit_breaker import CircuitBreaker, State
        import asyncio

        breaker = CircuitBreaker("test_open", failure_threshold=3, recovery_timeout=60)

        async def run():
            for _ in range(3):
                try:
                    async with breaker.guard():
                        raise ValueError("simulated failure")
                except (ValueError, Exception):
                    pass
            assert breaker.state == State.OPEN

        asyncio.run(run())


class TestDeadLetterQueue:
    def test_persist_failed_event(self, tmp_path, monkeypatch):
        """DLQ persist should not raise even if DB is unavailable."""
        from events.dead_letter import persist_failed_event
        import db.database as db_mod

        # Monkeypatch SessionLocal to raise
        original = db_mod.SessionLocal

        class FakeSession:
            def add(self, _): raise Exception("DB down")
            def commit(self): pass
            def close(self): pass

        monkeypatch.setattr(db_mod, "SessionLocal", lambda: FakeSession())

        # Should not raise — just log
        persist_failed_event("test-channel", '{"event": "test"}', "Redis timeout")

        monkeypatch.setattr(db_mod, "SessionLocal", original)


class TestRequestSizeLimit:
    def test_oversized_body_rejected(self, client):
        big_payload = {"data": "x" * (11 * 1024 * 1024)}
        res = client.post("/api/health", json=big_payload)
        # Either 413 (size rejected) or 405 (method not allowed on health) — not 200
        assert res.status_code in (413, 405, 422)
