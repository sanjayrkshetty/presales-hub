"""
Langfuse observability helpers (Python SDK v3+).

Best practices applied:
  - Prefer get_client() + start_as_current_observation(as_type=...)
  - Use typed observations: chain / retriever / generation / guardrail / evaluator / embedding
  - Stable verb-first names (no dynamic IDs in names)
  - Explicit input/output (scrubbed), tags + environment via propagate_attributes
  - Graceful no-op when keys missing or SDK absent
"""
from __future__ import annotations

import logging
import os
from contextlib import contextmanager, nullcontext
from typing import Any, Iterator, Optional

logger = logging.getLogger("telemetry.langfuse")

_client = None
_client_attempted = False
_sdk_mode: Optional[str] = None  # "v3" | "v2" | None


def _ensure_env_loaded() -> None:
    """Load .env before Langfuse init (SDK reads LANGFUSE_* at client creation)."""
    try:
        from dotenv import load_dotenv
        from pathlib import Path

        # apps/hub-api cwd OR repo root
        here = Path(__file__).resolve()
        candidates = [
            Path.cwd() / ".env",
            here.parents[2] / ".env",          # repo root from apps/hub-api/telemetry/
            here.parents[1] / ".env",          # apps/hub-api/.env
        ]
        for p in candidates:
            if p.is_file():
                load_dotenv(p, override=False)
    except Exception:
        pass


def get_langfuse():
    """Return Langfuse client or None. Uses SDK v3 get_client when available."""
    global _client, _client_attempted, _sdk_mode
    if _client_attempted:
        return _client
    _client_attempted = True
    _ensure_env_loaded()

    # Prefer BASE_URL (current docs); fall back to HOST (legacy in this repo).
    base_url = (
        os.getenv("LANGFUSE_BASE_URL")
        or os.getenv("LANGFUSE_HOST")
        or "https://cloud.langfuse.com"
    )
    # Normalize for both env names so CLI + SDK agree
    os.environ.setdefault("LANGFUSE_BASE_URL", base_url)
    os.environ.setdefault("LANGFUSE_HOST", base_url)

    public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    secret_key = os.getenv("LANGFUSE_SECRET_KEY")
    if not public_key or not secret_key:
        return None

    try:
        from langfuse import get_client  # SDK v3+

        _client = get_client()
        _sdk_mode = "v3"
        logger.info("Langfuse v3 client ready (base_url=%s)", base_url)
        return _client
    except Exception as exc:
        logger.debug("Langfuse get_client failed (%s); trying legacy Langfuse()", exc)

    try:
        from langfuse import Langfuse  # type: ignore[import]

        _client = Langfuse(public_key=public_key, secret_key=secret_key, host=base_url)
        _sdk_mode = "v2"
        logger.info("Langfuse legacy client ready (host=%s)", base_url)
        return _client
    except ImportError:
        logger.warning("langfuse package not installed — AI telemetry disabled")
    except Exception as exc:
        logger.warning("Langfuse init failed: %s", exc)
    return None


def _env_name() -> str:
    return os.getenv("ENVIRONMENT") or os.getenv("LANGFUSE_TRACING_ENVIRONMENT") or "development"


@contextmanager
def observe_pipeline(
    name: str,
    *,
    as_type: str = "chain",
    input: Any = None,
    metadata: Optional[dict[str, Any]] = None,
    tags: Optional[list[str]] = None,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    feature: Optional[str] = None,
) -> Iterator[Any]:
    """
    Root observation for one unit of work (one Generate, one Copilot call, one ingest).

    Yields the observation object (v3) or legacy trace (v2) or None.
    """
    client = get_langfuse()
    if client is None:
        yield None
        return

    meta = {
        "correlation_id": _safe_ctx("get_correlation_id"),
        "proposal_id": _safe_ctx("get_proposal_id"),
        **(metadata or {}),
    }
    tag_list = list(tags or [])
    if feature and feature not in tag_list:
        tag_list.append(feature)
    tag_list.append(f"env:{_env_name()}")

    if _sdk_mode == "v3":
        try:
            from langfuse import propagate_attributes

            with client.start_as_current_observation(
                as_type=as_type,
                name=name,
                input=input,
                metadata=meta,
            ) as root:
                prop_kwargs: dict[str, Any] = {
                    "tags": tag_list,
                    "metadata": {"environment": _env_name()},
                }
                if user_id:
                    prop_kwargs["user_id"] = user_id
                if session_id:
                    prop_kwargs["session_id"] = session_id
                try:
                    ctx = propagate_attributes(**prop_kwargs)
                except TypeError:
                    # Older signature variants
                    ctx = nullcontext()
                with ctx:
                    try:
                        yield root
                    except Exception as exc:
                        try:
                            root.update(level="ERROR", status_message=str(exc)[:500])
                        except Exception:
                            pass
                        raise
                    finally:
                        try:
                            client.flush()
                        except Exception:
                            pass
            return
        except Exception as exc:
            logger.debug("v3 observe_pipeline failed, falling back: %s", exc)

    # Legacy v2 path
    try:
        trace = client.trace(
            name=name,
            input=input,
            metadata=meta,
            tags=tag_list,
            user_id=user_id,
            session_id=session_id,
        )
        try:
            yield trace
        except Exception as exc:
            try:
                trace.update(status_message=f"error: {exc}", level="ERROR")
            except Exception:
                pass
            raise
        finally:
            try:
                client.flush()
            except Exception:
                pass
    except Exception as exc:
        logger.debug("legacy observe_pipeline failed: %s", exc)
        yield None


