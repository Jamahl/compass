"""Pydantic models — single source of truth for API shapes.

Mirrored on the frontend via TS interfaces in apps/web/src/api/client.ts.
See project_overview.md section 4 for the canonical data model.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# ---- Enums (string literals) ----------------------------------------------
Template = Literal[
    "market_sizing",
    "competitor_scan",
    "customer_pain",
    "company_deep_dive",
    "product_teardown",
    "custom",
]

Depth = Literal["quick", "standard", "deep", "exhaustive"]

OutputType = Literal[
    # OpenAI-generated PDF reports
    "report_1pg",
    "report_5pg",
    "competitor_doc",
    # AutoContent media
    "podcast",
    "slides",
    "video",
    "infographic",
    # AutoContent PDF
    "briefing_doc",
    # AutoContent text/structured
    "faq",
    "study_guide",
    "timeline",
    "quiz",
    "datatable",
    "text",
    # ElevenLabs (independent pipeline)
    "elevenlabs_audio",
    "elevenlabs_video",
]

Status = Literal["pending", "running", "done", "error"]
RunStatus = Literal["pending", "research_done", "completed", "failed"]


# ---- Request / response shapes --------------------------------------------
class RunRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    urls: list[str] = Field(default_factory=list)
    template: Template
    depth: Depth
    outputs: list[OutputType] = Field(..., min_length=1)
    # Filenames (without path) from /Context directory whose contents should be
    # injected as background material into the research prompt. Empty list
    # means no extra context. See src/routes/contexts.py for discovery.
    context_files: list[str] = Field(default_factory=list)


class Stage(BaseModel):
    name: str
    status: Status
    error: str | None = None


class ArtifactMeta(BaseModel):
    id: str
    type: OutputType
    status: Status
    filename: str = ""
    error: str | None = None


class RunState(BaseModel):
    run_id: str
    status: RunStatus
    stages: list[Stage] = Field(default_factory=list)
    artifacts: list[ArtifactMeta] = Field(default_factory=list)
    research_payload: str | None = None
    created_at: str | None = None  # ISO 8601 UTC; set by the store on create
    request: RunRequest | None = None  # keep original for debug / writer access


# ---- Chat shapes -----------------------------------------------------------
class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] = Field(default_factory=list)


class ChatResponse(BaseModel):
    reply: str
