import asyncio
import json
import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, Response, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, text

from db.database import init_db, SessionLocal, engine
from events.broadcaster import broadcaster
from models import ActivityFeed
from routers import opportunities, proposals, approvals, stakeholders, analytics, ai, workflows, decision_intelligence, memory, copilot, agents, strategy, integration, platform, auth as auth_router, ai_governance, admin as admin_router
from core.config import settings
from hub_platform.middleware.tenant_context import TenantContextMiddleware
from middleware.rate_limit import limiter, rate_limit_exceeded_handler, RateLimitExceeded
from middleware.request_size import RequestSizeLimitMiddleware
from middleware.security import SecurityHeadersMiddleware
from middleware.timeout import RequestTimeoutMiddleware
from telemetry.prometheus import get_metrics_response, record_request, update_circuit_breaker_gauges
from telemetry import setup_logging, setup_telemetry
from telemetry.context import set_correlation_id, new_correlation_id
from telemetry.middleware import CorrelationIdMiddleware
from telemetry.tracing import trace_span
from workers import sla_worker

setup_logging()
logger = logging.getLogger("hub-api")


async def _check_postgres(db_engine) -> dict:
    try:
        with db_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)[:120]}


async def _check_redis() -> dict:
    try:
        import redis
        r = redis.Redis.from_url(settings.REDIS_URL, socket_connect_timeout=2)
        r.ping()
        return {"status": "ok"}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)[:120]}


async def _check_temporal() -> dict:
    try:
        import socket
        host, _, port_str = settings.TEMPORAL_HOST.partition(":")
        port = int(port_str) if port_str else 7233
        sock = socket.create_connection((host, port), timeout=2)
        sock.close()
        return {"status": "ok"}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)[:120]}


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    # Ensure DLQ table exists
    from events.dead_letter import DeadLetterEvent
    from db.database import Base
    Base.metadata.create_all(bind=engine, tables=[DeadLetterEvent.__table__])

    setup_telemetry(app=app, engine=engine)
    sla_worker.start()
    listener_task = asyncio.create_task(
        broadcaster.start_redis_listener(),
        name="redis-listener",
    )
    logger.info("Hub API ready")
    yield
    listener_task.cancel()
    try:
        await listener_task
    except asyncio.CancelledError:
        pass


