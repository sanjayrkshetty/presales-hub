"""
Temporal workflow orchestration tests.

Structure:
  TestSchemas              — dataclass validation (no external deps)
  TestActivitiesUnit       — activities called directly with mocked DB/Redis
  TestWorkflowRegistration — import/registration smoke tests (no runtime)
  TestTemporalDegradation  — FastAPI returns 503 when Temporal is down
  TestWorkflowIntegration  — full workflow round-trips via WorkflowEnvironment
                             (requires temporalio; skipped if not installed)

Note: WorkflowEnvironment.start_time_skipping() uses an embedded test server
bundled with the temporalio SDK — no separate Temporal cluster required.
"""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock

# Guard: skip module if temporalio is not installed
temporalio = pytest.importorskip("temporalio", reason="temporalio not installed")


# ── Schema tests ─────────────────────────────────────────────────────────────

class TestSchemas:
    def test_proposal_workflow_input_defaults(self):
        from temporal.schemas import ProposalWorkflowInput
        inp = ProposalWorkflowInput(proposal_id="p-001")
        assert inp.proposal_id == "p-001"
        assert inp.correlation_id == ""
        assert inp.initial_stage == "intake"

    def test_transition_input_optional_fields(self):
        from temporal.schemas import TransitionInput
        inp = TransitionInput(proposal_id="p1", from_stage="intake", to_stage="qualification")
        assert inp.actor_id is None
        assert inp.note is None
        assert inp.correlation_id == ""

    def test_transition_result(self):
        from temporal.schemas import TransitionResult
        r = TransitionResult(success=True, stage="qualification")
        assert r.success is True
        assert r.stage == "qualification"
        assert r.error is None

    def test_parallel_review_input(self):
        from temporal.schemas import ParallelReviewInput
        inp = ParallelReviewInput(proposal_id="p1", timeout_hours=48)
        assert inp.timeout_hours == 48

    def test_parallel_review_result_all_approved(self):
        from temporal.schemas import ParallelReviewResult, PARALLEL_REVIEW_STAGES
        stages = sorted(PARALLEL_REVIEW_STAGES)
        r = ParallelReviewResult(
            all_approved=True,
            decisions={s: {"status": "approved"} for s in stages},
        )
        assert r.all_approved is True
        assert len(r.decisions) == 3

    def test_parallel_review_result_partial(self):
        from temporal.schemas import ParallelReviewResult, PARALLEL_REVIEW_STAGES
        stages = sorted(PARALLEL_REVIEW_STAGES)
        r = ParallelReviewResult(
            all_approved=False,
            decisions={
                stages[0]: {"status": "approved"},
                stages[1]: {"status": "rejected"},
                stages[2]: {"status": "approved"},
            },
        )
        assert r.all_approved is False

    def test_sla_input(self):
        from temporal.schemas import SlaInput
        inp = SlaInput(proposal_id="p1", opportunity_id="o1", stage="drafting", sla_hours=24)
        assert inp.sla_hours == 24
        assert inp.escalate_to_role is None

    def test_terminal_stages(self):
        from temporal.schemas import TERMINAL_STAGES
        assert "closed_won" in TERMINAL_STAGES
        assert "closed_lost" in TERMINAL_STAGES
        assert "drafting" not in TERMINAL_STAGES

    def test_parallel_review_stages(self):
        from temporal.schemas import PARALLEL_REVIEW_STAGES
        assert len(PARALLEL_REVIEW_STAGES) == 3
        assert "technical_review" in PARALLEL_REVIEW_STAGES
        assert "security_review" in PARALLEL_REVIEW_STAGES
        assert "delivery_review" in PARALLEL_REVIEW_STAGES

    def test_task_queue_name(self):
        from temporal.schemas import TASK_QUEUE
        assert TASK_QUEUE == "presales-hub"


# ── Activity unit tests ───────────────────────────────────────────────────────