@contextmanager
def observe_step(
    name: str,
    *,
    as_type: str = "span",
    input: Any = None,
    metadata: Optional[dict[str, Any]] = None,
    model: Optional[str] = None,
) -> Iterator[Any]:
    """Nested observation under the current pipeline (retriever/generation/guardrail/...)."""
    client = get_langfuse()
    if client is None or _sdk_mode != "v3":
        yield None
        return
    kwargs: dict[str, Any] = {
        "as_type": as_type,
        "name": name,
        "input": input,
        "metadata": metadata or {},
    }
    if model and as_type in {"generation", "embedding"}:
        kwargs["model"] = model
    try:
        with client.start_as_current_observation(**kwargs) as obs:
            yield obs
    except Exception as exc:
        logger.debug("observe_step(%s) failed: %s", name, exc)
        yield None


def update_observation(
    obs: Any,
    *,
    output: Any = None,
    input: Any = None,
    metadata: Optional[dict[str, Any]] = None,
    usage_details: Optional[dict[str, Any]] = None,
    model: Optional[str] = None,
    level: Optional[str] = None,
    status_message: Optional[str] = None,
) -> None:
    if obs is None:
        return
    payload: dict[str, Any] = {}
    if output is not None:
        payload["output"] = output
    if input is not None:
        payload["input"] = input
    if metadata is not None:
        payload["metadata"] = metadata
    if usage_details is not None:
        payload["usage_details"] = usage_details
    if model is not None:
        payload["model"] = model
    if level is not None:
        payload["level"] = level
    if status_message is not None:
        payload["status_message"] = status_message
    if not payload:
        return
    try:
        obs.update(**payload)
    except TypeError:
        # legacy generation() style objects may not support all kwargs
        try:
            obs.update(output=output, metadata=metadata or {})
        except Exception as exc:
            logger.debug("update_observation failed: %s", exc)
    except Exception as exc:
        logger.debug("update_observation failed: %s", exc)


def log_generation(
    parent: Any,
    *,
    name: str,
    model: str,
    input_text: str,
    output_text: str,
    provider: str = "",
    input_tokens: int = 0,
    output_tokens: int = 0,
    latency_ms: float = 0,
    metadata: Optional[dict[str, Any]] = None,
) -> None:
    """Record an LLM generation (works under v3 current context or legacy parent)."""
    if _sdk_mode == "v3":
        client = get_langfuse()
        if client is None:
            return
        try:
            with client.start_as_current_observation(
                as_type="generation",
                name=name,
                model=model,
                input=[{"role": "user", "content": input_text}],
                metadata={"provider": provider, "latency_ms": round(latency_ms, 1), **(metadata or {})},
            ) as gen:
                gen.update(
                    output=output_text,
                    usage_details={
                        "input": input_tokens,
                        "output": output_tokens,
                        "total": input_tokens + output_tokens,
                    },
                )
            return
        except Exception as exc:
            logger.debug("v3 log_generation failed: %s", exc)
            return

    if parent is None:
        return
    try:
        parent.generation(
            name=name,
            model=model,
            input=input_text,
            output=output_text,
            usage={"input": input_tokens, "output": output_tokens, "total": input_tokens + output_tokens},
            metadata={"provider": provider, "latency_ms": round(latency_ms, 1), **(metadata or {})},
        )
    except Exception as exc:
        logger.debug("legacy log_generation failed: %s", exc)


def log_span(
    parent: Any,
    *,
    name: str,
    input_data: Any = None,
    output_data: Any = None,
    metadata: Optional[dict[str, Any]] = None,
    as_type: str = "span",
) -> None:
    """Typed non-LLM step (retriever/guardrail/evaluator/span)."""
    if _sdk_mode == "v3":
        client = get_langfuse()
        if client is None:
            return
        try:
            with client.start_as_current_observation(
                as_type=as_type,
                name=name,
                input=input_data,
                metadata=metadata or {},
            ) as obs:
                if output_data is not None:
                    obs.update(output=output_data)
            return
        except Exception as exc:
            logger.debug("v3 log_span failed: %s", exc)
            return

    if parent is None:
        return
    try:
        parent.span(name=name, input=input_data, output=output_data, metadata=metadata or {})
    except Exception as exc:
        logger.debug("legacy log_span failed: %s", exc)


# Back-compat alias used by older call sites
@contextmanager
def langfuse_trace(name: str, metadata: dict[str, Any] | None = None):
    with observe_pipeline(name, metadata=metadata) as root:
        yield root


def log_standalone_generation(**kwargs) -> None:
    with observe_pipeline(
        kwargs.get("name", "llm.complete"),
        as_type="chain",
        feature="llm",
        metadata=kwargs.get("metadata"),
    ):
        log_generation(None, **{k: v for k, v in kwargs.items()})


def _safe_ctx(fn_name: str) -> str:
    try:
        from telemetry import context as ctx

        return getattr(ctx, fn_name)() or ""
    except Exception:
        return ""
