"""Routes for viewing and editing the user-editable system prompts.

`GET /api/prompts` returns `{config, defaults}` so the UI can show per-field
"reset to default" affordances. `PUT /api/prompts` replaces the whole config.
`POST /api/prompts/reset` restores one field, one section, or everything.
"""

from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..store import prompts as prompts_store
from ..store.prompts import PromptsConfig

router = APIRouter(prefix="/prompts")


class PromptsEnvelope(BaseModel):
    config: PromptsConfig
    defaults: PromptsConfig


class ResetRequest(BaseModel):
    section: Optional[
        Literal["synthesize", "chat", "reports", "media_guidance"]
    ] = None
    key: Optional[str] = None


def _validate(cfg: PromptsConfig) -> None:
    if not cfg.synthesize.strip():
        raise HTTPException(422, "synthesize prompt cannot be empty")
    if not cfg.chat.strip():
        raise HTTPException(422, "chat prompt cannot be empty")
    for k, v in cfg.reports.items():
        if not isinstance(v, str) or not v.strip():
            raise HTTPException(422, f"reports.{k} cannot be empty")


@router.get("")
def get_prompts() -> PromptsEnvelope:
    return PromptsEnvelope(
        config=prompts_store.get_prompts(),
        defaults=prompts_store.defaults(),
    )


@router.put("")
def put_prompts(cfg: PromptsConfig) -> PromptsEnvelope:
    _validate(cfg)
    saved = prompts_store.save_prompts(cfg)
    return PromptsEnvelope(config=saved, defaults=prompts_store.defaults())


@router.post("/reset")
def reset_prompts(req: ResetRequest) -> PromptsEnvelope:
    saved = prompts_store.reset(section=req.section, key=req.key)
    return PromptsEnvelope(config=saved, defaults=prompts_store.defaults())
