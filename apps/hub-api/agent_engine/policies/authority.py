from agent_engine.config import AUTHORITY_LEVELS, APPROVAL_REQUIRED_AGENTS


def check_authority(agent_type: str, requested_level: str) -> tuple[bool, str]:
    """
    Returns (allowed, reason). Blocks any agent trying to claim an authority
    level beyond what its class declares, or any agent in APPROVAL_REQUIRED_AGENTS
    from being treated as completed without human sign-off.
    """
    if requested_level not in AUTHORITY_LEVELS:
        return False, f"Unknown authority level: {requested_level!r}"

    if agent_type in APPROVAL_REQUIRED_AGENTS and requested_level == "execute":
        return False, f"Agent {agent_type!r} cannot hold execute authority — approval required"

    return True, "ok"


def requires_human_approval(agent_type: str) -> bool:
    return agent_type in APPROVAL_REQUIRED_AGENTS


def get_max_authority(agent_type: str) -> str:
    if agent_type in APPROVAL_REQUIRED_AGENTS:
        return "draft"
    return "recommend"
