"""
Strategic Intelligence Layer test suite.

Uses in-memory SQLite (via conftest.py fixtures).
All tests are read-only with respect to intelligence computations —
they seed data then verify outputs, never calling real LLMs or external APIs.

Coverage:
- Pipeline forecasting (pipeline + quarter + rolling)
- Team capacity
- Escalation prediction
- Win probability modeling
- Dependency graph
- What-if simulation (all 5 scenario types)
- Organizational economics
- Recommendation engine
- Executive summary
- Efficiency scorer
- All 8 API endpoints
"""
import uuid
import pytest
from decimal import Decimal
from datetime import date, datetime, timedelta, timezone


# ── Seed helpers ───────────────────────────────────────────────────────────────

def _make_client(db, name="Acme Corp"):
    from models.opportunity import Client
    c = Client(id=str(uuid.uuid4()), name=name)
    db.add(c)
    db.flush()
    return c


def _make_opportunity(db, client_id, title="Test RFP", rfp_type="ISO 27001",
                      deal_value_cr=5.0, win_prob=60, stage="intake",
                      deadline_days=30):
    from models.opportunity import Opportunity
    o = Opportunity(
        id=str(uuid.uuid4()),
        client_id=client_id,
        title=title,
        rfp_type=rfp_type,
        deal_value_cr=Decimal(str(deal_value_cr)),
        win_probability=win_prob,
        stage=stage,
        deadline=date.today() + timedelta(days=deadline_days),
    )
    db.add(o)
    db.flush()
    return o


def _make_proposal(db, opp_id, stage="intake"):
    from models import Proposal
    p = Proposal(id=str(uuid.uuid4()), opportunity_id=opp_id, stage=stage, content={
        "exec_summary": "Test executive summary content that is long enough to be meaningful.",
        "scope": "Test scope definition for the engagement covering all requirements.",
    })
    db.add(p)
    db.flush()
    return p


def _make_stakeholder(db, name="Alice", role="sme", bu="security", workload=3):
    from models.stakeholder import Stakeholder
    s = Stakeholder(
        id=str(uuid.uuid4()),
        name=name,
        role=role,
        bu=bu,
        current_workload=workload,
        expertise=["iso 27001", "pen testing"],
    )
    db.add(s)
    db.flush()
    return s


def _make_approval(db, proposal_id, approver_id=None, status="pending",
                   stage="technical_review", days_old=2, due_in_days=5):
    from models import Approval
    now = datetime.now(timezone.utc)
    a = Approval(
        id=str(uuid.uuid4()),
        proposal_id=proposal_id,
        approver_id=approver_id,
        stage=stage,
        status=status,
        created_at=now - timedelta(days=days_old),
        due_at=now + timedelta(days=due_in_days),
    )
    db.add(a)
    db.flush()
    return a


def _seed_basic(db):
    """Seed a minimal dataset: 1 client, 2 opportunities, 3 proposals, 2 SMEs."""
    client = _make_client(db)
    opp1 = _make_opportunity(db, client.id, title="PCI DSS Audit", rfp_type="PCI DSS",
                              deal_value_cr=8.0, win_prob=70, deadline_days=25)
    opp2 = _make_opportunity(db, client.id, title="ISO Cert", rfp_type="ISO 27001",
                              deal_value_cr=3.0, win_prob=50, deadline_days=60)
    p1 = _make_proposal(db, opp1.id, stage="technical_review")
    p2 = _make_proposal(db, opp2.id, stage="intake")
    p3 = _make_proposal(db, opp1.id, stage="approval")
    sme1 = _make_stakeholder(db, "Alice", role="sme", bu="security", workload=4)
    sme2 = _make_stakeholder(db, "Bob", role="approver", bu="delivery", workload=2)
    appr1 = _make_approval(db, p1.id, approver_id=sme2.id, status="pending", days_old=3)
    db.commit()
    return {
        "client": client, "opp1": opp1, "opp2": opp2,
        "p1": p1, "p2": p2, "p3": p3,
        "sme1": sme1, "sme2": sme2, "appr1": appr1,
    }


