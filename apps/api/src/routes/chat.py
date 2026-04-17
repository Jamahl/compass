"""Chat route — POST /runs/{run_id}/chat.

Lets the user chat against the research context produced by the runner.
Gated on research being complete (synth stage writes ``state.brief``; we fall
back to the raw ``research_payload`` if the brief isn't stored for some reason
— e.g. runs created before the `brief` column existed).

System prompt is user-editable via ``/prompts`` (see store/prompts.py); the
template must contain a ``{context}`` placeholder into which the brief (or
legacy payload) plus any available artifact context is injected.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from openai import AsyncOpenAI

from ..config import OPENAI_API_KEY
from ..models import ChatRequest, ChatResponse
from ..store import runs as runs_store
from ..store.artifacts_dir import artifacts_base
from ..store.prompts import get_prompts

router = APIRouter()

_client: AsyncOpenAI | None = None

# Artifact types that have an accompanying markdown sidecar we can inline:
#   - AutoContent text outputs (_OUTPUT_MAP entries with empty url_field) —
#     saved directly as {artifact_id}.md by tools/autocontent.py.
#   - Report types — source markdown persisted as {artifact_id}.md sidecar
#     alongside the rendered PDF by orchestrator/writer.py (the PDF itself
#     is not text-extractable without extra deps).
_TEXT_ARTIFACT_TYPES: frozenset[str] = frozenset(
    {
        # AutoContent text/markdown outputs
        "text", "faq", "study_guide", "timeline", "quiz", "datatable",
        # Report PDFs — sidecar .md written pre-render
        "report_1pg", "report_5pg", "competitor_doc",
    }
)

# Caps — brief is markdown and tiny; legacy payload is big JSON and gets a
# harder clamp so we don't blow the context window.
_BRIEF_CAP = 8000
_LEGACY_PAYLOAD_CAP = 15000
_PER_ARTIFACT_CHAR_CAP = 4000
_TOTAL_ARTIFACT_CHAR_CAP = 24000


def _get_client() -> AsyncOpenAI:
    """Lazily initialise and cache the module-level AsyncOpenAI client."""
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    return _client


def _load_artifact_context(run_id: str, artifacts: list) -> str:
    """Build a summary + inlined-content block for a run's artifacts.

    Lists every artifact by type + status, then inlines the body of
    text-based outputs (AutoContent text + report .md sidecars) so the chat
    model can answer against generated content, not just the research brief.
    """
    if not artifacts:
        return ""

    lines: list[str] = ["ARTIFACTS PRODUCED:"]
    for a in artifacts:
        lines.append(f"- {a.type} [{a.status}] {a.filename or ''}".rstrip())

    bodies: list[str] = []
    total = 0
    run_dir = artifacts_base() / run_id
    for a in artifacts:
        if a.status != "done" or a.type not in _TEXT_ARTIFACT_TYPES:
            continue
        # Try the recorded filename first (AutoContent text outputs write
        # {id}.md, this matches). Fall back to the {id}.md sidecar path that
        # writer.py persists for report PDFs.
        path = None
        if a.filename:
            candidate = run_dir / a.filename
            if candidate.exists() and candidate.suffix.lower() in {".md", ".txt"}:
                path = candidate
        if path is None:
            sidecar = run_dir / f"{a.id}.md"
            if sidecar.exists():
                path = sidecar
        if path is None:
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not content.strip():
            continue
        snippet = content[:_PER_ARTIFACT_CHAR_CAP]
        room = _TOTAL_ARTIFACT_CHAR_CAP - total
        if room <= 0:
            break
        snippet = snippet[:room]
        label = a.filename or path.name
        bodies.append(f"--- {a.type} ({label}) ---\n{snippet}")
        total += len(snippet)

    block = "\n".join(lines)
    if bodies:
        block += "\n\nARTIFACT CONTENT:\n\n" + "\n\n".join(bodies)
    return block


def _build_system_content(
    brief: str | None,
    payload: str | None,
    artifact_block: str,
) -> str:
    """Inject the best available context into the user-editable chat prompt.

    Prefer the synthesized markdown brief (what the user actually wants Q&A
    against); fall back to truncated raw payload for pre-migration runs. The
    artifact block (summary + inlined sidecar content) is appended after the
    brief so the assistant can reference generated outputs too. If the
    template lacks a ``{context}`` placeholder, append the context after a
    blank line so edits that accidentally strip the placeholder still work.
    """
    if brief:
        context = brief[:_BRIEF_CAP]
    elif payload:
        context = payload[:_LEGACY_PAYLOAD_CAP]
    else:
        context = "(no research context available)"

    if artifact_block:
        context = f"{context}\n\n{artifact_block}"

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

    artifact_block = _load_artifact_context(run_id, state.artifacts)
    system_content = _build_system_content(
        state.brief, state.research_payload, artifact_block
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
