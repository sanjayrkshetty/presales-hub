import csv
import io
from datetime import datetime, timedelta
from collections import defaultdict
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from db.database import get_db
from models import Opportunity, Proposal, Stakeholder, Assignment, SlaConfig
from models.proposal import VALID_STAGES

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/pipeline")
def pipeline_analytics(db: Session = Depends(get_db)):
    # Stage counts
    stage_counts: dict[str, int] = defaultdict(int)
    stage_values: dict[str, float] = defaultdict(float)

    opps = db.scalars(select(Opportunity)).all()
    for o in opps:
        stage_counts[o.stage] += 1
        stage_values[o.stage] += float(o.deal_value_cr or 0)

    total = len(opps)
    won = stage_counts.get("closed_won", 0)
    lost = stage_counts.get("closed_lost", 0)
    decided = won + lost

    # Avg cycle time (days from created to closed)
    closed_opps = [o for o in opps if o.stage in ("closed_won", "closed_lost")]
    avg_cycle_days = None
    if closed_opps:
        total_days = sum((o.updated_at - o.created_at).days for o in closed_opps)
        avg_cycle_days = round(total_days / len(closed_opps), 1)

    acv_cr = sum(float(o.deal_value_cr or 0) for o in opps if o.stage == "closed_won")

    return {
        "total_opportunities": total,
        "win_rate": round(won / decided * 100, 1) if decided else 0,
        "acv_cr": round(acv_cr, 2),
        "avg_cycle_days": avg_cycle_days,
        "funnel": [
            {
                "stage": s,
                "count": stage_counts.get(s, 0),
                "value_cr": round(stage_values.get(s, 0), 2),
            }
            for s in VALID_STAGES
        ],
        "active_pipeline_cr": round(
            sum(float(o.deal_value_cr or 0) for o in opps
                if o.stage not in ("closed_won", "closed_lost")),
            2,
        ),
    }


@router.get("/sla")
def sla_analytics(db: Session = Depends(get_db)):
    opps = db.scalars(select(Opportunity)).all()
    sla_configs = db.scalars(select(SlaConfig)).all()
    sla_map = {s.stage: s.hours_allowed for s in sla_configs}

    breached, warning, ok = [], [], []

    for o in opps:
        if o.stage in ("closed_won", "closed_lost"):
            continue
        hours = sla_map.get(o.stage)
        if not hours:
            continue
        elapsed = (datetime.utcnow() - (o.updated_at or o.created_at)).total_seconds() / 3600
        remaining = hours - elapsed
        item = {
            "opportunity_id": o.id,
            "title": o.title,
            "stage": o.stage,
            "hours_remaining": round(remaining, 1),
            "hours_allowed": hours,
        }
        if remaining < 0:
            breached.append(item)
        elif remaining < hours * 0.25:
            warning.append(item)
        else:
            ok.append(item)

    # Breach count by stage
    stage_breach_counts: dict[str, int] = defaultdict(int)
    for item in breached:
        stage_breach_counts[item["stage"]] += 1

    return {
        "total_active": len(breached) + len(warning) + len(ok),
        "breached_count": len(breached),
        "warning_count": len(warning),
        "breached": sorted(breached, key=lambda x: x["hours_remaining"]),
        "warning": sorted(warning, key=lambda x: x["hours_remaining"]),
        "breach_by_stage": dict(stage_breach_counts),
        "top_bottleneck": max(stage_breach_counts, key=stage_breach_counts.get) if stage_breach_counts else None,
    }


@router.get("/sme-load")
def sme_load(db: Session = Depends(get_db)):
    stakeholders = db.scalars(select(Stakeholder)).all()

    result = []
    for s in stakeholders:
        active = db.scalar(
            select(func.count(Assignment.id))
            .where(Assignment.stakeholder_id == s.id)
            .where(Assignment.status.in_(["pending", "in_progress"]))
        ) or 0

        result.append({
            "id": s.id,
            "name": s.name,
            "bu": s.bu,
            "role": s.role,
            "expertise": s.expertise or [],
            "current_workload": s.current_workload,
            "active_assignments": active,
            "utilization_pct": min(100, round(s.current_workload / 4 * 100)),
        })

    return sorted(result, key=lambda x: x["utilization_pct"], reverse=True)


@router.get("/export/pipeline.csv")
def export_pipeline_csv(db: Session = Depends(get_db)):
    """Download active pipeline as CSV for exec reporting."""
    opps = db.scalars(select(Opportunity)).all()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Title", "Client", "Stage", "Deal Value (Cr)", "Created", "Days in Pipeline"])

    for o in opps:
        days = (datetime.utcnow() - o.created_at).days if o.created_at else ""
        writer.writerow([
            o.title,
            getattr(o, "client_name", ""),
            o.stage,
            o.deal_value_cr,
            o.created_at.date().isoformat() if o.created_at else "",
            days,
        ])

    buf.seek(0)
    filename = f"presales_pipeline_{datetime.utcnow().strftime('%Y%m%d')}.csv"
    return StreamingResponse(
        iter([buf.read()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