# ══════════════════════════════════════════════════════════════════════════════
# TestPipelineForecasting
# ══════════════════════════════════════════════════════════════════════════════

class TestPipelineForecasting:
    def test_empty_db_returns_zero_forecast(self, db):
        from strategic_intelligence.forecasting.pipeline_forecast import compute_pipeline_forecast
        result = compute_pipeline_forecast(db)
        assert result.total_pipeline_cr == 0.0
        assert result.active_proposals == 0
        assert result.pipeline_health_score == 0

    def test_basic_forecast_computes(self, db):
        _seed_basic(db)
        from strategic_intelligence.forecasting.pipeline_forecast import compute_pipeline_forecast
        result = compute_pipeline_forecast(db)
        assert result.active_proposals > 0
        assert result.weighted_forecast_cr >= 0
        assert result.forecast_low_cr <= result.weighted_forecast_cr
        assert result.forecast_high_cr >= result.weighted_forecast_cr
        assert 0.0 <= result.confidence <= 1.0

    def test_pipeline_health_label_valid(self, db):
        _seed_basic(db)
        from strategic_intelligence.forecasting.pipeline_forecast import compute_pipeline_forecast
        result = compute_pipeline_forecast(db)
        assert result.pipeline_health_label in ("green", "yellow", "red")

    def test_stage_breakdown_populated(self, db):
        _seed_basic(db)
        from strategic_intelligence.forecasting.pipeline_forecast import compute_pipeline_forecast
        result = compute_pipeline_forecast(db)
        assert len(result.stage_breakdown) > 0
        for s in result.stage_breakdown:
            assert s.stage
            assert s.proposal_count >= 0
            assert 0.0 <= s.stage_weight <= 1.0

    def test_rationale_present(self, db):
        _seed_basic(db)
        from strategic_intelligence.forecasting.pipeline_forecast import compute_pipeline_forecast
        result = compute_pipeline_forecast(db)
        assert len(result.rationale) > 10

    def test_high_value_late_stage_boosts_confidence(self, db):
        client = _make_client(db)
        opp = _make_opportunity(db, client.id, deal_value_cr=10.0, deadline_days=20)
        _make_proposal(db, opp.id, stage="approval")
        db.commit()
        from strategic_intelligence.forecasting.pipeline_forecast import compute_pipeline_forecast
        result = compute_pipeline_forecast(db)
        assert result.confidence > 0.5  # late stage proposals increase confidence


class TestQuarterProjection:
    def test_empty_db_quarter(self, db):
        from strategic_intelligence.forecasting.quarter_projection import compute_quarter_projection
        result = compute_quarter_projection(db)
        assert result.proposals_due == 0
        assert result.projected_close_cr == 0.0

    def test_quarter_projection_with_data(self, db):
        _seed_basic(db)
        from strategic_intelligence.forecasting.quarter_projection import compute_quarter_projection
        result = compute_quarter_projection(db)
        assert result.quarter_label
        assert result.quarter_start <= result.quarter_end
        assert 0.0 <= result.confidence <= 1.0

    def test_rolling_forecast_returns_valid(self, db):
        from strategic_intelligence.forecasting.quarter_projection import compute_rolling_forecast
        result = compute_rolling_forecast(db, window_days=30)
        assert result.window_days == 30
        assert result.window_label == "rolling-30d"
        assert result.avg_inflow_rate_per_day >= 0


# ══════════════════════════════════════════════════════════════════════════════
# TestTeamCapacity
# ══════════════════════════════════════════════════════════════════════════════

