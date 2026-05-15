import uuid
from datetime import datetime
from sqlalchemy import String, Integer, Text, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db.database import Base


class Stakeholder(Base):
    __tablename__ = "stakeholders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str | None] = mapped_column(Text)
    bu: Mapped[str | None] = mapped_column(Text)
    expertise: Mapped[list] = mapped_column(JSON, default=list)
    current_workload: Mapped[int] = mapped_column(Integer, default=0)
    email: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    assignments = relationship("Assignment", back_populates="stakeholder")
    approvals = relationship("Approval", back_populates="approver")
