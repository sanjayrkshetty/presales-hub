"""
B3 — SLA Breach Tracking Logic regression tests.

Before the fix, _BREACHED_IDS was keyed by opp.id alone, so a breach alert fired
once per opportunity lifetime. After a stage transition, the opportunity would
silently miss breach detection in the new stage.

Fix: key is (opp_id, stage) so each stage entry gets an independent breach window.
"""
from datetime import datetime, timedelta

import pytest
from sqlalchemy.orm import sessionmaker

import workers.sla_worker as sla_mod
from tests._testdb import TEST_ENGINE
from models import Client, Opportunity, SlaConfig


def _make_session():
    Session = sessionmaker(autocommit=False, autoflush=False, bind=TEST_ENGINE)
    return Session()


@pytest.fixture(autouse=True)
def clear_breached_ids():
    """Reset module-level breach state before each test."""
    sla_mod._BREACHED_IDS.clear()
    yield
    sla_mod._BREACHED_IDS.clear()


@pytest.fixture(autouse=True)
def patch_sla_session(monkeypatch):
    """
    _check_slas() creates its own DB session via SessionLocal.
    Redirect it to the test engine so seeded data is visible.
    """
    monkeypatch.setattr(sla_mod, "SessionLocal", _make_session)


def _seed_overdue_opp(db, stage: str, hours_elapsed: int, sla_hours: int) -> Opportunity:
    db.merge(SlaConfig(stage=stage, hours_allowed=sla_hours, escalate_to_role="presales_lead"))

    client = Client(name=f"SLACo-{stage}")
    db.add(client)
    db.flush()

    opp = Opportunity(
        client_id=client.id,
        title=f"SLA Test — {stage}",
        stage=stage,
        created_at=datetime.utcnow() - timedelta(days=7),
        updated_at=datetime.utcnow() - timedelta(hours=hours_elapsed),
    )
    db.add(opp)
    db.commit()
    return opp


def test_b3_breach_key_is_tuple_of_opp_id_and_stage(db):
    """Breach key must be (opp_id, stage), not just opp_id."""
    opp = _seed_overdue_opp(db, stage="drafting", hours_elapsed=80, sla_hours=72)

    sla_mod._check_slas()

    assert (str(opp.id), "drafting") in sla_mod._BREACHED_IDS


def test_b3_stage_transition_fires_independent_breach(db):
    """
    After an opp breaches in stage A and transitions to stage B, a breach
    in stage B must fire independently — not be suppressed by the stage-A key.
    """
    opp = _seed_overdue_opp(db, stage="drafting", hours_elapsed=80, sla_hours=72)

    sla_mod._check_slas()
    assert (str(opp.id), "drafting") in sla_mod._BREACHED_IDS

    # Simulate stage transition: update opp stage and reset the elapsed timer to be overdue
    db.merge(SlaConfig(stage="qualification", hours_allowed=24, escalate_to_role="presales_lead"))
    opp.stage = "qualification"
    opp.updated_at = datetime.utcnow() - timedelta(hours=30)
    db.commit()

    sla_mod._check_slas()

    assert (str(opp.id), "qualification") in sla_mod._BREACHED_IDS


def test_b3_same_stage_breach_not_double_fired(db):
    """A breach already recorded for (opp_id, stage) must not fire again on next check."""
    opp = _seed_overdue_opp(db, stage="drafting", hours_elapsed=80, sla_hours=72)

    sla_mod._check_slas()
    first_breach_count = len(sla_mod._BREACHED_IDS)

    # Run again — should not add a duplicate
    sla_mod._check_slas()

    assert len(sla_mod._BREACHED_IDS) == first_breach_count


def test_b3_non_breached_opp_not_added(db):
    """An opp well within SLA must not appear in _BREACHED_IDS."""
    opp = _seed_overdue_opp(db, stage="drafting", hours_elapsed=10, sla_hours=72)

    sla_mod._check_slas()

    assert (str(opp.id), "drafting") not in sla_mod._BREACHED_IDS


def test_b3_closed_opps_skipped(db):
    """Closed opportunities must be skipped by the SLA worker regardless of elapsed time."""
    db.merge(SlaConfig(stage="closed_won", hours_allowed=1, escalate_to_role="presales_lead"))

    client = Client(name="ClosedCo")
    db.add(client)
    db.flush()

    opp = Opportunity(
        client_id=client.id,
        title="Already Won",
        stage="closed_won",
        created_at=datetime.utcnow() - timedelta(days=30),
        updated_at=datetime.utcnow() - timedelta(days=29),
    )
    db.add(opp)
    db.commit()

    sla_mod._check_slas()

    assert (str(opp.id), "closed_won") not in sla_mod._BREACHED_IDS