class TestTeamCapacity:
    def test_empty_db_capacity(self, db):
        from strategic_intelligence.capacity.team_capacity import compute_capacity_report
        result = compute_capacity_report(db)
        assert result.total_smes == 0
        assert result.overall_capacity_label == "healthy"

    def test_normal_capacity(self, db):
        _seed_basic(db)
        from strategic_intelligence.capacity.team_capacity import compute_capacity_report
        result = compute_capacity_report(db)
        assert result.total_smes >= 2
        assert result.overall_capacity_label in ("healthy", "strained", "critical")
        assert 0.0 <= result.saturation_pct <= 1.0

    def test_overloaded_sme_detected(self, db):
        client = _make_client(db)
        _make_stakeholder(db, "Overloaded SME", workload=15)
        db.commit()
        from strategic_intelligence.capacity.team_capacity import compute_capacity_report
        result = compute_capacity_report(db)
        assert result.overloaded_smes >= 1
        overloaded = [p for p in result.sme_profiles if p.risk_level == "overloaded"]
        assert len(overloaded) >= 1

    def test_approval_bottleneck_detected(self, db):
        client = _make_client(db)
        opp = _make_opportunity(db, client.id)
        sme = _make_stakeholder(db, "Approver")
        # Create 4 pending approvals in same stage
        for _ in range(4):
            p = _make_proposal(db, opp.id, stage="technical_review")
            _make_approval(db, p.id, approver_id=sme.id, status="pending", stage="technical_review", days_old=5)
        db.commit()
        from strategic_intelligence.capacity.team_capacity import compute_capacity_report
        result = compute_capacity_report(db)
        assert len(result.bottleneck_stages) >= 1

    def test_throughput_risk_labels_valid(self, db):
        _seed_basic(db)
        from strategic_intelligence.capacity.team_capacity import compute_capacity_report
        result = compute_capacity_report(db)
        assert result.throughput_risk in ("low", "medium", "high")


# ══════════════════════════════════════════════════════════════════════════════
# TestEscalationPredictor
# ══════════════════════════════════════════════════════════════════════════════

class TestEscalationPredictor:
    def test_empty_db_escalation(self, db):
        from strategic_intelligence.prediction.escalation_predictor import predict_escalations
        result = predict_escalations(db)
        assert result.assessed_proposals == 0
        assert result.signals == []

    def test_escalation_scores_in_range(self, db):
        _seed_basic(db)
        from strategic_intelligence.prediction.escalation_predictor import predict_escalations
        result = predict_escalations(db)
        for sig in result.signals:
            assert 0.0 <= sig.escalation_score <= 1.0
            assert sig.risk_level in ("low", "medium", "high", "critical")
            assert sig.confidence > 0

    def test_overdue_approval_raises_score(self, db):
        client = _make_client(db)
        opp = _make_opportunity(db, client.id, deal_value_cr=10.0, deadline_days=3)
        p = _make_proposal(db, opp.id, stage="approval")
        sme = _make_stakeholder(db)
        # Overdue approval
        _make_approval(db, p.id, approver_id=sme.id, status="pending", days_old=10, due_in_days=-2)
        db.commit()
        from strategic_intelligence.prediction.escalation_predictor import predict_escalations
        result = predict_escalations(db)
        top = next((s for s in result.signals if s.proposal_id == p.id), None)
        assert top is not None
        assert top.escalation_score >= 0.35  # overdue + deadline + high value

    def test_rationale_and_action_present(self, db):
        _seed_basic(db)
        from strategic_intelligence.prediction.escalation_predictor import predict_escalations
        result = predict_escalations(db)
        for sig in result.signals:
            assert sig.rationale
            assert sig.recommended_action


# ══════════════════════════════════════════════════════════════════════════════
# TestWinProbability
# ══════════════════════════════════════════════════════════════════════════════

