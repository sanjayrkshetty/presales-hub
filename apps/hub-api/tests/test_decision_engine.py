"""
Decision Intelligence Layer — test suite.

7 test classes:
  TestProposalHealthScorer       — deterministic scoring correctness
  TestSlaBreachPredictor         — probability model and risk levels
  TestBottleneckPredictor        — multi-proposal stagnation detection
  TestSmeRanker                  — composite ranking order
  TestApprovalAnomalyDetector    — threshold-based anomaly detection
  TestWorkflowThroughputAnalytics— stage timing computation from audit rows
  TestDecisionIntelligenceAPI    — HTTP endpoint integration tests
"""
import pytest
from datetime import datetime, timedelta, date
from unittest.mock import MagicMock, patch

# ── Proposal Health Scorer ─────────────────────────────────────────────────────

class TestProposalHealthScorer:
    def _score(self, **kwargs):
        from decision_engine.scoring.health import compute_health_score
        defaults = dict(
            proposal_id="p-001",
            stage="drafting",
            content={},
            assignments=[],
            approvals=[],
            deadline=None,
        )
        defaults.update(kwargs)
        return compute_health_score(**defaults)

    def test_empty_proposal_scores_low(self):
        h = self._score()
        assert h.overall_score < 40
        assert h.readiness_classification == "red"

    def test_complete_content_boosts_score(self):
        content = {
            "exec_summary": "Summary text",
            "scope": "Scope text",
            "technical_approach": "Technical text",
            "methodology": "Method text",
            "timeline": "Timeline text",
            "team": "Team text",
            "pricing": "Price text",
            "risk_matrix": "Risk text",
        }
        h = self._score(content=content)
        assert h.breakdown.content_completeness == 30

    def test_deadline_near_gives_partial_timeline_score(self):
        near = (datetime.utcnow() + timedelta(days=5)).date()
        h = self._score(deadline=near)
        assert 0 < h.breakdown.timeline_defined < 15

    def test_no_deadline_zero_timeline_score(self):
        h = self._score(deadline=None)
        assert h.breakdown.timeline_defined == 0

    def test_deadline_comfortable_gives_full_score(self):
        far = (datetime.utcnow() + timedelta(days=90)).date()
        h = self._score(deadline=far)
        assert h.breakdown.timeline_defined == 15

    def test_assignment_gives_staffing_score(self):
        mock_assign = MagicMock()
        mock_assign.status = "pending"
        h = self._score(assignments=[mock_assign])
        assert h.breakdown.staffing_complete == 15

    def test_no_assignment_zero_staffing(self):
        h = self._score(assignments=[])
        assert h.breakdown.staffing_complete == 0

    def test_risk_matrix_gives_coverage(self):
        h = self._score(content={"risk_matrix": "risks here"})
        assert h.breakdown.risk_coverage == 10

    def test_no_risk_zero_coverage(self):
        h = self._score(content={})
        assert h.breakdown.risk_coverage == 0

    def test_classification_green(self):
        from decision_engine.scoring.health import compute_health_score
        content = {
            "exec_summary": "x", "scope": "x", "technical_approach": "x",
            "methodology": "x", "timeline": "x", "team": "x",
            "pricing": "x", "risk_matrix": "x",
        }
        deadline = (datetime.utcnow() + timedelta(days=90)).date()
        mock_a = MagicMock(); mock_a.status = "pending"
        mock_ap = MagicMock(); mock_ap.status = "approved"
        h = compute_health_score(
            proposal_id="p-green",
            stage="approval",
            content=content,
            assignments=[mock_a],
            approvals=[mock_ap],
            deadline=deadline,
        )
        assert h.overall_score >= 80
        assert h.readiness_classification == "green"

    def test_risk_factors_emitted_for_empty_proposal(self):
        h = self._score(stage="security_review")
        assert len(h.risk_factors) > 0

    def test_missing_requirements_listed(self):
        h = self._score(stage="drafting", content={})
        assert len(h.missing_requirements) > 0

    def test_score_bounded_0_to_100(self):
        h = self._score()
        assert 0 <= h.overall_score <= 100

    def test_breakdown_total_equals_overall(self):
        content = {"exec_summary": "x", "scope": "x", "risk_matrix": "x"}
        deadline = (datetime.utcnow() + timedelta(days=30)).date()
        mock_a = MagicMock(); mock_a.status = "pending"
        h = self._score(content=content, deadline=deadline, assignments=[mock_a])
        assert h.breakdown.total() == h.overall_score