class TestActivitiesUnit:
    """
    Call activities directly (no Temporal runtime).
    DB is monkeypatched to the in-memory test DB via conftest fixtures.
    """

    @pytest.fixture(autouse=True)
    def patch_session(self, monkeypatch):
        """Route activity DB calls to the in-memory test DB."""
        from tests._testdb import TestSessionLocal
        monkeypatch.setattr("temporal.activities.proposal.SessionLocal", TestSessionLocal)
        monkeypatch.setattr("temporal.activities.approval.SessionLocal", TestSessionLocal)
        monkeypatch.setattr("temporal.activities.notification.SessionLocal", TestSessionLocal)

    def test_persist_stage_transition_not_found_raises(self):
        from temporal.activities.proposal import persist_stage_transition
        from temporal.schemas import TransitionInput
        with pytest.raises(ValueError, match="not found"):
            persist_stage_transition(TransitionInput(
                proposal_id="00000000-0000-0000-0000-000000000000",
                from_stage="intake",
                to_stage="qualification",
            ))

    def test_persist_stage_transition_succeeds(self, db):
        from temporal.activities.proposal import persist_stage_transition
        from temporal.schemas import TransitionInput
        from models import Proposal

        proposal = Proposal(id="p-temporal-test", stage="intake")
        db.add(proposal)
        db.commit()

        result = persist_stage_transition(TransitionInput(
            proposal_id="p-temporal-test",
            from_stage="intake",
            to_stage="qualification",
        ))

        assert result.success is True
        assert result.stage == "qualification"

    def test_initialize_parallel_approvals_creates_records(self, db):
        from temporal.activities.proposal import initialize_parallel_approvals
        from temporal.schemas import InitParallelApprovalsInput, PARALLEL_REVIEW_STAGES
        from models import Proposal

        proposal = Proposal(id="p-par-review-test", stage="drafting")
        db.add(proposal)
        db.commit()

        created = initialize_parallel_approvals(InitParallelApprovalsInput(
            proposal_id="p-par-review-test",
            review_stages=sorted(PARALLEL_REVIEW_STAGES),
        ))

        assert len(created) == 3
        assert set(created) == PARALLEL_REVIEW_STAGES

    def test_initialize_parallel_approvals_idempotent(self, db):
        from temporal.activities.proposal import initialize_parallel_approvals
        from temporal.schemas import InitParallelApprovalsInput, PARALLEL_REVIEW_STAGES
        from models import Proposal

        proposal = Proposal(id="p-idem-test", stage="drafting")
        db.add(proposal)
        db.commit()

        stages = sorted(PARALLEL_REVIEW_STAGES)
        initialize_parallel_approvals(InitParallelApprovalsInput(
            proposal_id="p-idem-test",
            review_stages=stages,
        ))
        # Second call must create nothing
        created = initialize_parallel_approvals(InitParallelApprovalsInput(
            proposal_id="p-idem-test",
            review_stages=stages,
        ))
        assert created == []

    def test_persist_approval_decision_not_found_raises(self):
        from temporal.activities.approval import persist_approval_decision
        from temporal.schemas import ApprovalActivityInput
        with pytest.raises(ValueError, match="not found"):
            persist_approval_decision(ApprovalActivityInput(
                approval_id="00000000-0000-0000-0000-000000000000",
                proposal_id="p1",
                stage="technical_review",
                status="approved",
            ))

    def test_emit_workflow_event_no_redis(self):
        """emit_workflow_event must not raise when Redis is unavailable."""
        from temporal.activities.notification import emit_workflow_event
        from temporal.schemas import EventInput
        import events.bus as bus_mod
        original = bus_mod.sync_client
        try:
            bus_mod.sync_client = None
            emit_workflow_event(EventInput(
                event_type="test.event",
                entity_id="e1",
                entity_type="proposal",
            ))
        finally:
            bus_mod.sync_client = original

    def test_emit_workflow_event_redis_error_swallowed(self):
        """emit_workflow_event swallows connection errors — never fails a workflow."""
        from temporal.activities.notification import emit_workflow_event
        from temporal.schemas import EventInput
        import events.bus as bus_mod
        mock_client = MagicMock()
        mock_client.publish.side_effect = ConnectionError("down")
        original = bus_mod.sync_client
        try:
            bus_mod.sync_client = mock_client
            emit_workflow_event(EventInput(
                event_type="test.event",
                entity_id="e1",
                entity_type="proposal",
            ))
        finally:
            bus_mod.sync_client = original

    def test_escalate_sla_writes_activity_feed(self, db):
        from temporal.activities.notification import escalate_sla
        from temporal.schemas import EscalationInput
        from models import Proposal, ActivityFeed
        from sqlalchemy import select

        # ActivityFeed.proposal_id is a FK — the proposal must exist first.
        proposal = Proposal(id="p-sla-test", stage="drafting")
        db.add(proposal)
        db.commit()

        escalate_sla(EscalationInput(
            proposal_id="p-sla-test",
            opportunity_id="o-sla-test",
            stage="drafting",
            escalate_to_role="presales_lead",
            overdue_hours=3.5,
        ))

        alerts = db.scalars(
            select(ActivityFeed).where(ActivityFeed.is_alert == True)  # noqa: E712
        ).all()
        assert any("drafting" in (a.description or "") for a in alerts)