class TestWinProbability:
    def test_missing_proposal_returns_default(self, db):
        from strategic_intelligence.prediction.win_probability import compute_win_probability
        result = compute_win_probability(db, "nonexistent-id")
        assert result.confidence == 0.10
        assert "not found" in result.contributing_factors[0].lower()

    def test_win_probability_in_bounds(self, db):
        data = _seed_basic(db)
        from strategic_intelligence.prediction.win_probability import compute_win_probability
        from strategic_intelligence.config import WIN_PROB_FLOOR, WIN_PROB_CEIL
        result = compute_win_probability(db, data["p1"].id)
        assert WIN_PROB_FLOOR <= result.adjusted_probability <= WIN_PROB_CEIL

    def test_rationale_present(self, db):
        data = _seed_basic(db)
        from strategic_intelligence.prediction.win_probability import compute_win_probability
        result = compute_win_probability(db, data["p1"].id)
        assert result.rationale
        assert result.risk_level in ("low", "medium", "high", "critical")

    def test_portfolio_returns_list(self, db):
        _seed_basic(db)
        from strategic_intelligence.prediction.win_probability import compute_portfolio_win_probabilities
        results = compute_portfolio_win_probabilities(db)
        assert isinstance(results, list)

    def test_overdue_approvals_reduce_win_prob(self, db):
        client = _make_client(db)
        opp = _make_opportunity(db, client.id, win_prob=80)
        p = _make_proposal(db, opp.id, stage="technical_review")
        sme = _make_stakeholder(db)
        # Two overdue approvals
        for _ in range(2):
            _make_approval(db, p.id, approver_id=sme.id, status="pending", days_old=15, due_in_days=-3)
        db.commit()
        from strategic_intelligence.prediction.win_probability import compute_win_probability
        result = compute_win_probability(db, p.id)
        assert result.adjusted_probability < result.base_probability  # overdue = reduced


# ══════════════════════════════════════════════════════════════════════════════
# TestDependencyGraph
# ══════════════════════════════════════════════════════════════════════════════

class TestDependencyGraph:
    def test_empty_graph(self, db):
        from strategic_intelligence.dependency_graph.graph_builder import build_dependency_graph
        graph = build_dependency_graph(db)
        assert graph.nodes == []
        assert graph.edges == []
        assert graph.chokepoints == []

    def test_graph_with_data(self, db):
        _seed_basic(db)
        from strategic_intelligence.dependency_graph.graph_builder import build_dependency_graph
        graph = build_dependency_graph(db)
        assert len(graph.nodes) > 0
        assert graph.summary
        assert graph.generated_at

    def test_node_types_valid(self, db):
        _seed_basic(db)
        from strategic_intelligence.dependency_graph.graph_builder import build_dependency_graph
        graph = build_dependency_graph(db)
        for node in graph.nodes:
            assert node.node_type in ("proposal", "stakeholder", "bu")

    def test_edge_types_valid(self, db):
        _seed_basic(db)
        from strategic_intelligence.dependency_graph.graph_builder import build_dependency_graph
        graph = build_dependency_graph(db)
        valid_types = {"assigned_to", "approves", "blocks", "depends_on", "cross_bu"}
        for edge in graph.edges:
            assert edge.edge_type in valid_types

    def test_chokepoint_detected_with_many_approvals(self, db):
        client = _make_client(db)
        opp = _make_opportunity(db, client.id)
        sme = _make_stakeholder(db, "Bottleneck Bob", role="approver")
        for _ in range(4):
            p = _make_proposal(db, opp.id)
            _make_approval(db, p.id, approver_id=sme.id, status="pending")
        db.commit()
        from strategic_intelligence.dependency_graph.graph_builder import build_dependency_graph
        graph = build_dependency_graph(db)
        choke_ids = [c["stakeholder_id"] for c in graph.chokepoints]
        assert sme.id in choke_ids


# ══════════════════════════════════════════════════════════════════════════════
# TestWhatIfSimulation
# ══════════════════════════════════════════════════════════════════════════════