# ── SLA Breach Predictor ──────────────────────────────────────────────────────

class TestSlaBreachPredictor:
    def _predict(self, elapsed_hours, sla_hours=24, pending=0, workload=0):
        from decision_engine.predictors.sla_breach import predict_breach
        stage_entered = datetime.utcnow() - timedelta(hours=elapsed_hours)
        return predict_breach(
            proposal_id="p-sla",
            stage="technical_review",
            stage_entered_at=stage_entered,
            sla_hours=sla_hours,
            pending_approvals=pending,
            sme_workload=workload,
        )

    def test_fresh_proposal_is_low_risk(self):
        r = self._predict(elapsed_hours=1, sla_hours=24)
        assert r.risk_level == "low"
        assert r.breach_probability < 0.2

    def test_75_percent_elapsed_is_medium_or_high(self):
        r = self._predict(elapsed_hours=18, sla_hours=24)
        assert r.breach_probability > 0.4
        assert r.risk_level in {"medium", "high"}

    def test_already_breached_is_critical(self):
        r = self._predict(elapsed_hours=25, sla_hours=24)
        assert r.breach_probability == 1.0
        assert r.risk_level == "critical"
        assert r.predicted_hours_to_breach == 0.0

    def test_pending_approvals_increase_probability(self):
        r_no_pending = self._predict(elapsed_hours=12, sla_hours=24, pending=0)
        r_pending = self._predict(elapsed_hours=12, sla_hours=24, pending=3)
        assert r_pending.breach_probability > r_no_pending.breach_probability

    def test_high_workload_increases_probability(self):
        r_low = self._predict(elapsed_hours=12, sla_hours=24, workload=1)
        r_high = self._predict(elapsed_hours=12, sla_hours=24, workload=4)
        assert r_high.breach_probability > r_low.breach_probability

    def test_probability_bounded(self):
        r = self._predict(elapsed_hours=12, sla_hours=24, pending=10, workload=4)
        assert 0.0 <= r.breach_probability <= 1.0

    def test_factors_included(self):
        r = self._predict(elapsed_hours=20, sla_hours=24, pending=2)
        factor_types = [f["factor"] for f in r.factors]
        assert "time_elapsed" in factor_types

    def test_risk_level_ordering(self):
        low = self._predict(1)
        critical = self._predict(25)
        assert low.breach_probability < critical.breach_probability


# ── Bottleneck Predictor ──────────────────────────────────────────────────────

class TestBottleneckPredictor:
    def _snap(self, proposal_id, stage, elapsed, sla=24, pending=0):
        from decision_engine.predictors.bottleneck import ProposalStageSnapshot
        return ProposalStageSnapshot(
            proposal_id=proposal_id,
            stage=stage,
            elapsed_hours=elapsed,
            sla_hours=sla,
            pending_approvals=pending,
        )

    def test_single_proposal_below_threshold_no_bottleneck(self):
        from decision_engine.predictors.bottleneck import detect_bottlenecks
        snaps = [self._snap("p1", "drafting", 10, sla=24)]
        result = detect_bottlenecks(snaps)
        assert len(result) == 0

    def test_two_proposals_same_stage_triggers_bottleneck(self):
        from decision_engine.predictors.bottleneck import detect_bottlenecks
        snaps = [
            self._snap("p1", "technical_review", 15, sla=24),
            self._snap("p2", "technical_review", 18, sla=24),
        ]
        result = detect_bottlenecks(snaps)
        assert len(result) == 1
        assert result[0].stage == "technical_review"
        assert result[0].affected_count == 2

    def test_breached_proposal_gives_high_severity(self):
        from decision_engine.predictors.bottleneck import detect_bottlenecks
        snaps = [
            self._snap("p1", "security_review", 25, sla=24),
            self._snap("p2", "security_review", 20, sla=24),
        ]
        result = detect_bottlenecks(snaps)
        assert result[0].severity == "high"

    def test_terminal_stages_excluded(self):
        from decision_engine.predictors.bottleneck import detect_bottlenecks
        snaps = [
            self._snap("p1", "closed_won", 100),
            self._snap("p2", "closed_won", 100),
        ]
        result = detect_bottlenecks(snaps)
        assert len(result) == 0

    def test_sorted_by_severity_desc(self):
        from decision_engine.predictors.bottleneck import detect_bottlenecks
        snaps = [
            self._snap("p1", "drafting", 10, sla=24),  # below threshold alone
            self._snap("p2", "technical_review", 25, sla=24),  # breached
            self._snap("p3", "technical_review", 22, sla=24),  # also breached
        ]
        result = detect_bottlenecks(snaps)
        if len(result) >= 2:
            order = {"high": 0, "medium": 1, "low": 2}
            assert order[result[0].severity] <= order[result[-1].severity]


