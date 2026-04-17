"""Filesystem helper for artifact storage under /tmp/betterlabs-artifacts/."""

from __future__ import annotations

from pathlib import Path

_BASE = Path("/tmp/betterlabs-artifacts")


def artifacts_base() -> Path:
    _BASE.mkdir(parents=True, exist_ok=True)
    return _BASE


def get_artifact_path(run_id: str, artifact_id: str, ext: str) -> Path:
    """Return full path under base/{run_id}/{artifact_id}.{ext} (dir created).

    Strips any leading dot from ext.
    """
    ext = ext.lstrip(".")
    run_dir = artifacts_base() / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir / f"{artifact_id}.{ext}"
