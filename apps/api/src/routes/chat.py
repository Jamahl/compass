"""Chat route — POST /runs/{run_id}/chat.

Lets the user chat against the research context produced by the runner.
Gated on `state.research_payload` being populated (set at end of research stage).
Uses OpenAI via the async client (model pinned inline below). See
project_overview.md sections 4, 5 and tasks.md T32, T33.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from openai import AsyncOpenAI

from ..config import OPENAI_API_KEY
from ..models import ChatRequest, ChatResponse
from ..store import runs as runs_store
from ..store.artifacts_dir import artifacts_base

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
_PER_ARTIFACT_CHAR_CAP = 4000
_TOTAL_ARTIFACT_CHAR_CAP = 24000
_BRIEF_CHAR_CAP = 8000


def _get_client() -> AsyncOpenAI:
    """Lazily initialise and cache the module-level AsyncOpenAI client."""
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    return _client


def _load_artifact_context(run_id: str, artifacts: list) -> str:
    """Build a summary block of AutoContent artifacts for the system prompt.

    Lists every artifact by type + status and inlines the body of text-based
    AutoContent outputs (saved as .md) so the chat model can answer against
    generated content, not just the Parallel research payload.
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


def _load_brief(run_id: str) -> str:
    """Read the synthesized brief sidecar if it exists, else empty string."""
    path = artifacts_base() / run_id / "brief.md"
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


@router.post("/runs/{run_id}/chat", response_model=ChatResponse)
async def chat(run_id: str, body: ChatRequest) -> ChatResponse:
    """Chat against the research context for a given run."""
    state = runs_store.get_run(run_id)
    if state is None:
        raise HTTPException(status_code=404, detail="run not found")

    if state.research_payload is None:
        raise HTTPException(status_code=400, detail="research not complete yet")

    artifact_block = _load_artifact_context(run_id, state.artifacts)
    brief = _load_brief(run_id)

    system_content = (
        "You are a research assistant. Use the following research context and "
        "generated artifacts to answer the user's questions. Cite specifics "
        "when possible. Format responses in Markdown.\n\n"
        "RESEARCH CONTEXT (from Parallel):\n\n"
        f"{state.research_payload[:15000]}"
    )
    if brief:
        system_content += (
            "\n\nSYNTHESIZED BRIEF (distilled summary used to generate all "
            "outputs — the highest-signal source):\n\n"
            f"{brief[:_BRIEF_CHAR_CAP]}"
        )
    if artifact_block:
        system_content += "\n\n" + artifact_block

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
