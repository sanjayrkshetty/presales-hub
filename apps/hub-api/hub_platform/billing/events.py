"""Billing event type constants."""
from __future__ import annotations

USAGE_CHARGE = "usage_charge"
PLAN_CHANGE = "plan_change"
OVERAGE = "overage"
CREDIT = "credit"
REFUND = "refund"
QUOTA_BREACH = "quota_breach"
TRIAL_START = "trial_start"
TRIAL_END = "trial_end"

RESOURCE_TYPES = {
    "api_call", "token", "workflow", "storage_mb",
    "agent_execution", "simulation", "connector_sync",
}
