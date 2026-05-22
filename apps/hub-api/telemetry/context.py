"""
Request-scoped context propagation via Python ContextVars.

These propagate automatically:
- across `await` boundaries within the same async task
- into thread-pool workers when Starlette dispatches sync route handlers
  (Starlette copies the context when calling run_in_executor)

They do NOT propagate:
- across threading.Thread (background workers start fresh contexts)
- across subprocess boundaries
"""
import uuid
from contextvars import ContextVar

_correlation_id: ContextVar[str] = ContextVar("correlation_id", default="")
_request_id: ContextVar[str] = ContextVar("request_id", default="")
_actor_id: ContextVar[str] = ContextVar("actor_id", default="")
_proposal_id: ContextVar[str] = ContextVar("proposal_id", default="")
_workflow_id: ContextVar[str] = ContextVar("workflow_id", default="")


def get_correlation_id() -> str:
    return _correlation_id.get()


def get_request_id() -> str:
    return _request_id.get()


def get_actor_id() -> str:
    return _actor_id.get()


def get_proposal_id() -> str:
    return _proposal_id.get()


def get_workflow_id() -> str:
    return _workflow_id.get()


def set_correlation_id(v: str) -> object:
    return _correlation_id.set(v)


def set_request_id(v: str) -> object:
    return _request_id.set(v)


def set_actor_id(v: str) -> object:
    return _actor_id.set(v)


def set_proposal_id(v: str) -> object:
    return _proposal_id.set(v)


def set_workflow_id(v: str) -> object:
    return _workflow_id.set(v)


def new_correlation_id() -> str:
    return str(uuid.uuid4())