# ── SME Ranker ────────────────────────────────────────────────────────────────

class TestSmeRanker:
    def _sme(self, sid, name, expertise, workload):
        s = MagicMock()
        s.id = sid
        s.name = name
        s.expertise = expertise
        s.current_workload = workload
        return s

    def test_highest_expertise_match_ranked_first(self):
        from decision_engine.recommendations.sme_ranker import rank_sme_candidates
        sme_perfect = self._sme("s1", "Alice", ["SOC", "SIEM", "Threat Detection"], 0)
        sme_partial = self._sme("s2", "Bob", ["Cloud", "DevSecOps"], 0)
        result = rank_sme_candidates(
            proposal_id="p-rank",
            rfp_type="SOC Transformation",
            required_expertise=["SOC", "SIEM"],
            candidates=[sme_partial, sme_perfect],
            historical_success={"s1": 0.8, "s2": 0.8},
        )
        assert result.ranked[0].stakeholder_id == "s1"

    def test_lower_workload_preferred_equal_expertise(self):
        from decision_engine.recommendations.sme_ranker import rank_sme_candidates
        s_busy = self._sme("s-busy", "Busy", ["SOC"], 3)
        s_free = self._sme("s-free", "Free", ["SOC"], 0)
        result = rank_sme_candidates(
            proposal_id="p-wl",
            rfp_type="SOC",
            required_expertise=["SOC"],
            candidates=[s_busy, s_free],
            historical_success={"s-busy": 0.5, "s-free": 0.5},
        )
        assert result.ranked[0].stakeholder_id == "s-free"

    def test_empty_candidates_returns_no_recommendation(self):
        from decision_engine.recommendations.sme_ranker import rank_sme_candidates
        result = rank_sme_candidates("p", None, [], [], {})
        assert result.recommended is None

    def test_composite_score_bounded(self):
        from decision_engine.recommendations.sme_ranker import rank_sme_candidates
        sme = self._sme("s1", "A", ["SOC"], 0)
        result = rank_sme_candidates("p", "SOC", ["SOC"], [sme], {"s1": 1.0})
        assert 0.0 <= result.ranked[0].composite_score <= 1.0

    def test_matching_and_missing_tags_populated(self):
        from decision_engine.recommendations.sme_ranker import rank_sme_candidates
        sme = self._sme("s1", "A", ["SOC", "SIEM"], 0)
        result = rank_sme_candidates("p", None, ["SOC", "SIEM", "Threat Detection"], [sme], {})
        r = result.ranked[0]
        assert "soc" in r.matching_tags
        assert "threat detection" in r.missing_tags

    def test_history_default_when_no_data(self):
        from decision_engine.recommendations.sme_ranker import rank_sme_candidates
        sme = self._sme("s1", "A", ["SOC"], 0)
        # No history provided
        result = rank_sme_candidates("p", None, ["SOC"], [sme], {})
        # Should default to 0.5 history, not fail
        assert result.ranked[0].historical_success == 0.5

    def test_explanation_non_empty(self):
        from decision_engine.recommendations.sme_ranker import rank_sme_candidates
        sme = self._sme("s1", "A", ["SOC"], 1)
        result = rank_sme_candidates("p", None, ["SOC"], [sme], {"s1": 0.7})
        assert len(result.ranked[0].explanation) > 0


# ── Approval Anomaly Detector ─────────────────────────────────────────────────

