from __future__ import annotations


def resolve(local: dict, remote: dict, strategy: str) -> dict:
    """Return the winning record dict according to *strategy*.

    last_write_wins — newer updated_at wins; remote wins on tie or missing field.
    source_wins     — remote always wins.
    manual          — local returned unchanged; caller must call mark_conflict.
    """
    if strategy == "source_wins":
        return dict(remote)

    if strategy == "manual":
        return dict(local)

    if strategy == "last_write_wins":
        local_ts = local.get("updated_at") or ""
        remote_ts = remote.get("updated_at") or ""
        return dict(local) if local_ts > remote_ts else dict(remote)

    raise ValueError(f"Unknown conflict resolution strategy: {strategy!r}")
