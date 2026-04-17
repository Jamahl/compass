"""Helpers for locating and reading user-supplied markdown context files.

The context directory lives at the repo root (`<repo>/Context/`). Users drop
`.md` files there; the frontend lists them via `GET /contexts`, and the runner
concatenates the selected ones into the research prompt as "Internal Context".

This module exposes two helpers:
  - `get_contexts_base()` — absolute path to the `Context/` directory.
  - `load_context_files(filenames)` — read & return `[(name, content), ...]`,
    with path-traversal defence.
"""

from __future__ import annotations

import os
from pathlib import Path


def get_contexts_base() -> Path:
    """Return the absolute path to the Context/ directory.

    Resolution order:
      1. ``CONTEXT_BASE`` env var (used by Docker: set to ``/app/Context``).
      2. Repo-root layout: walk ``__file__`` parents looking for a ``Context``
         sibling directory. This handles both host dev (``apps/api/src/store``
         depth) and any relative layout change without hard-coding an index.
      3. Fallback to ``./Context`` relative to CWD.
    """
    env = os.getenv("CONTEXT_BASE")
    if env:
        return Path(env)

    # Walk upward looking for a sibling Context directory.
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "Context"
        if candidate.is_dir():
            return candidate

    return Path.cwd() / "Context"


def load_context_files(filenames: list[str]) -> list[tuple[str, str]]:
    """Read each filename from the contexts dir, returning `[(name, content)]`.

    - Missing files are skipped silently.
    - Any filename that would resolve outside the contexts dir (path traversal,
      absolute paths, symlinks escaping the base) is rejected and skipped.
    - `name` is the title-cased file stem (matches the UI's display name).
    """
    base = get_contexts_base()
    if not base.exists() or not base.is_dir():
        return []

    base_resolved = base.resolve()
    results: list[tuple[str, str]] = []

    for raw in filenames:
        if not raw:
            continue
        candidate = (base / raw).resolve()
        # Reject anything that escapes the contexts dir.
        if candidate.parent != base_resolved:
            continue
        if not candidate.exists() or not candidate.is_file():
            continue
        try:
            content = candidate.read_text(encoding="utf-8")
        except OSError:
            continue
        name = candidate.stem.title()
        results.append((name, content))

    return results