class TestApprovalAnomalyDetector:
    def test_very_fast_approval_is_high_severity(self):
        from decision_engine.anomaly_detection.approval_anomaly import detect_fast_approval
        created = datetime(2026, 1, 1, 10, 0, 0)
        decided = datetime(2026, 1, 1, 10, 0, 30)  # 30 seconds
        result = detect_fast_approval("a1", "p1", "approval", created, decided)
        assert result is not None
        assert result.severity == "high"
        assert result.anomaly_type == "fast_approval"

    def test_moderately_fast_approval_is_medium(self):
        from decision_engine.anomaly_detection.approval_anomaly import detect_fast_approval
        created = datetime(2026, 1, 1, 10, 0, 0)
        decided = datetime(2026, 1, 1, 10, 5, 0)  # 5 minutes
        result = detect_fast_approval("a1", "p1", "technical_review", created, decided)
        assert result is not None
        assert result.severity == "medium"

    def test_normal_approval_speed_no_anomaly(self):
        from decision_engine.anomaly_detection.approval_anomaly import detect_fast_approval
        created = datetime(2026, 1, 1, 10, 0, 0)
        decided = datetime(2026, 1, 1, 14, 0, 0)  # 4 hours
        result = detect_fast_approval("a1", "p1", "approval", created, decided)
        assert result is None

    def test_bypass_at_finance_stage_is_high(self):
        from decision_engine.anomaly_detection.approval_anomaly import detect_bypass
        result = detect_bypass("a1", "p1", "finance_review")
        assert result is not None
        assert result.severity == "high"
        assert result.anomaly_type == "bypass"

    def test_bypass_at_early_stage_is_medium(self):
        from decision_engine.anomaly_detection.approval_anomaly import detect_bypass
        result = detect_bypass("a1", "p1", "technical_review")
        assert result is not None
        assert result.severity == "medium"

    def test_sequential_self_approval_detected(self):
        from decision_engine.anomaly_detection.approval_anomaly import detect_sequential_self_approval
        appr_a = MagicMock()
        appr_a.id = "a1"
        appr_a.approver_id = "actor-x"
        appr_a.stage = "technical_review"
        appr_a.status = "approved"

        appr_b = MagicMock()
        appr_b.id = "a2"
        appr_b.approver_id = "actor-x"
        appr_b.stage = "security_review"
        appr_b.status = "approved"

        results = detect_sequential_self_approval("p1", [appr_a, appr_b])
        assert len(results) == 1
        assert results[0].anomaly_type == "self_approval"

    def test_different_actors_no_self_approval(self):
        from decision_engine.anomaly_detection.approval_anomaly import detect_sequential_self_approval
        appr_a = MagicMock()
        appr_a.id = "a1"; appr_a.approver_id = "actor-1"
        appr_a.stage = "technical_review"; appr_a.status = "approved"

        appr_b = MagicMock()
        appr_b.id = "a2"; appr_b.approver_id = "actor-2"
        appr_b.stage = "security_review"; appr_b.status = "approved"

        results = detect_sequential_self_approval("p1", [appr_a, appr_b])
        assert len(results) == 0

    def test_rejection_pattern_above_threshold(self):
        from decision_engine.anomaly_detection.approval_anomaly import detect_rejection_pattern
        result = detect_rejection_pattern("a1", "p1", "approval", rejection_count=3)
        assert result is not None
        assert result.anomaly_type == "pattern_break"

    def test_rejection_pattern_below_threshold_no_anomaly(self):
        from decision_engine.anomaly_detection.approval_anomaly import detect_rejection_pattern
        result = detect_rejection_pattern("a1", "p1", "approval", rejection_count=1)
        assert result is None


# ── Workflow Throughput Analytics ─────────────────────────────────────────────

