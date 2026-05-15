import asyncio
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from db.database import init_db, SessionLocal
from models import ActivityFeed
from routers import opportunities, proposals, approvals, stakeholders, analytics, ai
from workers import sla_worker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("hub-api")

# WebSocket connection managers
activity_clients: list[WebSocket] = []
sla_clients: list[WebSocket] = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    sla_worker.start()
    logger.info("Hub API ready")
    yield


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
    activity_clients.append(ws)
    logger.info(f"Activity WS connected. Total: {len(activity_clients)}")
    try:
        # Send last 20 activity items on connect
        db = SessionLocal()
        try:
            items = db.scalars(
                select(ActivityFeed)
                .order_by(ActivityFeed.created_at.desc())
                .limit(20)
            ).all()
            for item in reversed(items):
                await ws.send_text(json.dumps({
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

        # Keep alive — broadcast happens from push_activity()
        while True:
            await asyncio.sleep(30)
            await ws.send_text(json.dumps({"type": "ping"}))

    except WebSocketDisconnect:
        activity_clients.remove(ws)
        logger.info(f"Activity WS disconnected. Total: {len(activity_clients)}")


@app.websocket("/ws/sla-alerts")
async def ws_sla(ws: WebSocket):
    await ws.accept()
    sla_clients.append(ws)
    try:
        while True:
            await asyncio.sleep(60)
            # SLA worker writes alerts to activity_feed; this WS polls for them
            db = SessionLocal()
            try:
                alerts = db.scalars(
                    select(ActivityFeed)
                    .where(ActivityFeed.is_alert == True)  # noqa: E712
                    .order_by(ActivityFeed.created_at.desc())
                    .limit(5)
                ).all()
                for alert in alerts:
                    await ws.send_text(json.dumps({
                        "proposal_id": alert.proposal_id,
                        "description": alert.description,
                        "created_at": alert.created_at.isoformat(),
                    }))
            finally:
                db.close()
    except WebSocketDisconnect:
        sla_clients.remove(ws)