# ── Registration smoke tests ──────────────────────────────────────────────────

class TestWorkflowRegistration:
    """Verify all workflow and activity definitions can be imported without errors."""

    def test_proposal_workflow_importable(self):
        from temporal.workflows.proposal import ProposalLifecycleWorkflow
        assert ProposalLifecycleWorkflow is not None

    def test_parallel_review_workflow_importable(self):
        from temporal.workflows.approval import ParallelReviewWorkflow
        assert ParallelReviewWorkflow is not None

    def test_sla_workflow_importable(self):
        from temporal.workflows.sla import SlaEscalationWorkflow
        assert SlaEscalationWorkflow is not None

    def test_all_activities_importable(self):
        from temporal.activities.proposal import persist_stage_transition, initialize_parallel_approvals
        from temporal.activities.approval import persist_approval_decision
        from temporal.activities.notification import emit_workflow_event, escalate_sla
        for fn in (persist_stage_transition, initialize_parallel_approvals,
                   persist_approval_decision, emit_workflow_event, escalate_sla):
            assert callable(fn)

    def test_worker_importable(self):
        import temporal.worker as _mod
        assert hasattr(_mod, "main")

    def test_client_importable(self):
        from temporal.client import get_temporal_client, TEMPORAL_HOST
        assert callable(get_temporal_client)
        assert TEMPORAL_HOST


# ── FastAPI graceful degradation ──────────────────────────────────────────────

class TestTemporalDegradation:
    """Workflow endpoints must return 503 (not 500) when Temporal is unreachable."""

    @pytest.fixture(autouse=True)
    def patch_sla(self):
        import workers.sla_worker as _sla
        _sla.start = lambda: None

    def test_start_returns_503_when_temporal_none(self):
        from starlette.testclient import TestClient
        from main import app

        async def _none():
            return None

        with patch("routers.workflows.get_temporal_client", side_effect=_none):
            client = TestClient(app)
            resp = client.post("/api/workflows/proposals/p1/start")
            assert resp.status_code == 503

    def test_transition_returns_503_when_temporal_none(self):
        from starlette.testclient import TestClient
        from main import app

        async def _none():
            return None

        with patch("routers.workflows.get_temporal_client", side_effect=_none):
            client = TestClient(app)
            resp = client.post(
                "/api/workflows/proposals/p1/transition",
                json={"to_stage": "qualification"},
            )
            assert resp.status_code == 503

    def test_status_returns_503_when_temporal_none(self):
        from starlette.testclient import TestClient
        from main import app

        async def _none():
            return None

        with patch("routers.workflows.get_temporal_client", side_effect=_none):
            client = TestClient(app)
            resp = client.get("/api/workflows/proposals/p1/status")
            assert resp.status_code == 503


# ── Workflow integration tests ────────────────────────────────────────────────

