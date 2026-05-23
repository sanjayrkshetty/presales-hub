import asyncio
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from db.database import init_db, SessionLocal, engine
from events.broadcaster import broadcaster
from models import ActivityFeed
from routers import opportunities, proposals, approvals, stakeholders, analytics, ai, workflows, decision_intelligence, memory, copilot, agents, strategy, integration
from telemetry import setup_logging, setup_telemetry
from telemetry.context import set_correlation_id, new_correlation_id
from telemetry.middleware import CorrelationIdMiddleware
from telemetry.tracing import trace_span
from workers import sla_worker

setup_logging()
logger = logging.getLogger("hub-api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
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

# CorrelationIdMiddleware must be added BEFORE CORSMiddleware so that
# the correlation ID is in context for all downstream middleware/routes.
app.add_middleware(CorrelationIdMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "service": "presales-hub",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
    }


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
