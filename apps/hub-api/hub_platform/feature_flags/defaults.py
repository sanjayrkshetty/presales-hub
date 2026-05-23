"""Default feature flags per tenant tier."""
from __future__ import annotations

# flag_name → enabled (True/False) per tier
# Flags not listed = disabled for that tier
DEFAULT_FLAGS_BY_TIER: dict[str, dict[str, bool]] = {
    "free": {
        "proposal_ai_assist":       False,
        "advanced_analytics":       False,
        "multi_agent_workflows":    False,
        "crm_integration":          False,
        "api_access":               True,
        "basic_templates":          True,
        "email_notifications":      True,
        "single_sso":               False,
        "audit_logs":               False,
        "custom_roles":             False,
        "data_export":              False,
        "sandbox_environment":      False,
        "beta_features":            False,
    },
    "starter": {
        "proposal_ai_assist":       True,
        "advanced_analytics":       False,
        "multi_agent_workflows":    False,
        "crm_integration":          True,
        "api_access":               True,
        "basic_templates":          True,
        "email_notifications":      True,
        "single_sso":               True,
        "audit_logs":               True,
        "custom_roles":             False,
        "data_export":              True,
        "sandbox_environment":      False,
        "beta_features":            False,
    },
    "professional": {
        "proposal_ai_assist":       True,
        "advanced_analytics":       True,
        "multi_agent_workflows":    True,
        "crm_integration":          True,
        "api_access":               True,
        "basic_templates":          True,
        "email_notifications":      True,
        "single_sso":               True,
        "audit_logs":               True,
        "custom_roles":             True,
        "data_export":              True,
        "sandbox_environment":      True,
        "beta_features":            False,
    },
    "enterprise": {
        "proposal_ai_assist":       True,
        "advanced_analytics":       True,
        "multi_agent_workflows":    True,
        "crm_integration":          True,
        "api_access":               True,
        "basic_templates":          True,
        "email_notifications":      True,
        "single_sso":               True,
        "audit_logs":               True,
        "custom_roles":             True,
        "data_export":              True,
        "sandbox_environment":      True,
        "beta_features":            True,
    },
}

# Flags that are always gated regardless of tier setting
EMERGENCY_DISABLED_FLAGS: set[str] = set()

# Minimum tier required for each flag (for tier-gating checks)
FLAG_TIER_MINIMUMS: dict[str, str] = {
    "proposal_ai_assist":    "starter",
    "advanced_analytics":    "professional",
    "multi_agent_workflows": "professional",
    "crm_integration":       "starter",
    "single_sso":            "starter",
    "audit_logs":            "starter",
    "custom_roles":          "professional",
    "data_export":           "starter",
    "sandbox_environment":   "professional",
    "beta_features":         "enterprise",
}
