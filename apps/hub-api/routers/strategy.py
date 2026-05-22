"""
Strategic Intelligence Layer API.

All responses include confidence + rationale.
No auto-execution of operational changes — outputs are advisory only.
Language: "projected", "estimated", "indicative" — never certain.

Endpoints:
  POST /api/strategy/forecast              Pipeline + quarter forecast
  GET  /api/strategy/capacity              Team capacity report
  GET  /api/strategy/escalations           Escalation predictions (all active proposals)
  GET  /api/strategy/dependencies          Cross-BU dependency graph
  POST /api/strategy/simulate              What-if scenario simulation
  GET  /api/strategy/executive-summary     Executive operational summary
  GET  /api/strategy/recommendations       Actionable recommendations
"""
import logging
from dataclasses import asdict
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from db.database import get_db

logger = logging.getLogger("routers.strategy")
router = APIRouter(prefix="/api/strategy", tags=["strategy"])


# ── Request models ─────────────────────────────────────────────────────────────

class ForecastRequest(BaseModel):
    period_label: str = Field("current", description="Label for this forecast snapshot (e.g. 'Q2-2026')")
    rolling_window_days: int = Field(30, ge=7, le=365)
    include_quarter_projection: bool = True


class SimulateRequest(BaseModel):
    scenario_type: str = Field(
        ...,
        description="One of: sme_unavailable | approval_delayed | rfp_surge | bu_overloaded | proposal_rejected"
    )
    parameters: dict[str, Any] = Field(default_factory=dict)
    label: str = Field("", description="Optional human-readable label for this simulation")


# ── Helpers ────────────────────────────────────────────────────────────────────

def _to_dict(obj) -> Any:
    """Recursively convert dataclasses to dicts for JSON serialization."""
    if hasattr(obj, "__dataclass_fields__"):
        return {k: _to_dict(v) for k, v in asdict(obj).items()}
    if isinstance(obj, list):
        return [_to_dict(i) for i in obj]
    if isinstance(obj, dict):
        return {k: _to_dict(v) for k, v in obj.items()}
    return obj


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post("/forecast")
def get_forecast(req: ForecastRequest, db: Session = Depends(get_db)):
    """
    Weighted revenue forecast, confidence intervals, pipeline health,
    and quarter-close projection.
    """
    from strategic_intelligence.forecasting.pipeline_forecast import compute_pipeline_forecast
    from strategic_intelligence.forecasting.quarter_projection import (
        compute_quarter_projection,
        compute_rolling_forecast,
    )

    pipeline = compute_pipeline_forecast(db, period_label=req.period_label)
    rolling = compute_rolling_forecast(db, window_days=req.rolling_window_days)

    result = {
        "pipeline": _to_dict(pipeline),
        "rolling": _to_dict(rolling),
        "advisory": "All forecasts are probabilistic estimates. Confidence intervals should be treated as indicative ranges.",
    }

    if req.include_quarter_projection:
        quarter = compute_quarter_projection(db)
        result["quarter"] = _to_dict(quarter)

    return result


@router.get("/capacity")
def get_capacity(db: Session = Depends(get_db)):
    """Team capacity forecast: SME saturation, approval bottlenecks, burnout risk."""
    from strategic_intelligence.capacity.team_capacity import compute_capacity_report

    report = compute_capacity_report(db)
    return {
        "report": _to_dict(report),
        "advisory": "Capacity assessments reflect current workload data. Redistribute proactively — do not wait for critical state.",
    }


@router.get("/escalations")
def get_escalations(
    min_risk: str = Query("medium", description="Minimum risk level to include: low|medium|high|critical"),
    db: Session = Depends(get_db),
):
    """Escalation predictions for all active proposals."""
    from strategic_intelligence.prediction.escalation_predictor import predict_escalations

    valid_levels = ["low", "medium", "high", "critical"]
    if min_risk not in valid_levels:
        raise HTTPException(status_code=400, detail=f"min_risk must be one of {valid_levels}")

    report = predict_escalations(db)
    level_idx = valid_levels.index(min_risk)

    filtered_signals = [
        _to_dict(s) for s in report.signals
        if valid_levels.index(s.risk_level) >= level_idx
    ]

    return {
        "summary": report.summary,
        "assessed_proposals": report.assessed_proposals,
        "high_risk_count": report.high_risk_count,
        "medium_risk_count": report.medium_risk_count,
        "top_risk_proposal_id": report.top_risk_proposal_id,
        "signals": filtered_signals,
        "advisory": "Escalation scores are probabilistic. Human judgment is required before escalation actions.",
    }


