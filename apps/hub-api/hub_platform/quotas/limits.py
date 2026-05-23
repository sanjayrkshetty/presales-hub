"""Per-tier default quota limits."""
from __future__ import annotations

# Resource keys match UsageRecord.resource_type
# -1 = unlimited
DEFAULT_QUOTAS: dict[str, dict[str, int]] = {
    "free": {
        "api_calls":         1_000,
        "tokens":           50_000,
        "workflows":            10,
        "storage_mb":          500,
        "agents":                1,
        "simulations":           5,
        "connectors":            2,
    },
    "starter": {
        "api_calls":        10_000,
        "tokens":          500_000,
        "workflows":           100,
        "storage_mb":        5_000,
        "agents":                5,
        "simulations":          25,
        "connectors":            5,
    },
    "professional": {
        "api_calls":       100_000,
        "tokens":        5_000_000,
        "workflows":         1_000,
        "storage_mb":       50_000,
        "agents":               20,
        "simulations":         100,
        "connectors":           12,
    },
    "enterprise": {
        "api_calls":            -1,  # unlimited
        "tokens":               -1,
        "workflows":            -1,
        "storage_mb":           -1,
        "agents":               -1,
        "simulations":          -1,
        "connectors":           -1,
    },
}

OVERAGE_RATES_USD: dict[str, float] = {
    "api_calls":    0.0001,   # per call
    "tokens":       0.00002,  # per token
    "workflows":    0.01,     # per execution
    "storage_mb":   0.00023,  # per MB-month (S3-class pricing)
    "agents":       0.05,     # per agent-hour
    "simulations":  0.02,     # per simulation
    "connectors":   1.0,      # per connector-month
}
