"""Chat route — POST /runs/{run_id}/chat.

Lets the user chat against the research context produced by the runner.
Gated on `state.research_payload` being populated (set at end of research stage).
Uses OpenAI `gpt-4o` via the async client. See project_overview.md sections 4, 5
and tasks.md T32, T33.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from openai import AsyncOpenAI

from ..config import OPENAI_API_KEY
from ..models import ChatRequest, ChatResponse
from ..store import runs as runs_store

router = APIRouter()

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    """Lazily initialise and cache the module-level AsyncOpenAI client."""
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    return _client


@router.post("/runs/{run_id}/chat", response_model=ChatResponse)
async def chat(run_id: str, body: ChatRequest) -> ChatResponse:
    """Chat against the research context for a given run."""
    state = runs_store.get_run(run_id)
    if state is None:
        raise HTTPException(status_code=404, detail="run not found")

    if state.research_payload is None:
        raise HTTPException(status_code=400, detail="research not complete yet")

    system_content = (
        "You are a research assistant. Use the following research context to "
        "answer the user's questions. Cite specifics when possible.\n\n"
        "RESEARCH CONTEXT:\n\n"
        f"{state.research_payload[:15000]}"
    )

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
