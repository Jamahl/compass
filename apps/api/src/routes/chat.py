"""Chat route — POST /runs/{run_id}/chat.

Lets the user chat against the research context produced by the runner.
Gated on research being complete (synth stage writes ``state.brief``; we fall
back to the raw ``research_payload`` if the brief isn't stored for some reason
— e.g. runs created before the `brief` column existed).

System prompt is user-editable via ``/prompts`` (see store/prompts.py); the
template must contain a ``{context}`` placeholder into which the brief (or
legacy payload) is injected.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from openai import AsyncOpenAI

from ..config import OPENAI_API_KEY
from ..models import ChatRequest, ChatResponse
from ..store import runs as runs_store
from ..store.prompts import get_prompts

router = APIRouter()

_client: AsyncOpenAI | None = None

# Caps — brief is markdown and tiny; legacy payload is big JSON and gets a
# harder clamp so we don't blow the context window.
_BRIEF_CAP = 8000
_LEGACY_PAYLOAD_CAP = 15000


def _get_client() -> AsyncOpenAI:
    """Lazily initialise and cache the module-level AsyncOpenAI client."""
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    return _client


def _build_system_content(brief: str | None, payload: str | None) -> str:
    """Inject the best available context into the user-editable chat prompt.

    Prefer the synthesized markdown brief (what the user actually wants Q&A
    against); fall back to truncated raw payload for pre-migration runs. If
    the template lacks a ``{context}`` placeholder, append the context after
    a blank line so edits that accidentally strip the placeholder still work.
    """
    if brief:
        context = brief[:_BRIEF_CAP]
    elif payload:
        context = payload[:_LEGACY_PAYLOAD_CAP]
    else:
        context = "(no research context available)"

    template = get_prompts().chat
    if "{context}" in template:
        return template.replace("{context}", context)
    return f"{template.rstrip()}\n\nRESEARCH BRIEF:\n{context}"


@router.post("/runs/{run_id}/chat", response_model=ChatResponse)
async def chat(run_id: str, body: ChatRequest) -> ChatResponse:
    """Chat against the research context for a given run."""
    state = runs_store.get_run(run_id)
    if state is None:
        raise HTTPException(status_code=404, detail="run not found")

    if state.research_payload is None and state.brief is None:
        raise HTTPException(status_code=400, detail="research not complete yet")

    system_content = _build_system_content(state.brief, state.research_payload)

    messages: list[dict[str, str]] = [{"role": "system", "content": system_content}]
    messages.extend({"role": m.role, "content": m.content} for m in body.history)
    messages.append({"role": "user", "content": body.message})

    client = _get_client()
    response = await client.chat.completions.create(
        model="gpt-5.4-nano",
        messages=messages,  # type: ignore[arg-type]
    )

    reply = response.choices[0].message.content or ""
    return ChatResponse(reply=reply)