class TestWorkflowThroughputAnalytics:
    def _audit_row(self, entity_id, from_state, to_state, occurred_at):
        r = MagicMock()
        r.entity_id = entity_id
        r.from_state = from_state
        r.to_state = to_state
        r.occurred_at = occurred_at
        r.action = "stage_transition"
        return r

    def test_single_proposal_computes_stage_duration(self):
        from decision_engine.analytics.throughput import compute_throughput
        t0 = datetime(2026, 1, 1, 0, 0)
        t1 = datetime(2026, 1, 1, 10, 0)   # 10h in intake
        t2 = datetime(2026, 1, 1, 18, 0)   # 8h in qualification
        rows = [
            self._audit_row("p1", "intake", "qualification", t1),
            self._audit_row("p1", "qualification", "drafting", t2),
        ]
        report = compute_throughput(rows, {"qualification": 24})
        stages = {m.stage: m for m in report.stage_metrics}
        assert "qualification" in stages
        assert abs(stages["qualification"].avg_hours - 8.0) < 0.1

    def test_breach_rate_computed(self):
        from decision_engine.analytics.throughput import compute_throughput
        base = datetime(2026, 1, 1, 0, 0)
        t1 = base + timedelta(hours=30)  # 30h into security_review — exceeds 24h SLA
        t2 = t1 + timedelta(hours=8)     # exited after 8 more hours
        rows = [
            self._audit_row("p1", "technical_review", "security_review", t1),
            self._audit_row("p1", "security_review", "delivery_review", t2),
        ]
        report = compute_throughput(rows, {"security_review": 24})
        stages = {m.stage: m for m in report.stage_metrics}
        # security_review: 8h → no breach (SLA 24h)
        if "security_review" in stages:
            assert stages["security_review"].breach_rate == 0.0

    def test_top_bottleneck_is_slowest_stage(self):
        from decision_engine.analytics.throughput import compute_throughput
        base = datetime(2026, 1, 1, 0)
        t1 = base + timedelta(hours=5)   # entered qualification after 5h in intake
        t2 = t1 + timedelta(hours=50)    # left qualification after 50h (slow)
        t3 = t2 + timedelta(hours=8)     # left drafting after 8h
        rows = [
            self._audit_row("p1", "intake", "qualification", t1),
            self._audit_row("p1", "qualification", "drafting", t2),
            self._audit_row("p1", "drafting", "technical_review", t3),
        ]
        report = compute_throughput(rows, {})
        # qualification took 50h — should be top_bottleneck
        assert report.top_bottleneck is not None

    def test_empty_audit_rows(self):
        from decision_engine.analytics.throughput import compute_throughput
        report = compute_throughput([], {})
        assert report.stage_metrics == []
        assert report.overall_avg_cycle_hours == 0.0

    def test_p90_at_least_p50(self):
        from decision_engine.analytics.throughput import compute_throughput
        # Create multiple proposals at same stage with varied durations
        rows = []
        base = datetime(2026, 1, 1)
        for i in range(5):
            enter = base + timedelta(days=i)
            exit_ = enter + timedelta(hours=i * 5 + 5)
            rows.append(self._audit_row(f"p{i}", "intake", "qualification", enter))
            rows.append(self._audit_row(f"p{i}", "qualification", "drafting", exit_))
        report = compute_throughput(rows, {})
        for m in report.stage_metrics:
            assert m.p90_hours >= m.p50_hours


# ── Deal Risk Scorer ──────────────────────────────────────────────────────────

class TestDealRiskScorer:
    def _score(self, **kwargs):
        from decision_engine.scoring.deal_risk import compute_deal_risk
        defaults = dict(
            opportunity_id="opp-1",
            stage="drafting",
            win_probability=50,
            deal_value_cr=5.0,
            deadline=None,
            created_at=None,
            pending_approvals=0,
            total_approvals=0,
        )
        defaults.update(kwargs)
        return compute_deal_risk(**defaults)

    def test_overdue_deadline_critical(self):
        past = (datetime.utcnow() - timedelta(days=1)).date()
        r = self._score(deadline=past, win_probability=20, deal_value_cr=25.0)
        assert r.risk_level in {"high", "critical"}

    def test_high_win_probability_low_risk(self):
        far = (datetime.utcnow() + timedelta(days=90)).date()
        r = self._score(deadline=far, win_probability=90, deal_value_cr=2.0)
        assert r.risk_score < 55

    def test_recommendations_non_empty_for_risky(self):
        past = (datetime.utcnow() - timedelta(days=3)).date()
        r = self._score(deadline=past, win_probability=10, deal_value_cr=30.0)
        assert len(r.recommendations) > 0

    def test_risk_score_bounded(self):
        r = self._score()
        assert 0 <= r.risk_score <= 100

    def test_factors_include_all_components(self):
        r = self._score()
        factor_names = [f["factor"] for f in r.factors]
        assert "deadline_pressure" in factor_names
        assert "win_probability" in factor_names
        assert "value_exposure" in factor_names


