import os

# Stage weights for revenue forecasting (probability of closing from this stage)
STAGE_CLOSE_WEIGHTS: dict[str, float] = {
    "intake": 0.05,
    "qualification": 0.10,
    "sme_assignment": 0.15,
    "drafting": 0.20,
    "technical_review": 0.40,
    "security_review": 0.40,
    "delivery_review": 0.40,
    "finance_review": 0.55,
    "legal_review": 0.60,
    "approval": 0.75,
    "submission": 0.82,
    "client_followup": 0.88,
    "closed_won": 1.00,
    "closed_lost": 0.00,
}

# Stage ordering for progress scoring
STAGE_ORDER: list[str] = [
    "intake", "qualification", "sme_assignment", "drafting",
    "technical_review", "security_review", "delivery_review",
    "finance_review", "legal_review", "approval",
    "submission", "client_followup", "closed_won",
]

TERMINAL_STAGES = frozenset({"closed_won", "closed_lost"})
WIN_STAGES = frozenset({"closed_won"})
ACTIVE_STAGES = frozenset(s for s in STAGE_ORDER if s not in TERMINAL_STAGES)

# Capacity thresholds
SME_SATURATION_WORKLOAD = int(os.getenv("SME_SATURATION_WORKLOAD", "10"))
SME_WARNING_WORKLOAD = int(os.getenv("SME_WARNING_WORKLOAD", "7"))
APPROVAL_BOTTLENECK_THRESHOLD = int(os.getenv("APPROVAL_BOTTLENECK_THRESHOLD", "3"))
BURNOUT_WORKLOAD_RATIO = float(os.getenv("BURNOUT_WORKLOAD_RATIO", "0.9"))

# Escalation thresholds
ESCALATION_HIGH_THRESHOLD = float(os.getenv("ESCALATION_HIGH_THRESHOLD", "0.65"))
ESCALATION_MEDIUM_THRESHOLD = float(os.getenv("ESCALATION_MEDIUM_THRESHOLD", "0.40"))

# Economics constants
HOURLY_RATE_CR = float(os.getenv("HOURLY_RATE_CR", "0.015"))  # Cr per hour
SME_HOURS_PER_PROPOSAL = float(os.getenv("SME_HOURS_PER_PROPOSAL", "8.0"))
APPROVAL_COST_PER_DAY_CR = float(os.getenv("APPROVAL_COST_PER_DAY_CR", "0.005"))
REVIEW_HOURS_PER_STAGE = float(os.getenv("REVIEW_HOURS_PER_STAGE", "4.0"))

# Forecast windows
FORECAST_QUARTER_DAYS = 90
FORECAST_ROLLING_DAYS = int(os.getenv("FORECAST_ROLLING_DAYS", "30"))
CONFIDENCE_SPREAD_FACTOR = float(os.getenv("CONFIDENCE_SPREAD_FACTOR", "0.20"))

# Pipeline health thresholds
PIPELINE_HEALTH_GREEN = 70
PIPELINE_HEALTH_YELLOW = 45
PIPELINE_HEALTH_RED = 0

# Win probability bounds
WIN_PROB_FLOOR = 0.03
WIN_PROB_CEIL = 0.97

# Simulation caps
MAX_SIMULATION_PROPOSALS = int(os.getenv("MAX_SIMULATION_PROPOSALS", "500"))
