from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from db.database import get_db
from models import Stakeholder, Assignment

router = APIRouter(prefix="/api/stakeholders", tags=["stakeholders"])


@router.get("")
def list_stakeholders(db: Session = Depends(get_db)):
    stakeholders = db.scalars(select(Stakeholder).order_by(Stakeholder.name)).all()

    result = []
    for s in stakeholders:
        active_assignments = db.scalars(
            select(Assignment)
            .where(Assignment.stakeholder_id == s.id)
            .where(Assignment.status.in_(["pending", "in_progress"]))
        ).all()

        result.append({
            "id": s.id,
            "name": s.name,
            "role": s.role,
            "bu": s.bu,
            "expertise": s.expertise or [],
            "current_workload": s.current_workload,
            "email": s.email,
            "active_proposals": len(active_assignments),
        })

    return result
