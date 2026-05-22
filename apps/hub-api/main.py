import asyncio
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from db.database import init_db, SessionLocal
from events.broadcaster import broadcaster
from models import ActivityFeed
from routers import opportunities, proposals, approvals, stakeholders, analytics, ai
from workers import sla_worker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("hub-api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
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
    await broadcaster.register(ws)
    logger.info("Activity WS connected. Total clients: %d", len(broadcaster._clients))
    try:
        # Backfill: send last 20 activity items on connect
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

        # Keep the connection alive; broadcaster pushes events as they arrive
        while True:
            await asyncio.sleep(30)
            await ws.send_text(json.dumps({"event_type": "ping"}))

    except WebSocketDisconnect:
        pass
    finally:
        await broadcaster.unregister(ws)
        logger.info("Activity WS disconnected. Total clients: %d", len(broadcaster._clients))


@app.websocket("/ws/sla-alerts")
async def ws_sla(ws: WebSocket):
    """SLA alert stream — receives all events; clients filter by event_type='sla.breach'."""
    await ws.accept()
    await broadcaster.register(ws)
    try:
        while True:
            await asyncio.sleep(30)
            await ws.send_text(json.dumps({"event_type": "ping"}))
    except WebSocketDisconnect:
        pass
    finally:
        await broadcaster.unregister(ws)


@app.websocket("/ws/events")
async def ws_events(ws: WebSocket):
    """Unified event stream — receives all domain events as JSON."""
    await ws.accept()
    await broadcaster.register(ws)
    try:
        while True:
            await asyncio.sleep(30)
            await ws.send_text(json.dumps({"event_type": "ping"}))
    except WebSocketDisconnect:
        pass
    finally:
        await broadcaster.unregister(ws)