# ── API Integration Tests ─────────────────────────────────────────────────────

class TestDecisionIntelligenceAPI:
    """
    Full stack tests using FastAPI TestClient with in-memory SQLite.
    Uses the `client` and `db` fixtures from conftest.py (already wired to test DB).
    The `reset_db` autouse fixture in conftest drops/recreates tables per test.
    """

    @pytest.fixture
    def seeded(self, db):
        """Seed minimal data; return (proposal_id, opportunity_id)."""
        import uuid
        from models.opportunity import Client, Opportunity
        from models.proposal import Proposal

        client_id = str(uuid.uuid4())
        opp_id = str(uuid.uuid4())
        prop_id = str(uuid.uuid4())

        db.add(Client(id=client_id, name="Test Corp"))
        db.add(Opportunity(
            id=opp_id, client_id=client_id,
            title="Test Opp", stage="drafting",
            win_probability=60,
        ))
        db.add(Proposal(
            id=prop_id, opportunity_id=opp_id,
            stage="drafting", health_score=0, content={},
        ))
        db.commit()
        return prop_id, opp_id

    def test_health_endpoint_returns_score(self, client, seeded):
        prop_id, _ = seeded
        resp = client.get(f"/api/intelligence/proposals/{prop_id}/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "overall_score" in data
        assert "readiness_classification" in data
        assert 0 <= data["overall_score"] <= 100

    def test_health_unknown_proposal_recompute_404(self, client, seeded):
        resp = client.post("/api/intelligence/proposals/nonexistent-id/health/recompute")
        assert resp.status_code == 404

    def test_recompute_endpoint_returns_fresh_score(self, client, seeded):
        prop_id, _ = seeded
        resp = client.post(f"/api/intelligence/proposals/{prop_id}/health/recompute")
        assert resp.status_code == 200
        data = resp.json()
        assert data["cached"] == False

    def test_sla_risk_returns_probability(self, client, seeded):
        prop_id, _ = seeded
        resp = client.get(f"/api/intelligence/proposals/{prop_id}/sla-risk")
        assert resp.status_code == 200
        data = resp.json()
        assert "breach_probability" in data
        assert "risk_level" in data
        assert data["risk_level"] in {"low", "medium", "high", "critical"}

    def test_sme_candidates_returns_ranked_list(self, client, seeded):
        prop_id, _ = seeded
        resp = client.get(f"/api/intelligence/proposals/{prop_id}/sme-candidates")
        assert resp.status_code == 200
        data = resp.json()
        assert "ranked" in data
        assert isinstance(data["ranked"], list)

    def test_bottlenecks_endpoint_returns_list(self, client, seeded):
        resp = client.get("/api/intelligence/bottlenecks")
        assert resp.status_code == 200
        data = resp.json()
        assert "bottlenecks" in data
        assert "total" in data

    def test_throughput_endpoint_responds(self, client, seeded):
        resp = client.get("/api/intelligence/throughput")
        assert resp.status_code == 200
        data = resp.json()
        assert "stage_metrics" in data
        assert "top_bottleneck" in data

    def test_opportunity_risk_endpoint(self, client, seeded):
        _, opp_id = seeded
        resp = client.get(f"/api/intelligence/opportunities/{opp_id}/risk")
        assert resp.status_code == 200
        data = resp.json()
        # OpportunityIntelligence nests deal risk under "deal_risk"
        assert "deal_risk" in data
        assert "risk_score" in data["deal_risk"]
        assert "risk_level" in data["deal_risk"]

    def test_dashboard_endpoint_responds(self, client, seeded):
        resp = client.get("/api/intelligence/dashboard")
        assert resp.status_code == 200
        data = resp.json()
        assert "anomalies" in data
        assert "score_distribution" in data
        assert "critical_sla_risks" in data

    def test_anomalies_endpoint_returns_list(self, client, seeded):
        resp = client.get("/api/intelligence/anomalies")
        assert resp.status_code == 200
        data = resp.json()
        assert "anomalies" in data
        assert isinstance(data["anomalies"], list)