class TestWhatIfSimulation:
    def test_invalid_scenario_type_raises(self):
        from strategic_intelligence.simulation.what_if import SimulationScenario
        with pytest.raises(ValueError, match="Unknown scenario type"):
            SimulationScenario(scenario_type="nonexistent_xyz")

    def test_rfp_surge_simulation(self, db):
        _seed_basic(db)
        from strategic_intelligence.simulation.what_if import SimulationScenario, run_what_if
        scenario = SimulationScenario("rfp_surge", parameters={"new_rfp_count": 15})
        result = run_what_if(db, scenario)
        assert result.impact.affected_proposals == 15
        assert result.impact.capacity_impact in ("none", "mild", "moderate", "severe")
        assert result.note  # confirms no mutation

    def test_approval_delayed_simulation(self, db):
        _seed_basic(db)
        from strategic_intelligence.simulation.what_if import SimulationScenario, run_what_if
        scenario = SimulationScenario("approval_delayed", parameters={"delay_hours": 48})
        result = run_what_if(db, scenario)
        assert result.impact.timeline_delay_days == 2.0
        assert 0.0 <= result.impact.sla_risk_increase <= 1.0

    def test_sme_unavailable_simulation(self, db):
        data = _seed_basic(db)
        from strategic_intelligence.simulation.what_if import SimulationScenario, run_what_if
        scenario = SimulationScenario("sme_unavailable", parameters={
            "stakeholder_id": data["sme1"].id,
            "duration_days": 3,
        })
        result = run_what_if(db, scenario)
        assert result.impact.timeline_delay_days == 3.0

    def test_bu_overloaded_simulation(self, db):
        _seed_basic(db)
        from strategic_intelligence.simulation.what_if import SimulationScenario, run_what_if
        scenario = SimulationScenario("bu_overloaded", parameters={"bu": "security"})
        result = run_what_if(db, scenario)
        assert isinstance(result.impact.capacity_impact, str)

    def test_proposal_rejected_simulation(self, db):
        data = _seed_basic(db)
        from strategic_intelligence.simulation.what_if import SimulationScenario, run_what_if
        scenario = SimulationScenario("proposal_rejected", parameters={"proposal_id": data["p1"].id})
        result = run_what_if(db, scenario)
        assert result.impact.affected_proposals == 1
        assert result.impact.revenue_at_risk_cr >= 0

    def test_simulation_does_not_mutate_db(self, db):
        _seed_basic(db)
        from sqlalchemy import select
        from models import Proposal
        from strategic_intelligence.simulation.what_if import SimulationScenario, run_what_if
        count_before = len(db.scalars(select(Proposal)).all())
        scenario = SimulationScenario("rfp_surge", parameters={"new_rfp_count": 100})
        run_what_if(db, scenario)
        count_after = len(db.scalars(select(Proposal)).all())
        assert count_before == count_after  # DB unchanged

    def test_simulation_recommendations_populated(self, db):
        _seed_basic(db)
        from strategic_intelligence.simulation.what_if import SimulationScenario, run_what_if
        scenario = SimulationScenario("rfp_surge", parameters={"new_rfp_count": 50})
        result = run_what_if(db, scenario)
        assert len(result.recommendations) >= 1


# ══════════════════════════════════════════════════════════════════════════════
# TestOrganizationalEconomics
# ══════════════════════════════════════════════════════════════════════════════

class TestOrganizationalEconomics:
    def test_empty_economics(self, db):
        from strategic_intelligence.economics.cost_tracker import compute_organizational_economics
        result = compute_organizational_economics(db)
        assert result.proposals_analyzed == 0
        assert result.total_estimated_cost_cr == 0.0

    def test_basic_economics(self, db):
        _seed_basic(db)
        from strategic_intelligence.economics.cost_tracker import compute_organizational_economics
        result = compute_organizational_economics(db)
        assert result.proposals_analyzed > 0
        assert result.avg_cost_per_proposal_cr >= 0
        assert result.pipeline_efficiency_score >= 0
        assert result.rationale

    def test_cost_per_proposal_positive(self, db):
        _seed_basic(db)
        from strategic_intelligence.economics.cost_tracker import compute_organizational_economics
        result = compute_organizational_economics(db)
        for detail in result.proposal_details:
            assert detail.estimated_cost_cr >= 0
            assert detail.total_cost_cr >= 0

    def test_economics_insights_list(self, db):
        _seed_basic(db)
        from strategic_intelligence.economics.cost_tracker import compute_organizational_economics
        result = compute_organizational_economics(db)
        assert isinstance(result.insights, list)


# ══════════════════════════════════════════════════════════════════════════════
# TestRecommendationEngine
# ══════════════════════════════════════════════════════════════════════════════

