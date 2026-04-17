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

from pathlib import Path


def get_contexts_base() -> Path:
    """Return the absolute path to `<repo>/Context/`.

    The directory is NOT created if missing — callers must handle absence.
    Computed relative to this file's location.
    """
    # __file__ = <repo>/apps/api/src/store/contexts_dir.py
    # parents[0] = store, [1] = src, [2] = api, [3] = apps, [4] = <repo>
    return Path(__file__).resolve().parents[4] / "Context"


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
