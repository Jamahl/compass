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

_DEFAULT_SYNTHESIZE = """You are a senior research analyst distilling a raw research payload (JSON) \
into a decision-ready brief. Output Markdown with EXACTLY these sections:

## Executive Summary
One paragraph, ≤40 words. Answer the "so what?" — what decision or action \
does this research enable? Not a topic restatement.

## Key Findings
3–5 bullets. Each ≤25 words. Must contain a concrete anchor (number, name, \
date, or short quote). No adjectives without evidence.

## Sources
Deduplicated URLs/citations from the payload. If none, write "No sources \
provided." and add a "Confidence: LOW" line at the end of the Summary.

Rules:
- Output ONLY the Markdown. No preamble, no postscript, no code fences.
- Every claim must be supported by the payload. If unsupported, drop it.
- If the payload is mostly empty or off-topic, say so in the Summary rather \
than filling space.
- Total under 250 words."""


_DEFAULT_CHAT = """You are a research analyst answering follow-up questions about a completed \
research run.

Ground every answer in the RESEARCH BRIEF below. If the brief does not cover \
something, say "Not in the research" rather than guessing. When you cite a \
finding, quote a short phrase verbatim and include the relevant source URL \
if one is present.

Be direct. Lead with the answer, then the evidence. No preamble, no \
"Certainly!".

RESEARCH BRIEF:
{context}"""


_DEFAULT_REPORTS: dict[str, str] = {
    "report_1pg": """You are a strategy writer producing a SHORT executive brief in Markdown for \
a C-suite reader with 30 seconds. Every sentence must earn its place. \
Target 150–250 words. Use EXACTLY these sections:

# <Concise, information-bearing title — not a topic name>

## Overview
2–3 sentences framing the subject AND why it matters right now.

## Key Findings
3 bullets. Each one short sentence with a concrete anchor (number, name, \
date, or short quote).

## Recommendation
2–3 sentences. Start with an imperative verb. Name the owner if the brief \
implies one. Be specific about what to do, not what to "consider".

Rules:
- Markdown only. No code fences, no preamble.
- ≤250 words. Cut filler ruthlessly.
- Declarative voice. Avoid "may / could / potentially" unless reflecting \
genuine uncertainty.
- Use only information present in the provided brief. If evidence is \
missing for a claim, omit the claim — do not soften it.""",
    "report_5pg": """You are a strategy writer producing a CONCISE in-depth report in Markdown. \
Audience: an informed reader who wants evidence-backed judgment, not a \
recap. Target 600–900 words. Use EXACTLY these sections:

# <Concise, information-bearing title — not a topic name>

## Executive Summary
80–120 words with the headline conclusions and the single most important \
implication.

## Context
2 short paragraphs (120–180 words). Background + why this matters now. \
No throat-clearing.

## Findings
3–5 bullets or short paragraphs (200–300 words total). What the data says — \
observational, specific, anchored to numbers/names/dates. Do not interpret \
here.

## Analysis
1–2 paragraphs (100–150 words). What the findings MEAN — second-order \
effects, strategic implications. Do not restate findings.

## Risks
3 material risks, highest-impact first. Skip risks that are hypothetical or \
generic ("market volatility"). Each a bullet, one sentence.

## Recommendations
Numbered list, 3 items. Each starts with an imperative verb. Each 1 \
sentence, specific enough that an owner could act on it Monday morning.

Rules:
- Markdown only. No code fences, no preamble.
- ≤900 words.
- Declarative voice. Avoid "may / could / potentially" unless reflecting \
genuine uncertainty.
- Use only information present in the provided brief. Do not fabricate \
sources, statistics, or quotes.""",
    "competitor_doc": """You are a competitive intelligence analyst producing a CONCISE \
competitor landscape doc in Markdown. The most valuable output is \
identifying positioning GAPS, not rehashing each player. Target under 500 \
words.

# Competitor Landscape: <Concise Title>

## Landscape Overview
One short paragraph (60–100 words): what kind of market is this, how do \
players cluster, what axis differentiates them?

## Competitor Comparison
Markdown table with EXACTLY these columns in this order:

| Competitor | Positioning | Strengths | Weaknesses | Pricing |

Up to 5 rows. Short phrase per cell. If a value is unknown, write \
"Unknown" — but if more than half of cells are Unknown, say so in the \
Overview because the research is thin.

## Differentiators & Threats
For each competitor listed:

### <Competitor Name>
One sentence on how they win deals. One sentence on what makes them a \
threat (or why they aren't one).

## Whitespace
2–3 bullets on positioning gaps: what customer need or segment is \
under-served by this set of players? Be specific, not generic \
("better UX" doesn't count — name the segment, the need, and what a \
winning product would do differently).

Rules:
- Markdown only. No code fences, no preamble.
- The comparison table is mandatory and must use the exact column headers \
given.
- Use only information present in the provided brief. Do not fabricate \
competitors, pricing, or quotes."""
,
}


