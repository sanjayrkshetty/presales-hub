"""
TenantAwareRepository — ABC that enforces tenant_id on all queries.

Subclasses override _model and all queries are automatically scoped.
Prevents cross-tenant data leakage at the data access layer.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class TenantAwareRepository(ABC):
    """
    Base repository that auto-scopes all queries to a single tenant.
    Subclasses must set _model to the SQLAlchemy model class.
    """

    def __init__(self, db: "Session", tenant_id: str):
        self.db = db
        self.tenant_id = tenant_id

    @property
    @abstractmethod
    def _model(self):
        """SQLAlchemy model class with a tenant_id column."""

    def _base_query(self):
        from sqlalchemy import select
        return select(self._model).where(self._model.tenant_id == self.tenant_id)

    def get(self, record_id: str) -> Optional[object]:
        row = self.db.get(self._model, record_id)
        if row is None or getattr(row, "tenant_id", None) != self.tenant_id:
            return None
        return row

    def list(self, limit: int = 100, offset: int = 0) -> list:
        return list(
            self.db.scalars(
                self._base_query().limit(limit).offset(offset)
            ).all()
        )

    def count(self) -> int:
        from sqlalchemy import select, func
        return self.db.scalar(
            select(func.count())
            .select_from(self._model)
            .where(self._model.tenant_id == self.tenant_id)
        ) or 0

    def delete_all(self) -> int:
        from sqlalchemy import delete
        result = self.db.execute(
            delete(self._model).where(self._model.tenant_id == self.tenant_id)
        )
        self.db.flush()
        return result.rowcount

    def assert_tenant_owns(self, record_id: str) -> object:
        row = self.get(record_id)
        if row is None:
            raise PermissionError(
                f"Record {record_id!r} not found or not owned by tenant {self.tenant_id!r}"
            )
        return row
