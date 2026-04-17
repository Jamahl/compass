"""OpenAI LLM wrappers for research synthesis and report writing.

Two async public functions:

- `synthesize(research_payload)`: distil a raw research payload from Parallel
  Task API into a compact markdown brief (executive summary + key findings +
  sources).
- `write_report(brief, report_type)`: expand a brief into a finished markdown
  report whose length/structure depends on `report_type`
  (`report_1pg`, `report_5pg`, `competitor_doc`).

Both call OpenAI via `openai.AsyncOpenAI` using the model named in `_MODEL`.
The client is lazy-initialised as a module-level singleton so import of this
module does not force network/key validation until the first call.
"""

from __future__ import annotations

import json
import time
from typing import Optional

from openai import AsyncOpenAI

from src.config import OPENAI_API_KEY
from src.store.events import append_event
from src.store.prompts import get_prompts

# ---------------------------------------------------------------------------
# Client singleton (lazy)
# ---------------------------------------------------------------------------

_client: Optional[AsyncOpenAI] = None

# Cap the JSON-dumped research payload at ~12k chars to keep prompts sane.
_MAX_PAYLOAD_CHARS = 12_000

_MODEL = "gpt-5.4-nano"


def _get_client() -> AsyncOpenAI:
    """Return the module-level AsyncOpenAI singleton, constructing it on demand."""
    global _client
    if _client is None:
        if not OPENAI_API_KEY:
            raise ValueError(
                "OPENAI_API_KEY is not set; cannot construct OpenAI client."
            )
        _client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    return _client


def _truncate(text: str, limit: int = _MAX_PAYLOAD_CHARS) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "\n\n… [truncated]"


# ---------------------------------------------------------------------------
# Prompts live in src/store/prompts.py (user-editable via /api/prompts).
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def synthesize(research_payload: dict, *, run_id: str | None = None) -> str:
    """Distil a raw research payload into a compact markdown brief.

    Calls OpenAI (model from `_MODEL`) with a fixed system prompt instructing
    the model to produce an Executive Summary, Key Findings, and Sources
    section. The user message is the JSON-dumped payload, truncated at ~12k
    chars.
    """
    client = _get_client()

    payload_json = json.dumps(research_payload, indent=2, default=str)
    payload_json = _truncate(payload_json)

    if run_id:
        append_event(
            run_id, "llm", "tool.call",
            f"OpenAI {_MODEL} synthesize ({len(payload_json)} chars in)",
            data={"model": _MODEL, "input_chars": len(payload_json)},
        )
    started = time.monotonic()
    response = await client.chat.completions.create(
        model=_MODEL,
        messages=[
            {"role": "system", "content": get_prompts().synthesize},
            {"role": "user", "content": payload_json},
        ],
    )

    content = response.choices[0].message.content or ""
    out = content.strip()
    if run_id:
        usage = getattr(response, "usage", None)
        usage_dict = (
            {
                "prompt_tokens": getattr(usage, "prompt_tokens", None),
                "completion_tokens": getattr(usage, "completion_tokens", None),
                "total_tokens": getattr(usage, "total_tokens", None),
            }
            if usage is not None
            else None
        )
        append_event(
            run_id, "llm", "tool.result",
            f"OpenAI synthesize done — {len(out)} chars in "
            f"{time.monotonic() - started:.1f}s",
            data={
                "model": _MODEL,
                "output_chars": len(out),
                "elapsed_s": round(time.monotonic() - started, 2),
                "usage": usage_dict,
            },
        )
    return out


async def write_report(
    brief: str, report_type: str, *, run_id: str | None = None
) -> str:
    """Expand a brief into a finished markdown report of the given type.

    `report_type` must be one of: `report_1pg`, `report_5pg`, `competitor_doc`.
    Returns raw markdown. Raises `ValueError` for unknown report types.
    """
    reports = get_prompts().reports
    if report_type not in reports:
        raise ValueError(
            f"Unknown report_type {report_type!r}. "
            f"Expected one of: {sorted(reports)}."
        )

    client = _get_client()
    system_prompt = reports[report_type]

    if run_id:
        append_event(
            run_id, "llm", "tool.call",
            f"OpenAI {_MODEL} write_report({report_type})",
            data={
                "model": _MODEL,
                "report_type": report_type,
                "brief_chars": len(brief),
            },
        )
    started = time.monotonic()
    response = await client.chat.completions.create(
        model=_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": brief},
        ],
    )

    content = response.choices[0].message.content or ""
    out = content.strip()
    if run_id:
        usage = getattr(response, "usage", None)
        usage_dict = (
            {
                "prompt_tokens": getattr(usage, "prompt_tokens", None),
                "completion_tokens": getattr(usage, "completion_tokens", None),
                "total_tokens": getattr(usage, "total_tokens", None),
            }
            if usage is not None
            else None
        )
        append_event(
            run_id, "llm", "tool.result",
            f"OpenAI write_report({report_type}) done — {len(out)} chars in "
            f"{time.monotonic() - started:.1f}s",
            data={
                "model": _MODEL,
                "report_type": report_type,
                "output_chars": len(out),
                "elapsed_s": round(time.monotonic() - started, 2),
                "usage": usage_dict,
            },
        )
    return out