@pytest.mark.asyncio
class TestWorkflowIntegration:
    """
    Full workflow round-trips using Temporal's embedded time-skipping test server.

    Activities are mocked so tests run without a real DB or Redis.
    WorkflowEnvironment.start_time_skipping() downloads the test server binary
    on first run (bundled with temporalio SDK).
    """

    @pytest.fixture
    def mock_activities(self):
        """
        Async mock functions matching real activity names.
        Async activities run in the event loop — no thread pool executor needed.
        """
        from temporalio import activity
        from temporal.schemas import (
            TransitionInput, TransitionResult,
            InitParallelApprovalsInput, ApprovalActivityInput,
            EventInput, EscalationInput,
        )

        @activity.defn(name="persist_stage_transition")
        async def mock_transition(inp: TransitionInput):
            return TransitionResult(success=True, stage=inp.to_stage)

        @activity.defn(name="initialize_parallel_approvals")
        async def mock_init_approvals(inp: InitParallelApprovalsInput):
            return list(inp.review_stages)

        @activity.defn(name="emit_workflow_event")
        async def mock_emit(inp: EventInput):
            pass

        @activity.defn(name="persist_approval_decision")
        async def mock_decision(inp: ApprovalActivityInput):
            return {"approval_id": inp.approval_id, "status": inp.status}

        @activity.defn(name="escalate_sla")
        async def mock_escalate(inp: EscalationInput):
            pass

        return [mock_transition, mock_init_approvals, mock_emit, mock_decision, mock_escalate]

    async def test_proposal_workflow_starts_and_answers_queries(self, mock_activities):
        from temporalio.testing import WorkflowEnvironment
        from temporalio.worker import Worker
        from temporal.workflows.proposal import ProposalLifecycleWorkflow
        from temporal.schemas import ProposalWorkflowInput, TASK_QUEUE
        import asyncio

        async with await WorkflowEnvironment.start_time_skipping() as env:
            async with Worker(
                env.client,
                task_queue=TASK_QUEUE,
                workflows=[ProposalLifecycleWorkflow],
                activities=mock_activities,
            ):
                handle = await env.client.start_workflow(
                    ProposalLifecycleWorkflow.run,
                    ProposalWorkflowInput(proposal_id="p-integ-001"),
                    id="proposal-p-integ-001",
                    task_queue=TASK_QUEUE,
                )

                # Immediately after start, workflow is in intake
                stage = await handle.query(ProposalLifecycleWorkflow.get_stage)
                assert stage == "intake"

                is_active = await handle.query(ProposalLifecycleWorkflow.is_active)
                assert is_active is True

    async def test_signal_advances_stage(self, mock_activities):
        from temporalio.testing import WorkflowEnvironment
        from temporalio.worker import Worker
        from temporal.workflows.proposal import ProposalLifecycleWorkflow
        from temporal.schemas import ProposalWorkflowInput, TASK_QUEUE
        import asyncio

        async with await WorkflowEnvironment.start_time_skipping() as env:
            async with Worker(
                env.client,
                task_queue=TASK_QUEUE,
                workflows=[ProposalLifecycleWorkflow],
                activities=mock_activities,
            ):
                handle = await env.client.start_workflow(
                    ProposalLifecycleWorkflow.run,
                    ProposalWorkflowInput(proposal_id="p-sig-001"),
                    id="proposal-p-sig-001",
                    task_queue=TASK_QUEUE,
                )

                await handle.signal(
                    ProposalLifecycleWorkflow.request_transition,
                    args=["qualification", "actor-1", None],
                )

                # Poll until workflow processes the signal
                for _ in range(10):
                    stage = await handle.query(ProposalLifecycleWorkflow.get_stage)
                    if stage == "qualification":
                        break
                    await asyncio.sleep(0.1)

                assert stage == "qualification"
                history = await handle.query(ProposalLifecycleWorkflow.get_history)
                assert len(history) == 1
                assert history[0]["from"] == "intake"
                assert history[0]["to"] == "qualification"

    async def test_cancel_signal_stops_workflow(self, mock_activities):
        from temporalio.testing import WorkflowEnvironment
        from temporalio.worker import Worker
        from temporal.workflows.proposal import ProposalLifecycleWorkflow
        from temporal.schemas import ProposalWorkflowInput, TASK_QUEUE
        import asyncio

        async with await WorkflowEnvironment.start_time_skipping() as env:
            async with Worker(
                env.client,
                task_queue=TASK_QUEUE,
                workflows=[ProposalLifecycleWorkflow],
                activities=mock_activities,
            ):
                handle = await env.client.start_workflow(
                    ProposalLifecycleWorkflow.run,
                    ProposalWorkflowInput(proposal_id="p-cancel-001"),
                    id="proposal-p-cancel-001",
                    task_queue=TASK_QUEUE,
                )

                await handle.signal(ProposalLifecycleWorkflow.cancel)

                for _ in range(10):
                    active = await handle.query(ProposalLifecycleWorkflow.is_active)
                    if not active:
                        break
                    await asyncio.sleep(0.1)

                assert active is False

    async def test_parallel_review_waits_for_all_decisions(self, mock_activities):
        from temporalio.testing import WorkflowEnvironment
        from temporalio.worker import Worker
        from temporal.workflows.approval import ParallelReviewWorkflow
        from temporal.schemas import ParallelReviewInput, PARALLEL_REVIEW_STAGES, TASK_QUEUE
        import asyncio

        async with await WorkflowEnvironment.start_time_skipping() as env:
            async with Worker(
                env.client,
                task_queue=TASK_QUEUE,
                workflows=[ParallelReviewWorkflow],
                activities=mock_activities,
            ):
                handle = await env.client.start_workflow(
                    ParallelReviewWorkflow.run,
                    ParallelReviewInput(proposal_id="p-rev-001", timeout_hours=72),
                    id="parallel-review-p-rev-001",
                    task_queue=TASK_QUEUE,
                )

                # Not complete yet
                assert await handle.query(ParallelReviewWorkflow.is_complete) is False

                # Submit all 3 reviews
                for stage in sorted(PARALLEL_REVIEW_STAGES):
                    await handle.signal(
                        ParallelReviewWorkflow.submit_review,
                        args=[stage, "approved", "reviewer-1", None],
                    )

                # Wait for completion
                for _ in range(20):
                    if await handle.query(ParallelReviewWorkflow.is_complete):
                        break
                    await asyncio.sleep(0.1)

                result = await handle.result()
                assert result.all_approved is True
                assert len(result.decisions) == 3

    async def test_sla_workflow_resolves_before_breach(self, mock_activities):
        from temporalio.testing import WorkflowEnvironment
        from temporalio.worker import Worker
        from temporal.workflows.sla import SlaEscalationWorkflow
        from temporal.schemas import SlaInput, TASK_QUEUE
        import asyncio

        async with await WorkflowEnvironment.start_time_skipping() as env:
            async with Worker(
                env.client,
                task_queue=TASK_QUEUE,
                workflows=[SlaEscalationWorkflow],
                activities=mock_activities,
            ):
                handle = await env.client.start_workflow(
                    SlaEscalationWorkflow.run,
                    SlaInput(
                        proposal_id="p-sla-001",
                        opportunity_id="o-sla-001",
                        stage="drafting",
                        sla_hours=48,
                    ),
                    id="sla-p-sla-001-drafting",
                    task_queue=TASK_QUEUE,
                )

                # Resolve before SLA fires
                await handle.signal(SlaEscalationWorkflow.resolve)

                for _ in range(10):
                    if await handle.query(SlaEscalationWorkflow.is_resolved):
                        break
                    await asyncio.sleep(0.1)

                # time-skipping env: skip past the 48h timer
                await env.sleep(48 * 3600 + 1)

                result = await handle.result()
                assert result["breached"] is False

    async def test_sla_workflow_breaches_on_timeout(self, mock_activities):
        from temporalio.testing import WorkflowEnvironment
        from temporalio.worker import Worker
        from temporal.workflows.sla import SlaEscalationWorkflow
        from temporal.schemas import SlaInput, TASK_QUEUE
        import asyncio

        async with await WorkflowEnvironment.start_time_skipping() as env:
            async with Worker(
                env.client,
                task_queue=TASK_QUEUE,
                workflows=[SlaEscalationWorkflow],
                activities=mock_activities,
            ):
                handle = await env.client.start_workflow(
                    SlaEscalationWorkflow.run,
                    SlaInput(
                        proposal_id="p-sla-breach-001",
                        opportunity_id="o-sla-breach-001",
                        stage="drafting",
                        sla_hours=24,
                    ),
                    id="sla-p-sla-breach-001-drafting",
                    task_queue=TASK_QUEUE,
                )

                # Skip past SLA without resolving
                await env.sleep(25 * 3600)

                result = await handle.result()
                assert result["breached"] is True
