import uuid
from datetime import datetime, date
from decimal import Decimal
from sqlalchemy import String, Integer, Text, DateTime, Date, Numeric, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db.database import Base


class Client(Base):
    __tablename__ = "clients"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(Text, nullable=False)
    sector: Mapped[str | None] = mapped_column(Text)
    region: Mapped[str | None] = mapped_column(Text)
    tier: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    opportunities = relationship("Opportunity", back_populates="client")


class Opportunity(Base):
    __tablename__ = "opportunities"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    client_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("clients.id"))
    title: Mapped[str] = mapped_column(Text, nullable=False)
    rfp_type: Mapped[str | None] = mapped_column(Text)
    deal_value_cr: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    win_probability: Mapped[int] = mapped_column(Integer, default=50)
    stage: Mapped[str] = mapped_column(Text, default="intake")
    owner_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("stakeholders.id"))
    deadline: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    client = relationship("Client", back_populates="opportunities")
    owner = relationship("Stakeholder", foreign_keys=[owner_id])
    proposal = relationship("Proposal", back_populates="opportunity", uselist=False)
