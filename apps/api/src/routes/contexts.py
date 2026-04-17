"""Routes for discovering user-supplied markdown context files.

Exposes `GET /contexts`, which scans `<repo>/Context/` for `.md` files and
returns lightweight metadata (name, filename, size, preview) for each. The
frontend renders these as tickable cards in the Research Studio UI; the chosen
filenames are round-tripped back to the backend via `RunRequest.context_files`.
"""

from __future__ import annotations

import re
from typing import TypedDict

from fastapi import APIRouter

from ..store.contexts_dir import get_contexts_base

router = APIRouter()


class ContextItem(TypedDict):
    name: str
    filename: str
    size: int
    preview: str


_WHITESPACE_RE = re.compile(r"\s+")
_README_STEMS = {"readme"}  # case-insensitive match on stem


def _make_preview(text: str) -> str:
    """Collapse all whitespace and trim to 200 chars for a card preview."""
    return _WHITESPACE_RE.sub(" ", text).strip()[:200]


@router.get("/contexts")
def list_contexts() -> list[ContextItem]:
    """Return a sorted list of available markdown context files.

    Skips `README.md` (case-insensitive). Returns an empty list if the
    Context directory does not exist.
    """
    base = get_contexts_base()
    if not base.exists() or not base.is_dir():
        return []

    items: list[ContextItem] = []
    for path in sorted(base.glob("*.md"), key=lambda p: p.name.lower()):
        if path.stem.lower() in _README_STEMS:
            continue
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
            size = path.stat().st_size
        except OSError:
            continue
        items.append(
            ContextItem(
                name=path.stem.title(),
                filename=path.name,
                size=size,
                preview=_make_preview(text),
            )
        )
    return items
