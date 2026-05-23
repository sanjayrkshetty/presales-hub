"""
RBAC permission definitions.

Permission format: "{resource}:{action}"
Resources: proposal, opportunity, approval, stakeholder, integration, analytics,
           strategy, agent, memory, webhook, api_key, user
Actions:   read, write, delete, approve, execute, admin
"""
from __future__ import annotations

PERMISSIONS = {
    # Proposals
    "proposal:read", "proposal:write", "proposal:delete", "proposal:approve",
    # Opportunities
    "opportunity:read", "opportunity:write", "opportunity:delete",
    # Approvals
    "approval:read", "approval:write", "approval:approve",
    # Stakeholders
    "stakeholder:read", "stakeholder:write", "stakeholder:delete",
    # Integration
    "integration:read", "integration:write", "integration:admin",
    # Analytics + Strategy
    "analytics:read", "strategy:read", "strategy:write",
    # Agent + AI
    "agent:execute", "agent:read", "copilot:use",
    # Memory
    "memory:read", "memory:write", "memory:delete",
    # Webhooks
    "webhook:read", "webhook:write", "webhook:delete",
    # API keys
    "api_key:read", "api_key:write", "api_key:delete",
    # User management
    "user:read", "user:write", "user:admin",
}

# Role → permission set
ROLE_PERMISSIONS: dict[str, set[str]] = {
    "admin": set(PERMISSIONS),  # all permissions
    "presales_lead": {
        "proposal:read", "proposal:write", "proposal:approve",
        "opportunity:read", "opportunity:write",
        "approval:read", "approval:approve",
        "stakeholder:read", "stakeholder:write",
        "analytics:read", "strategy:read",
        "agent:execute", "agent:read", "copilot:use",
        "memory:read", "memory:write",
        "webhook:read",
        "integration:read",
    },
    "sme": {
        "proposal:read", "proposal:write",
        "opportunity:read",
        "approval:read",
        "stakeholder:read",
        "analytics:read",
        "agent:read", "copilot:use",
        "memory:read", "memory:write",
    },
    "executive": {
        "proposal:read",
        "opportunity:read",
        "approval:read", "approval:approve",
        "stakeholder:read",
        "analytics:read", "strategy:read",
        "agent:read",
        "memory:read",
        "integration:read",
        "webhook:read",
    },
    "approver": {
        "proposal:read",
        "opportunity:read",
        "approval:read", "approval:approve",
        "stakeholder:read",
        "analytics:read",
        "memory:read",
    },
    "analyst": {
        "proposal:read",
        "opportunity:read",
        "approval:read",
        "stakeholder:read",
        "analytics:read", "strategy:read",
        "memory:read",
    },
    "readonly": {
        "proposal:read",
        "opportunity:read",
        "approval:read",
        "stakeholder:read",
        "analytics:read",
    },
}


def get_role_permissions(role: str) -> set[str]:
    return ROLE_PERMISSIONS.get(role, set())


def role_has_permission(role: str, permission: str) -> bool:
    return permission in get_role_permissions(role)