class TestRecommendationEngine:
    def test_empty_db_recommendations(self, db):
        from strategic_intelligence.recommendations.recommendation_engine import generate_recommendations
        result = generate_recommendations(db)
        assert isinstance(result.recommendations, list)
        assert result.summary

    def test_recommendations_with_data(self, db):
        _seed_basic(db)
        from strategic_intelligence.recommendations.recommendation_engine import generate_recommendations
        result = generate_recommendations(db)
        assert result.total_recommendations == len(result.recommendations)
        for r in result.recommendations:
            assert r.category in ("staffing", "escalation", "workflow", "prioritization", "resource")
            assert r.priority in ("critical", "high", "medium", "low")
            assert r.title
            assert r.rationale
            assert len(r.action_items) >= 1

    def test_overloaded_sme_generates_staffing_rec(self, db):
        _make_stakeholder(db, "Overloaded", workload=12)
        db.commit()
        from strategic_intelligence.recommendations.recommendation_engine import generate_recommendations
        result = generate_recommendations(db)
        staffing = [r for r in result.recommendations if r.category == "staffing"]
        assert len(staffing) >= 1

    def test_recommendations_sorted_by_priority(self, db):
        _seed_basic(db)
        _make_stakeholder(db, "Overloaded2", workload=15)
        db.commit()
        from strategic_intelligence.recommendations.recommendation_engine import generate_recommendations
        result = generate_recommendations(db)
        priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        priorities = [priority_order[r.priority] for r in result.recommendations]
        assert priorities == sorted(priorities)


# ══════════════════════════════════════════════════════════════════════════════
# TestExecutiveSummary
# ══════════════════════════════════════════════════════════════════════════════

class TestExecutiveSummary:
    def test_executive_summary_empty(self, db):
        from strategic_intelligence.executive.summary_generator import generate_executive_summary
        result = generate_executive_summary(db)
        assert result.generated_at
        assert result.delivery_readiness in ("on_track", "at_risk", "critical")
        assert 0.0 <= result.confidence <= 1.0

    def test_executive_summary_with_data(self, db):
        _seed_basic(db)
        from strategic_intelligence.executive.summary_generator import generate_executive_summary
        result = generate_executive_summary(db)
        assert result.headline_metrics["active_proposals"] > 0
        assert result.pipeline_snapshot["health"] in ("green", "yellow", "red")
        assert result.quarter_projection["label"]
        assert isinstance(result.top_risks, list)
        assert isinstance(result.top_recommendations, list)

    def test_economics_snapshot_in_summary(self, db):
        _seed_basic(db)
        from strategic_intelligence.executive.summary_generator import generate_executive_summary
        result = generate_executive_summary(db)
        assert "pipeline_efficiency_pct" in result.economics_snapshot
        assert "total_cost_cr" in result.economics_snapshot


# ══════════════════════════════════════════════════════════════════════════════
# TestEfficiencyScorer
# ══════════════════════════════════════════════════════════════════════════════

class TestEfficiencyScorer:
    def test_empty_efficiency(self, db):
        from strategic_intelligence.analytics.efficiency_scorer import compute_efficiency_score
        result = compute_efficiency_score(db)
        assert 0 <= result.overall_score <= 100
        assert result.score_label in ("excellent", "good", "fair", "poor")

    def test_breakdown_scores_sum(self, db):
        _seed_basic(db)
        from strategic_intelligence.analytics.efficiency_scorer import compute_efficiency_score
        result = compute_efficiency_score(db)
        bd = result.breakdown
        total = (
            bd.win_rate_score + bd.cycle_time_score +
            bd.approval_velocity_score + bd.throughput_score + bd.bottleneck_score
        )
        assert abs(total - bd.total_score) < 0.01

    def test_full_approval_velocity_boosts_score(self, db):
        client = _make_client(db)
        opp = _make_opportunity(db, client.id)
        p = _make_proposal(db, opp.id)
        sme = _make_stakeholder(db)
        # All approvals decided
        for _ in range(3):
            _make_approval(db, p.id, approver_id=sme.id, status="approved", days_old=2)
        db.commit()
        from strategic_intelligence.analytics.efficiency_scorer import compute_efficiency_score
        result = compute_efficiency_score(db)
        # Approval velocity score should be near max (20)
        assert result.breakdown.approval_velocity_score >= 18.0

    def test_insights_list(self, db):
        _seed_basic(db)
        from strategic_intelligence.analytics.efficiency_scorer import compute_efficiency_score
        result = compute_efficiency_score(db)
        assert isinstance(result.insights, list)
        assert len(result.insights) >= 1


