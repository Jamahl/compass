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
from typing import Optional

from openai import AsyncOpenAI

from src.config import OPENAI_API_KEY

# ---------------------------------------------------------------------------
# Client singleton (lazy)
# ---------------------------------------------------------------------------

_client: Optional[AsyncOpenAI] = None

# Cap the JSON-dumped research payload at ~12k chars to keep prompts sane.
_MAX_PAYLOAD_CHARS = 12_000

_MODEL = "gpt-4o"


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
(JSON) produced by an external deep-research tool. Distil it into a compact, \
decision-ready brief in Markdown with EXACTLY these sections and headings:

## Executive Summary
2-3 tight sentences capturing the single most important takeaway.

## Key Findings
A bulleted list (5-10 bullets). Each bullet should be a concrete finding, not a \
restatement of the prompt. Prefer specificity (numbers, names, dates) over generalities.

## Sources
A bulleted list of URLs / citations extracted from the payload. If the payload \
contains URLs, list them verbatim. If it contains citations without URLs, list \
those. De-duplicate. If no sources are present, write "No sources provided in \
research payload."

Rules:
- Output ONLY the Markdown brief. No preamble, no postscript, no code fences.
- Do not invent facts or sources not present in the payload.
- Keep the whole brief under ~500 words."""


_REPORT_SYSTEMS: dict[str, str] = {
    "report_1pg": """You are a strategy writer producing a ONE-PAGE executive report in \
Markdown. Target length: 400-600 words. Use EXACTLY these sections:

# <Concise Title>

## Overview
A short paragraph (3-5 sentences) framing the subject and why it matters.

## Key Findings
3-5 bullets. Each bullet one sentence, punchy, specific.

## Recommendation
A short paragraph (3-5 sentences) with a clear, actionable recommendation.

Rules:
- Output Markdown only. No code fences, no preamble.
- Stay within the target word count. One page, no filler.
- Use only information present in the provided brief. Do not fabricate.""",

    "report_5pg": """You are a strategy writer producing a FIVE-PAGE in-depth report in \
Markdown. Target length: 2000-3000 words. Use EXACTLY these sections with \
Markdown headings:

# <Concise Title>

## Executive Summary
Tight opening (150-250 words) with the headline conclusions.

## Context
Background, scope, why this matters now. (300-450 words.)

## Findings
Use ### subheadings to group related findings. Cover the material thoroughly. \
(700-1000 words total across subheadings.)

## Analysis
Synthesise the findings: what do they mean, how do the pieces interact, what's \
the signal vs noise. (400-600 words.)

## Risks
Bulleted or short-paragraph list of material risks, caveats, and unknowns. \
(150-300 words.)

## Recommendations
Numbered list of concrete, prioritised recommendations. Each item: 1-2 sentences. \
(150-300 words.)

Rules:
- Output Markdown only. No code fences, no preamble.
- Hit the target length — this is a substantive report, not a summary.
- Use only information present in the provided brief. Do not fabricate sources \
or statistics. If the brief is thin, say so explicitly in Context.""",

    "competitor_doc": """You are a competitive intelligence analyst producing a \
table-heavy competitor landscape document in Markdown.

Required structure:

# Competitor Landscape: <Concise Title>

## Landscape Overview
2-4 paragraphs framing the market, the axes of competition, and how players \
cluster.

## Competitor Comparison
A Markdown table with EXACTLY these columns in this order:

| Competitor | Positioning | Strengths | Weaknesses | Pricing |

Populate one row per competitor identified in the brief. Keep cells concise \
(one short phrase or sentence per cell). If a value is unknown, write "Unknown".

## Per-Competitor Notes
For each competitor in the table, a short subsection:

### <Competitor Name>
2-4 sentences of additional context, differentiation, and go-to-market notes.

Rules:
- Output Markdown only. No code fences, no preamble.
- The comparison table is mandatory and must use the exact column headers given.
- Use only information present in the provided brief. Do not fabricate \
competitors, pricing, or quotes.""",
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def synthesize(research_payload: dict) -> str:
    """Distil a raw research payload into a compact markdown brief.

    Calls OpenAI `gpt-4o` with a fixed system prompt instructing the model to
    produce an Executive Summary, Key Findings, and Sources section. The user
    message is the JSON-dumped payload, truncated at ~12k chars.
    """
    client = _get_client()

    payload_json = json.dumps(research_payload, indent=2, default=str)
    payload_json = _truncate(payload_json)

    response = await client.chat.completions.create(
        model=_MODEL,
        messages=[
            {"role": "system", "content": _SYNTHESIZE_SYSTEM},
            {"role": "user", "content": payload_json},
        ],
    )

    content = response.choices[0].message.content or ""
    return content.strip()


async def write_report(brief: str, report_type: str) -> str:
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

    response = await client.chat.completions.create(
        model=_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": brief},
        ],
    )

    content = response.choices[0].message.content or ""
    return content.strip()