app = FastAPI(title="Presales Hub API", version="1.0.0", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

# Middleware order (last-added = outermost, first to run):
#   CorrelationId → TenantContext → Timeout → RequestSize → SecurityHeaders → CORS
app.add_middleware(CorrelationIdMiddleware)
app.add_middleware(TenantContextMiddleware)
app.add_middleware(RequestTimeoutMiddleware)
app.add_middleware(RequestSizeLimitMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router.router)
app.include_router(opportunities.router)
app.include_router(proposals.router)
app.include_router(approvals.router)
app.include_router(stakeholders.router)
app.include_router(analytics.router)
app.include_router(ai.router)
app.include_router(workflows.router)
app.include_router(decision_intelligence.router)
app.include_router(memory.router)
app.include_router(copilot.router)
app.include_router(agents.router)
app.include_router(strategy.router)
app.include_router(integration.router)
app.include_router(platform.router)
app.include_router(ai_governance.router)
app.include_router(admin_router.router)


@app.get("/api/health")
async def health():
    """Aggregate dependency health — returns 200 (degraded) or 503 (critical failure)."""
    t0 = time.monotonic()
    postgres_check, redis_check, temporal_check = await asyncio.gather(
        _check_postgres(engine),
        _check_redis(),
        _check_temporal(),
        return_exceptions=False,
    )
    update_circuit_breaker_gauges()
    from core.circuit_breaker import all_breaker_statuses

    all_checks = {
        "postgres":  postgres_check,
        "redis":     redis_check,
        "temporal":  temporal_check,
    }
    critical_ok = postgres_check["status"] == "ok"
    overall = "ok" if all(v["status"] == "ok" for v in all_checks.values()) else (
        "degraded" if critical_ok else "critical"
    )
    status_code = 200 if critical_ok else 503

    # Count pending DLQ events for ops visibility
    dlq_pending = 0
    try:
        from events.dead_letter import DeadLetterEvent
        with SessionLocal() as db_sess:
            dlq_pending = db_sess.query(DeadLetterEvent).filter_by(resolved=False).count()
    except Exception:
        pass

    payload = {
        "status": overall,
        "service": "presales-hub",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat(),
        "checks": all_checks,
        "circuit_breakers": all_breaker_statuses(),
        "latency_ms": round((time.monotonic() - t0) * 1000, 1),
        "dlq_pending": dlq_pending,
    }
    return Response(
        content=json.dumps(payload),
        media_type="application/json",
        status_code=status_code,
    )


@app.get("/api/ready")
async def readiness():
    """Kubernetes readiness probe — only 200 when ALL critical deps are up."""
    pg = await _check_postgres(engine)
    if pg["status"] != "ok":
        return Response(
            content=json.dumps({"ready": False, "reason": "postgres unavailable"}),
            media_type="application/json",
            status_code=503,
        )
    return {"ready": True}


@app.get("/metrics")
def metrics():
    """Prometheus metrics endpoint."""
    body, content_type = get_metrics_response()
    return Response(content=body, media_type=content_type)


@app.websocket("/ws/activity")
async def ws_activity(ws: WebSocket):
    await ws.accept()

    # WebSocket sessions have no HTTP middleware — assign their own correlation ID.
    cid = new_correlation_id()
    set_correlation_id(cid)

    with trace_span("websocket.activity.connect"):
        await broadcaster.register(ws)
    logger.info(
        "Activity WS connected",
        extra={"total_clients": len(broadcaster._clients), "ws_correlation_id": cid},
    )

    try:
        db = SessionLocal()
        try:
            items = db.scalars(
                select(ActivityFeed)
                .order_by(ActivityFeed.created_at.desc())
                .limit(20)
            ).all()
            for item in reversed(items):
                await ws.send_text(json.dumps({
                    "event_type": "activity.backfill",
                    "id": item.id,
                    "proposal_id": item.proposal_id,
                    "actor_name": item.actor_name,
                    "action_type": item.action_type,
                    "description": item.description,
                    "is_alert": item.is_alert,
                    "created_at": item.created_at.isoformat(),
                }))
        finally:
            db.close()

        while True:
            await asyncio.sleep(30)
            await ws.send_text(json.dumps({"event_type": "ping"}))

    except WebSocketDisconnect:
        pass
    finally:
        with trace_span("websocket.activity.disconnect"):
            await broadcaster.unregister(ws)
        logger.info(
            "Activity WS disconnected",
            extra={"total_clients": len(broadcaster._clients)},
        )


@app.websocket("/ws/sla-alerts")
async def ws_sla(ws: WebSocket):
    """SLA alert stream. Clients filter by event_type='sla.breach'."""
    await ws.accept()
    cid = new_correlation_id()
    set_correlation_id(cid)
    with trace_span("websocket.sla.connect"):
        await broadcaster.register(ws)
    try:
        while True:
            await asyncio.sleep(30)
            await ws.send_text(json.dumps({"event_type": "ping"}))
    except WebSocketDisconnect:
        pass
    finally:
        with trace_span("websocket.sla.disconnect"):
            await broadcaster.unregister(ws)


@app.websocket("/ws/events")
async def ws_events(ws: WebSocket):
    """Unified domain event stream — all event types."""
    await ws.accept()
    cid = new_correlation_id()
    set_correlation_id(cid)
    with trace_span("websocket.events.connect"):
        await broadcaster.register(ws)
    try:
        while True:
            await asyncio.sleep(30)
            await ws.send_text(json.dumps({"event_type": "ping"}))
    except WebSocketDisconnect:
        pass
    finally:
        with trace_span("websocket.events.disconnect"):
            await broadcaster.unregister(ws)