# ══════════════════════════════════════════════════════════════════════════════
# TestStrategyAPI
# ══════════════════════════════════════════════════════════════════════════════

class TestStrategyAPI:
    def test_health_endpoint(self, client):
        resp = client.get("/api/strategy/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert len(data["modules"]) >= 10

    def test_forecast_endpoint_empty(self, client):
        resp = client.post("/api/strategy/forecast", json={"period_label": "test"})
        assert resp.status_code == 200
        data = resp.json()
        assert "pipeline" in data
        assert "rolling" in data
        assert "advisory" in data

    def test_forecast_endpoint_with_data(self, client, db):
        _seed_basic(db)
        db.commit()
        resp = client.post("/api/strategy/forecast", json={
            "period_label": "Q2-2026",
            "rolling_window_days": 30,
            "include_quarter_projection": True,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "quarter" in data
        assert data["pipeline"]["active_proposals"] > 0

    def test_capacity_endpoint(self, client, db):
        _seed_basic(db)
        db.commit()
        resp = client.get("/api/strategy/capacity")
        assert resp.status_code == 200
        data = resp.json()
        assert "report" in data
        assert data["report"]["total_smes"] >= 2

    def test_escalations_endpoint_default(self, client, db):
        _seed_basic(db)
        db.commit()
        resp = client.get("/api/strategy/escalations")
        assert resp.status_code == 200
        data = resp.json()
        assert "signals" in data
        assert "advisory" in data

    def test_escalations_invalid_min_risk(self, client):
        resp = client.get("/api/strategy/escalations?min_risk=extreme")
        assert resp.status_code == 400

    def test_dependencies_endpoint(self, client, db):
        _seed_basic(db)
        db.commit()
        resp = client.get("/api/strategy/dependencies")
        assert resp.status_code == 200
        data = resp.json()
        assert "node_count" in data
        assert "edge_count" in data
        assert data["node_count"] > 0

    def test_simulate_endpoint_rfp_surge(self, client, db):
        _seed_basic(db)
        db.commit()
        resp = client.post("/api/strategy/simulate", json={
            "scenario_type": "rfp_surge",
            "parameters": {"new_rfp_count": 10},
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["scenario_type"] == "rfp_surge"
        assert "impact" in data
        assert "advisory" in data

    def test_simulate_invalid_scenario(self, client):
        resp = client.post("/api/strategy/simulate", json={
            "scenario_type": "not_a_real_scenario",
            "parameters": {},
        })
        assert resp.status_code == 400

    def test_executive_summary_endpoint(self, client, db):
        _seed_basic(db)
        db.commit()
        resp = client.get("/api/strategy/executive-summary")
        assert resp.status_code == 200
        data = resp.json()
        assert "headline_metrics" in data
        assert "delivery_readiness" in data
        assert data["delivery_readiness"] in ("on_track", "at_risk", "critical")
        assert "advisory" in data

    def test_recommendations_endpoint(self, client, db):
        _seed_basic(db)
        _make_stakeholder(db, "Overloaded", workload=12)
        db.commit()
        resp = client.get("/api/strategy/recommendations")
        assert resp.status_code == 200
        data = resp.json()
        assert "recommendations" in data
        assert "total" in data
        assert "advisory" in data

    def test_recommendations_filtered_by_category(self, client, db):
        _make_stakeholder(db, "SME A", workload=11)
        db.commit()
        resp = client.get("/api/strategy/recommendations?category=staffing&min_priority=high")
        assert resp.status_code == 200
        data = resp.json()
        for r in data["recommendations"]:
            assert r["category"] == "staffing"

    def test_recommendations_invalid_priority(self, client):
        resp = client.get("/api/strategy/recommendations?min_priority=urgent")
        assert resp.status_code == 400
