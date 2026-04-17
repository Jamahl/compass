"""Filesystem helper for artifact storage.

Default location is ``<repo>/apps/api/data/artifacts`` so artifacts persist
alongside the SQLite DB under ``apps/api/data/``. Override with the
``ARTIFACTS_BASE`` env var when running in Docker (we set it to
``/app/data/artifacts`` inside the container so artifacts + db share the
same named volume). Falls back to ``/tmp/betterlabs-artifacts`` if neither
the env var is set nor the repo layout is detectable.
"""

from __future__ import annotations

import os
from pathlib import Path


def _resolve_default_base() -> Path:
    """Pick the best default base directory for artifact storage."""
    env = os.getenv("ARTIFACTS_BASE")
    if env:
        return Path(env)
    # This file lives at apps/api/src/store/artifacts_dir.py.
    # parents[0]=store, [1]=src, [2]=api → put artifacts under apps/api/data/.
    try:
        return Path(__file__).resolve().parents[2] / "data" / "artifacts"
    except (IndexError, OSError):
        return Path("/tmp/betterlabs-artifacts")


_BASE: Path = _resolve_default_base()


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
