import os

AGENT_DEFAULT_TIMEOUT_SECONDS = int(os.getenv("AGENT_DEFAULT_TIMEOUT", "120"))
AGENT_MAX_RETRIES = int(os.getenv("AGENT_MAX_RETRIES", "3"))
AGENT_MAX_TOOL_CALLS = int(os.getenv("AGENT_MAX_TOOL_CALLS", "10"))
AGENT_CONFIDENCE_THRESHOLD = float(os.getenv("AGENT_CONFIDENCE_THRESHOLD", "0.6"))
AGENT_MAX_INPUT_LENGTH = int(os.getenv("AGENT_MAX_INPUT_LENGTH", "4000"))

AUTHORITY_LEVELS = ["read_only", "recommend", "draft"]

# Agents that must pause for human approval before result is delivered
APPROVAL_REQUIRED_AGENTS = {
    "proposal_drafting",
    "escalation",
    "sme_coordination",
    "timeline_planning",
}

AGENT_TIMEOUTS: dict[str, int] = {
    "rfp_analysis": 90,
    "proposal_drafting": 180,
    "risk_assessment": 60,
    "compliance_check": 90,
    "sme_coordination": 120,
    "executive_briefing": 60,
    "approval_reasoning": 60,
    "solution_architecture": 120,
    "timeline_planning": 120,
    "escalation": 60,
}
