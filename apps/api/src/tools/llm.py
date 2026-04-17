"""OpenAI LLM wrappers for research synthesis and report writing.

Two async public functions:

- `synthesize(research_payload)`: distil a raw research payload from Parallel
  Task API into a compact markdown brief (executive summary + key findings +
  sources).
- `write_report(brief, report_type)`: expand a brief into a finished markdown
  report whose length/structure depends on `report_type`
  (`report_1pg`, `report_5pg`, `competitor_doc`).

Both call OpenAI `gpt-4o` via `openai.AsyncOpenAI`. The client is lazy-initialised
as a module-level singleton so import of this module does not force network/key
validation until the first call.
"""

from __future__ import annotations

import json
import time
from typing import Optional

from openai import AsyncOpenAI

from src.config import OPENAI_API_KEY
from src.store.events import append_event

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
# Prompts
# ---------------------------------------------------------------------------

_SYNTHESIZE_SYSTEM = """You are a senior research analyst. You will be given a raw research payload \
(JSON) produced by an external deep-research tool. Distil it into a TIGHT, \
decision-ready brief in Markdown with EXACTLY these sections and headings:

## Executive Summary
1-2 sentences. The single most important takeaway.

## Key Findings
3-5 bullets max. Each bullet ≤ 25 words. Concrete, specific (numbers, names, dates).

## Sources
Bulleted URLs/citations from the payload. De-duplicate. If none, write "No sources provided."

Rules:
- Output ONLY the Markdown brief. No preamble, no postscript, no code fences.
- Do not invent facts or sources not present in the payload.
- Keep the whole brief under 250 words."""


_REPORT_SYSTEMS: dict[str, str] = {
    "report_1pg": """You are a strategy writer producing a SHORT executive brief in Markdown. \
Target length: 150-250 words. Use EXACTLY these sections:

# <Concise Title>

## Overview
2-3 sentences framing the subject.

## Key Findings
3 bullets. Each bullet one short sentence.

## Recommendation
2-3 sentences with a clear, actionable recommendation.

Rules:
- Output Markdown only. No code fences, no preamble.
- Stay within 250 words. No filler.
- Use only information present in the provided brief. Do not fabricate.""",

    "report_5pg": """You are a strategy writer producing a CONCISE in-depth report in Markdown. \
Target length: 600-900 words. Use EXACTLY these sections:

# <Concise Title>

## Executive Summary
80-120 words with the headline conclusions.

## Context
2 short paragraphs (120-180 words) on background and why it matters now.

## Findings
3-5 bullets or short paragraphs (200-300 words total). Concrete and specific.

## Analysis
1-2 paragraphs (100-150 words) on what the findings mean.

## Risks
3 bullets covering material risks/unknowns.

## Recommendations
Numbered list, 3 items. Each 1 sentence.

Rules:
- Output Markdown only. No code fences, no preamble.
- Stay within 900 words.
- Use only information present in the provided brief. Do not fabricate sources \
or statistics.""",

    "competitor_doc": """You are a competitive intelligence analyst producing a CONCISE \
competitor landscape document in Markdown. Target: under 500 words total.

Required structure:

# Competitor Landscape: <Concise Title>

## Landscape Overview
1 short paragraph (60-100 words) framing the market and how players cluster.

## Competitor Comparison
A Markdown table with EXACTLY these columns in this order:

| Competitor | Positioning | Strengths | Weaknesses | Pricing |

Populate up to 5 rows max. Keep each cell to a short phrase. If a value is \
unknown, write "Unknown".

## Per-Competitor Notes
For each competitor in the table:

### <Competitor Name>
1-2 sentences of differentiation/go-to-market.

Rules:
- Output Markdown only. No code fences, no preamble.
- The comparison table is mandatory and must use the exact column headers given.
- Use only information present in the provided brief. Do not fabricate \
competitors, pricing, or quotes.""",
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def synthesize(research_payload: dict, *, run_id: str | None = None) -> str:
    """Distil a raw research payload into a compact markdown brief.

    Calls OpenAI `gpt-4o` with a fixed system prompt instructing the model to
    produce an Executive Summary, Key Findings, and Sources section. The user
    message is the JSON-dumped payload, truncated at ~12k chars.
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
            {"role": "system", "content": _SYNTHESIZE_SYSTEM},
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
    if report_type not in _REPORT_SYSTEMS:
        raise ValueError(
            f"Unknown report_type {report_type!r}. "
            f"Expected one of: {sorted(_REPORT_SYSTEMS)}."
        )

    client = _get_client()
    system_prompt = _REPORT_SYSTEMS[report_type]

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
