"""
Tests for the event-driven architecture:
  - Event schema serialization / field validation
  - bus.publish() degrades gracefully when Redis is unavailable
  - broadcaster.fanout() delivers to all registered WS clients
  - broadcaster.fanout() drops dead clients silently
"""
import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from events.schema import (
    ProposalTransitionedEvent,
    ApprovalDecisionEvent,
    SlaBreachEvent,
    SmeAssignedEvent,
)
from events.broadcaster import WebSocketBroadcaster


# ── Schema serialization ───────────────────────────────────────────────────────

class TestEventSchema:
    def test_proposal_transitioned_required_fields(self):
        ev = ProposalTransitionedEvent(
            entity_id="prop-1",
            from_stage="drafting",
            to_stage="technical_review",
        )
        assert ev.event_type == "proposal.transitioned"
        assert ev.entity_type == "proposal"
        assert ev.from_stage == "drafting"
        assert ev.to_stage == "technical_review"
        assert ev.event_id  # auto-generated UUID
        assert ev.timestamp  # auto-generated

    def test_approval_decision_event(self):
        ev = ApprovalDecisionEvent(
            entity_id="appr-1",
            proposal_id="prop-1",
            stage="technical_review",
            status="approved",
        )
        assert ev.event_type == "approval.decision"
        assert ev.status == "approved"

    def test_sla_breach_event(self):
        ev = SlaBreachEvent(
            entity_id="opp-1",
            stage="drafting",
            overdue_hours=3.5,
        )
        assert ev.event_type == "sla.breach"
        assert ev.overdue_hours == 3.5

    def test_sme_assigned_event(self):
        ev = SmeAssignedEvent(
            entity_id="prop-1",
            sme_id="sme-1",
            sme_name="Alice",
            rfp_type="cloud_migration",
        )
        assert ev.event_type == "sme.assigned"
        assert ev.sme_name == "Alice"

    def test_to_json_roundtrip(self):
        ev = ProposalTransitionedEvent(
            entity_id="prop-1",
            from_stage="intake",
            to_stage="qualification",
            actor_id="user-1",
        )
        payload = json.loads(ev.to_json())
        assert payload["event_type"] == "proposal.transitioned"
        assert payload["actor_id"] == "user-1"
        assert payload["entity_id"] == "prop-1"

    def test_metadata_default_is_empty_dict(self):
        ev = SlaBreachEvent(entity_id="o1", stage="drafting", overdue_hours=1.0)
        assert ev.metadata == {}

    def test_each_event_gets_unique_id(self):
        a = SlaBreachEvent(entity_id="o1", stage="drafting", overdue_hours=1.0)
        b = SlaBreachEvent(entity_id="o1", stage="drafting", overdue_hours=1.0)
        assert a.event_id != b.event_id


# ── bus.publish() graceful degradation ────────────────────────────────────────

class TestBusPublish:
    def test_publish_no_op_when_sync_client_is_none(self):
        """publish() must not raise even when sync_client is None."""
        import events.bus as bus_mod
        ev = SlaBreachEvent(entity_id="o1", stage="drafting", overdue_hours=2.0)
        original = bus_mod.sync_client
        try:
            bus_mod.sync_client = None
            bus_mod.publish(ev)  # must not raise
        finally:
            bus_mod.sync_client = original

    def test_publish_swallows_redis_error(self):
        """publish() must not propagate exceptions from redis.publish()."""
        import events.bus as bus_mod
        ev = SlaBreachEvent(entity_id="o1", stage="drafting", overdue_hours=2.0)
        mock_client = MagicMock()
        mock_client.publish.side_effect = ConnectionError("Redis down")
        original = bus_mod.sync_client
        try:
            bus_mod.sync_client = mock_client
            bus_mod.publish(ev)  # must not raise
        finally:
            bus_mod.sync_client = original

    def test_publish_calls_redis_with_correct_channel(self):
        import events.bus as bus_mod
        from events.redis_client import EVENTS_CHANNEL
        ev = ProposalTransitionedEvent(
            entity_id="prop-1", from_stage="intake", to_stage="qualification"
        )
        mock_client = MagicMock()
        original = bus_mod.sync_client
        try:
            bus_mod.sync_client = mock_client
            bus_mod.publish(ev)
            mock_client.publish.assert_called_once()
            channel_arg = mock_client.publish.call_args[0][0]
            assert channel_arg == EVENTS_CHANNEL
        finally:
            bus_mod.sync_client = original


# ── WebSocketBroadcaster ───────────────────────────────────────────────────────

class TestBroadcaster:
    def _run(self, coro):
        return asyncio.run(coro)

    def _make_ws(self, raises=False):
        ws = AsyncMock()
        if raises:
            ws.send_text.side_effect = Exception("connection closed")
        return ws

    def test_register_and_fanout(self):
        bc = WebSocketBroadcaster()
        ws = self._make_ws()

        async def run():
            await bc.register(ws)
            await bc.fanout('{"event_type":"test"}')

        self._run(run())
        ws.send_text.assert_called_once_with('{"event_type":"test"}')

    def test_fanout_to_multiple_clients(self):
        bc = WebSocketBroadcaster()
        ws1, ws2, ws3 = self._make_ws(), self._make_ws(), self._make_ws()

        async def run():
            await bc.register(ws1)
            await bc.register(ws2)
            await bc.register(ws3)
            await bc.fanout("hello")

        self._run(run())
        for ws in (ws1, ws2, ws3):
            ws.send_text.assert_called_once_with("hello")

    def test_dead_client_removed_silently(self):
        bc = WebSocketBroadcaster()
        live = self._make_ws()
        dead = self._make_ws(raises=True)

        async def run():
            await bc.register(live)
            await bc.register(dead)
            await bc.fanout("msg")
            return len(bc._clients)

        count = self._run(run())
        assert count == 1
        live.send_text.assert_called_once_with("msg")

    def test_unregister_removes_client(self):
        bc = WebSocketBroadcaster()
        ws = self._make_ws()

        async def run():
            await bc.register(ws)
            await bc.unregister(ws)
            await bc.fanout("should not arrive")

        self._run(run())
        ws.send_text.assert_not_called()

    def test_fanout_empty_set_is_noop(self):
        bc = WebSocketBroadcaster()

        async def run():
            await bc.fanout("irrelevant")

        self._run(run())  # no exception
