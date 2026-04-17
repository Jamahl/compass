"""Prompts store — user-editable system prompts for LLM + AutoContent.

Holds the canonical DEFAULTS for every prompt the pipeline uses and reads/writes
an override file (`Config/prompts.json`) so operators can tune behaviour from
the Settings UI without redeploying.

Resolution order for the config path:
  1. ``PROMPTS_PATH`` env var (used by Docker).
  2. First ``Config`` sibling directory found walking ``__file__`` parents.
  3. Stable fallback anchored to this file: ``apps/api/Config/prompts.json``
     (does NOT depend on CWD, so operators get the same file regardless of
     where they launched uvicorn from).

Callers use ``get_prompts()`` — it returns the merged (defaults ∪ overrides)
config, caches by file mtime, and silently falls back to defaults if the file
is missing or corrupt. ``save_prompts`` writes atomically (tmp + rename) so a
crash mid-write cannot leave a partial file.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from threading import Lock
from typing import Literal

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Defaults — copied verbatim from the pre-Settings hard-coded strings. Editing
# these changes the fallback the Reset buttons restore to.
# ---------------------------------------------------------------------------

_DEFAULT_SYNTHESIZE = """You are a senior research analyst. You will be given a raw research payload \
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


_DEFAULT_REPORTS: dict[str, str] = {
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


_DEFAULT_MEDIA_GUIDANCE: dict[str, str] = {
    "podcast":      "Keep podcast SHORT: 2-3 minutes, 1-2 speakers, single topic.",
    "video":        "Keep video SHORT: under 90 seconds, minimal scenes.",
    "slides":       "Keep deck SHORT: 5 slides max, one idea per slide.",
    "infographic":  "Single infographic, 3-5 key data points only.",
    "briefing_doc": "1-2 page briefing only. Tight bullets.",
    "text":         "Keep response under 200 words.",
    "faq":          "5 Q&A pairs max. Each answer 1-2 sentences.",
    "study_guide":  "Short study guide, 5 key concepts max.",
    "timeline":     "5-7 timeline entries max.",
    "quiz":         "5 questions max.",
    "datatable":    "Up to 5 rows, 3-5 columns.",
}


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------


class PromptsConfig(BaseModel):
    synthesize: str = Field(default=_DEFAULT_SYNTHESIZE)
    reports: dict[str, str] = Field(default_factory=lambda: dict(_DEFAULT_REPORTS))
    media_guidance: dict[str, str] = Field(
        default_factory=lambda: dict(_DEFAULT_MEDIA_GUIDANCE)
    )


Section = Literal["synthesize", "reports", "media_guidance"]


def defaults() -> PromptsConfig:
    """Return a fresh copy of the shipped defaults."""
    return PromptsConfig(
        synthesize=_DEFAULT_SYNTHESIZE,
        reports=dict(_DEFAULT_REPORTS),
        media_guidance=dict(_DEFAULT_MEDIA_GUIDANCE),
    )


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------


def get_prompts_path() -> Path:
    env = os.getenv("PROMPTS_PATH")
    if env:
        return Path(env)
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "Config"
        if candidate.is_dir():
            return candidate / "prompts.json"
    # Stable fallback anchored to this file, not CWD: walk up from
    # apps/api/src/store/prompts.py → apps/api, then /Config/prompts.json.
    # parents[0]=store, [1]=src, [2]=apps/api.
    return Path(__file__).resolve().parents[2] / "Config" / "prompts.json"


# ---------------------------------------------------------------------------
# Read / write (mtime-cached)
# ---------------------------------------------------------------------------

_cache_lock = Lock()
_cached: tuple[float, PromptsConfig] | None = None  # (mtime, config)


def _merge_over_defaults(raw: dict) -> PromptsConfig:
    """Merge a partial JSON dict over defaults so missing keys remain usable."""
    base = defaults()
    if isinstance(raw.get("synthesize"), str) and raw["synthesize"].strip():
        base.synthesize = raw["synthesize"]
    if isinstance(raw.get("reports"), dict):
        for k, v in raw["reports"].items():
            if isinstance(v, str) and v.strip():
                base.reports[k] = v
    if isinstance(raw.get("media_guidance"), dict):
        for k, v in raw["media_guidance"].items():
            if isinstance(v, str):
                base.media_guidance[k] = v
    return base


def get_prompts() -> PromptsConfig:
    """Return merged config. Cheap; cached by file mtime so hot-reload is free."""
    global _cached
    path = get_prompts_path()
    try:
        mtime = path.stat().st_mtime
    except FileNotFoundError:
        return defaults()

    with _cache_lock:
        if _cached is not None and _cached[0] == mtime:
            return _cached[1]
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return defaults()
        cfg = _merge_over_defaults(raw)
        _cached = (mtime, cfg)
        return cfg


def save_prompts(cfg: PromptsConfig) -> PromptsConfig:
    """Atomically persist the full config; invalidate the mtime cache."""
    global _cached
    path = get_prompts_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(cfg.model_dump_json(indent=2), encoding="utf-8")
    os.replace(tmp, path)
    with _cache_lock:
        _cached = None
    return get_prompts()


def reset(section: Section | None = None, key: str | None = None) -> PromptsConfig:
    """Reset a section/key (or everything) to defaults and persist.

    Works on a deep copy so concurrent readers holding the cached instance
    never observe a half-modified state.
    """
    if section is None:
        return save_prompts(defaults())

    current = get_prompts().model_copy(deep=True)
    d = defaults()
    if section == "synthesize":
        current.synthesize = d.synthesize
    elif section == "reports":
        if key is None:
            current.reports = dict(d.reports)
        elif key in d.reports:
            current.reports[key] = d.reports[key]
    elif section == "media_guidance":
        if key is None:
            current.media_guidance = dict(d.media_guidance)
        elif key in d.media_guidance:
            current.media_guidance[key] = d.media_guidance[key]
    return save_prompts(current)
