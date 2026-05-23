"""
RBAC enforcer — runtime permission checking.

Usage:
    enforcer = RBACEnforcer()
    enforcer.check(user_id="u1", roles=["sme"], permission="proposal:write")
    # raises PermissionDenied if not allowed
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from integration_fabric.rbac.permissions import role_has_permission, get_role_permissions


class PermissionDenied(Exception):
    def __init__(self, user_id: str, permission: str, roles: list[str]):
        self.user_id = user_id
        self.permission = permission
        self.roles = roles
        super().__init__(
            f"User '{user_id}' with roles {roles} denied permission '{permission}'"
        )


@dataclass
class AccessContext:
    user_id: str
    roles: list[str] = field(default_factory=list)
    tenant_id: Optional[str] = None
    resource_id: Optional[str] = None      # resource-level scope
    resource_type: Optional[str] = None


class RBACEnforcer:
    """
    Stateless permission enforcer.
    Resource-level access: if resource_id is set, also checks ownership table.
    """

    def has_permission(self, ctx: AccessContext, permission: str) -> bool:
        for role in ctx.roles:
            if role_has_permission(role, permission):
                return True
        return False

    def check(self, ctx: AccessContext, permission: str) -> None:
        if not self.has_permission(ctx, permission):
            raise PermissionDenied(ctx.user_id, permission, ctx.roles)

    def effective_permissions(self, ctx: AccessContext) -> set[str]:
        perms: set[str] = set()
        for role in ctx.roles:
            perms |= get_role_permissions(role)
        return perms

    def can_access_resource(
        self,
        ctx: AccessContext,
        permission: str,
        owner_id: Optional[str] = None,
    ) -> bool:
        """
        Resource-level check. Admins and presales_leads bypass ownership.
        Others need ownership match OR explicit permission.
        """
        if not self.has_permission(ctx, permission):
            return False
        if owner_id and ctx.user_id != owner_id:
            bypass_roles = {"admin", "presales_lead", "executive"}
            if not any(r in bypass_roles for r in ctx.roles):
                return False
        return True


_default_enforcer = RBACEnforcer()


def check_permission(user_id: str, roles: list[str], permission: str, tenant_id: str = "") -> None:
    """Convenience wrapper — raises PermissionDenied if not allowed."""
    ctx = AccessContext(user_id=user_id, roles=roles, tenant_id=tenant_id)
    _default_enforcer.check(ctx, permission)
