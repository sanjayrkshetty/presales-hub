"""
Platform IAM — tenant-scoped custom roles and role assignments.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


@dataclass
class RoleInfo:
    tenant_id: str
    role_name: str
    permissions: list[str]
    inherits_from: Optional[str]
    description: str


class PlatformIAM:
    def __init__(self, db: "Session"):
        self.db = db

    def create_role(
        self,
        tenant_id: str,
        role_name: str,
        permissions: list[str],
        inherits_from: Optional[str] = None,
        description: str = "",
    ) -> "TenantRole":
        from models.tenant import TenantRole

        role = TenantRole(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            role_name=role_name,
            permissions=permissions,
            inherits_from=inherits_from,
            description=description,
            created_at=datetime.utcnow(),
        )
        self.db.add(role)
        self.db.flush()
        return role

    def get_role(self, tenant_id: str, role_name: str) -> Optional["TenantRole"]:
        from sqlalchemy import select
        from models.tenant import TenantRole

        return self.db.scalars(
            select(TenantRole)
            .where(TenantRole.tenant_id == tenant_id)
            .where(TenantRole.role_name == role_name)
        ).first()

    def list_roles(self, tenant_id: str) -> list:
        from sqlalchemy import select
        from models.tenant import TenantRole

        return list(
            self.db.scalars(
                select(TenantRole).where(TenantRole.tenant_id == tenant_id)
            ).all()
        )

    def assign_role(
        self,
        tenant_id: str,
        user_id: str,
        role_name: str,
        granted_by: str = "system",
        expires_at: Optional[datetime] = None,
    ) -> "TenantRoleAssignment":
        from models.tenant import TenantRoleAssignment

        assignment = TenantRoleAssignment(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            user_id=user_id,
            role_name=role_name,
            granted_by=granted_by,
            granted_at=datetime.utcnow(),
            expires_at=expires_at,
        )
        self.db.add(assignment)
        self.db.flush()
        return assignment

    def revoke_role(self, tenant_id: str, user_id: str, role_name: str) -> bool:
        from sqlalchemy import delete
        from models.tenant import TenantRoleAssignment

        result = self.db.execute(
            delete(TenantRoleAssignment)
            .where(TenantRoleAssignment.tenant_id == tenant_id)
            .where(TenantRoleAssignment.user_id == user_id)
            .where(TenantRoleAssignment.role_name == role_name)
        )
        self.db.flush()
        return result.rowcount > 0

    def get_user_roles(self, tenant_id: str, user_id: str) -> list[str]:
        from sqlalchemy import select
        from models.tenant import TenantRoleAssignment

        rows = list(
            self.db.scalars(
                select(TenantRoleAssignment)
                .where(TenantRoleAssignment.tenant_id == tenant_id)
                .where(TenantRoleAssignment.user_id == user_id)
            ).all()
        )
        return [r.role_name for r in rows]

    def get_effective_permissions(self, tenant_id: str, user_id: str) -> set[str]:
        roles = self.get_user_roles(tenant_id, user_id)
        perms: set[str] = set()
        for role_name in roles:
            role = self.get_role(tenant_id, role_name)
            if role:
                perms.update(role.permissions)
                # Resolve inherited permissions
                if role.inherits_from:
                    parent = self.get_role(tenant_id, role.inherits_from)
                    if parent:
                        perms.update(parent.permissions)
        return perms