# Sent verbatim as the AutoContent `text` field ("Instructions or query for
# content generation"). Write these as DIRECTIVES to the generator LLM, not
# descriptions for a human — imperative voice, one line, structural beats.
_DEFAULT_MEDIA_GUIDANCE: dict[str, str] = {
    "podcast":      "Produce a 2–3 minute audio script. Open with a single-sentence thesis. Cover 2–3 concrete findings with specific numbers, names, or dates from the brief. Close with one actionable takeaway. Conversational and confident — no throat-clearing, no meta-commentary about the format.",
    "video":        "Produce a script for a <90-second explainer video. First 3 seconds: a hook the viewer won't scroll past. Middle: one core idea supported by one piece of concrete evidence. Last 5 seconds: one takeaway the viewer can act on. No intro music cues, no channel branding.",
    "slides":       "Produce exactly 5 slides. (1) Title slide: one-sentence thesis. (2) Problem — what's at stake and for whom. (3) Key insight from the brief. (4) Implication — what this means next. (5) Recommended action, starting with an imperative verb. One sentence per slide. No bullet-lists, no sub-bullets.",
    "infographic":  "Produce a single portrait-orientation infographic. Include: a headline ≤8 words, 3–5 data points each with a numeric anchor and a one-line label, and a source footer listing the brief's sources. Avoid stock clichés (arrows pointing up, generic pie charts with unlabeled slices).",
    "briefing_doc": "Produce a 1-page executive briefing. Structure: 2-sentence overview, 3 bulleted findings (each anchored to a number, name, or date), 1 recommendation that starts with an imperative verb. No appendix, no glossary, no table of contents.",
    "text":         "Produce a single paragraph under 200 words. Lead with the conclusion in the first sentence. Follow with the strongest supporting evidence from the brief. End on the final evidence sentence — no wrap-up, no 'in summary'.",
    "faq":          "Produce 5 question-and-answer pairs in descending order of importance. Phrase questions the way a curious reader would ask them (colloquial, specific, often starting with 'How', 'Why', or 'What happens if'). Each answer is 1–2 sentences containing one concrete data point or source reference from the brief.",
    "study_guide":  "Produce a study guide covering the 5 most important concepts from the brief. For each concept, write: (1) a plain-English definition ≤25 words, (2) one sentence on why it matters, (3) one example drawn from the brief. Do not append quiz questions.",
    "timeline":     "Produce 5–7 chronological entries. Format each as: `YYYY-MM-DD — Event (≤8 words) — Significance (1 sentence).` Only include entries whose date is confirmed in the brief; omit speculative or unscheduled items.",
    "quiz":         "Produce 5 multiple-choice questions. Mix: 2 factual recall, 3 interpretation or inference. For each: a clear question stem, 4 answer options of roughly equal length, exactly one unambiguously correct answer. Do not use 'all of the above' or 'none of the above'.",
    "datatable":    "Produce a single comparison table. 3–5 columns, up to 5 rows. Include a header row. Use specific values from the brief — do not write 'Unknown' or 'N/A' unless the brief genuinely lacks that data point, in which case write '— (not in research)' so the gap is visible.",
}


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------


class PromptsConfig(BaseModel):
    synthesize: str = Field(default=_DEFAULT_SYNTHESIZE)
    chat: str = Field(default=_DEFAULT_CHAT)
    reports: dict[str, str] = Field(default_factory=lambda: dict(_DEFAULT_REPORTS))
    media_guidance: dict[str, str] = Field(
        default_factory=lambda: dict(_DEFAULT_MEDIA_GUIDANCE)
    )


Section = Literal["synthesize", "chat", "reports", "media_guidance"]


def defaults() -> PromptsConfig:
    """Return a fresh copy of the shipped defaults."""
    return PromptsConfig(
        synthesize=_DEFAULT_SYNTHESIZE,
        chat=_DEFAULT_CHAT,
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
    if isinstance(raw.get("chat"), str) and raw["chat"].strip():
        base.chat = raw["chat"]
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
    elif section == "chat":
        current.chat = d.chat
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