@router.get("/dependencies")
def get_dependencies(db: Session = Depends(get_db)):
    """Cross-BU dependency graph: chokepoints, blocked proposals, high-risk stakeholders."""
    from strategic_intelligence.dependency_graph.graph_builder import build_dependency_graph

    graph = build_dependency_graph(db)
    return {
        "summary": graph.summary,
        "node_count": len(graph.nodes),
        "edge_count": len(graph.edges),
        "chokepoints": graph.chokepoints,
        "blocked_proposals": graph.blocked_proposals,
        "cross_bu_dependencies": graph.cross_bu_dependencies,
        "high_risk_stakeholders": graph.high_risk_stakeholders,
        "critical_path": _to_dict(graph.critical_path),
        "generated_at": graph.generated_at,
        "advisory": "Graph reflects current assignment and approval state. Node positions are logical, not physical.",
    }


@router.post("/simulate")
def run_simulation(req: SimulateRequest, db: Session = Depends(get_db)):
    """
    What-if scenario simulation. Does NOT mutate any production data.
    Returns projected impact on pipeline, capacity, and escalation risk.
    """
    from strategic_intelligence.simulation.what_if import SimulationScenario, run_what_if

    try:
        scenario = SimulationScenario(
            scenario_type=req.scenario_type,
            parameters=req.parameters,
            label=req.label or req.scenario_type,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    result = run_what_if(db, scenario)
    return {
        **_to_dict(result),
        "advisory": "Simulation only — no production data was modified. Projections are indicative.",
    }


@router.get("/executive-summary")
def get_executive_summary(
    period_label: str = Query("current"),
    db: Session = Depends(get_db),
):
    """Executive operational summary: pipeline, capacity, escalations, quarter outlook."""
    from strategic_intelligence.executive.summary_generator import generate_executive_summary

    summary = generate_executive_summary(db, period_label=period_label)
    return {
        **_to_dict(summary),
        "advisory": (
            "This summary aggregates estimated signals. "
            "Figures are indicative and should be validated before board or client communication."
        ),
    }


@router.get("/recommendations")
def get_recommendations(
    category: Optional[str] = Query(None, description="Filter by: staffing|escalation|workflow|prioritization|resource"),
    min_priority: str = Query("medium", description="Minimum priority: low|medium|high|critical"),
    db: Session = Depends(get_db),
):
    """Actionable recommendations: staffing, escalation, workflow, prioritization."""
    from strategic_intelligence.recommendations.recommendation_engine import generate_recommendations

    valid_priorities = ["low", "medium", "high", "critical"]
    if min_priority not in valid_priorities:
        raise HTTPException(status_code=400, detail=f"min_priority must be one of {valid_priorities}")

    report = generate_recommendations(db)
    priority_idx = valid_priorities.index(min_priority)

    recs = [
        _to_dict(r) for r in report.recommendations
        if valid_priorities.index(r.priority) <= priority_idx
        and (category is None or r.category == category)
    ]

    return {
        "total": len(recs),
        "critical_count": sum(1 for r in recs if r["priority"] == "critical"),
        "high_count": sum(1 for r in recs if r["priority"] == "high"),
        "recommendations": recs,
        "summary": report.summary,
        "generated_at": report.generated_at,
        "advisory": "Recommendations are advisory. All actions require human approval before execution.",
    }


@router.get("/health")
def strategy_health():
    """Strategic intelligence layer health check."""
    from strategic_intelligence.config import (
        SME_SATURATION_WORKLOAD, ESCALATION_HIGH_THRESHOLD, FORECAST_ROLLING_DAYS,
    )
    return {
        "status": "ok",
        "modules": [
            "pipeline_forecast", "quarter_projection", "team_capacity",
            "escalation_predictor", "win_probability", "dependency_graph",
            "what_if_simulation", "recommendation_engine", "executive_summary",
            "efficiency_scorer", "cost_tracker",
        ],
        "config": {
            "sme_saturation_workload": SME_SATURATION_WORKLOAD,
            "escalation_high_threshold": ESCALATION_HIGH_THRESHOLD,
            "forecast_rolling_days": FORECAST_ROLLING_DAYS,
        },
    }
