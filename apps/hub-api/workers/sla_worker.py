import threading
import time
import logging
from datetime import datetime
from sqlalchemy import select

from db.database import SessionLocal
from models import Opportunity, SlaConfig, ActivityFeed

logger = logging.getLogger("sla_worker")

_CHECK_INTERVAL = 300  # 5 minutes

# B3: Keyed by (opp_id, stage) so re-entry to a new stage fires a fresh alert.
# Using opp_id alone caused silent misses after stage transitions.
_BREACHED_IDS: set[tuple[str, str]] = set()


def _check_slas():
    db = SessionLocal()
    try:
        opps = db.scalars(select(Opportunity)).all()
        sla_map = {s.stage: s.hours_allowed for s in db.scalars(select(SlaConfig)).all()}

        for opp in opps:
            if opp.stage in ("closed_won", "closed_lost"):
                continue
            hours = sla_map.get(opp.stage)
            if not hours:
                continue

            elapsed = (datetime.utcnow() - (opp.updated_at or opp.created_at)).total_seconds() / 3600
            breach_key = (str(opp.id), opp.stage)

            if elapsed > hours and breach_key not in _BREACHED_IDS:
                _BREACHED_IDS.add(breach_key)
                overdue = round(elapsed - hours, 1)
                logger.warning(f"SLA BREACH: {opp.title} [{opp.stage}] — {overdue}h overdue")

                if opp.proposal:
                    db.add(ActivityFeed(
                        proposal_id=opp.proposal.id,
                        actor_name="SLA Monitor",
                        action_type="sla_breach",
                        description=f"SLA breached: {opp.stage.replace('_', ' ').title()} overdue by {overdue}h",
                        is_alert=True,
                    ))

        db.commit()
    except Exception:
        logger.exception("SLA check failed")
    finally:
        db.close()


def _run():
    logger.info("SLA worker started")
    while True:
        _check_slas()
        time.sleep(_CHECK_INTERVAL)


def start():
    t = threading.Thread(target=_run, daemon=True, name="sla-worker")
    t.start()
    return t
