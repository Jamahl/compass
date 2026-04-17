"""AutoContent API client.

Verified against live API 2026-04-17.
Docs: https://docs.autocontentapi.com

Endpoints:
- POST /content/Create   body {resources, outputType, text} -> {request_id, status}
- GET  /content/Status/{id} -> {status: 0..100, *_url fields when 100}
  status: 0=queued, 10..80=in-progress, 100=complete, <0=error

Supported outputTypes handled here:
  audio, video, slide_deck, infographic, briefing_doc,
  text, faq, study_guide, timeline, quiz, datatable
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path

import httpx

from src.config import AUTOCONTENT_API_KEY
from src.store.artifacts_dir import get_artifact_path
from src.store.events import append_event

_BASE = "https://api.autocontentapi.com"
_CREATE_URL = f"{_BASE}/content/Create"
_STATUS_URL_TMPL = f"{_BASE}/content/Status/{{request_id}}"

_POLL_INTERVAL_SECONDS = 5
_OVERALL_TIMEOUT_SECONDS = 1800

# Cap brief length sent to AutoContent. Shorter input → faster + smaller output.
_BRIEF_CHAR_CAP = 2000

# Per-output-type concise guidance appended to the AutoContent `text` field.
# AutoContent treats `text` as the user instruction for the generator.
_OUTPUT_GUIDANCE: dict[str, str] = {
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

# Case-insensitive tokens that indicate a Pro/subscription gating failure.
_PRO_ERROR_TOKENS: tuple[str, ...] = (
    "pro",
    "subscription",
    "upgrade",
    "not available on",
    "plan",
)


class AutoContentProRequiredError(RuntimeError):
    """Raised when AutoContent rejects a job because it requires a Pro plan."""


def _is_pro_error(message: str) -> bool:
    lowered = message.lower()
    return any(token in lowered for token in _PRO_ERROR_TOKENS)

# Map our OutputType -> AutoContent outputType + file ext + completion-url field.
# For text outputs (empty url_field) we save response_text / document_content
# as a markdown file.
_OUTPUT_MAP: dict[str, dict[str, str]] = {
    "podcast":      {"ac": "audio",        "ext": "mp3", "url_field": "audio_url"},
    "video":        {"ac": "video",        "ext": "mp4", "url_field": "video_url"},
    "slides":       {"ac": "slide_deck",   "ext": "mp4", "url_field": "video_url"},
    "infographic":  {"ac": "infographic",  "ext": "png", "url_field": "image_url"},
    "briefing_doc": {"ac": "briefing_doc", "ext": "pdf", "url_field": "briefing_doc_url"},
    # Text outputs — saved as markdown
    "text":         {"ac": "text",         "ext": "md",  "url_field": ""},
    "faq":          {"ac": "faq",          "ext": "md",  "url_field": ""},
    "study_guide":  {"ac": "study_guide",  "ext": "md",  "url_field": ""},
    "timeline":     {"ac": "timeline",     "ext": "md",  "url_field": ""},
    "quiz":         {"ac": "quiz",         "ext": "md",  "url_field": ""},
    "datatable":    {"ac": "datatable",    "ext": "md",  "url_field": ""},
}


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {AUTOCONTENT_API_KEY or ''}",
        "content-type": "application/json",
    }


async def _create(
    client: httpx.AsyncClient,
    ac_type: str,
    brief: str,
    title: str,
    our_run_id: str | None,
) -> str:
    body: dict[str, object] = {
        "resources": [{"type": "text", "content": brief}],
        "outputType": ac_type,
        "text": title,
        # `includeCitations: true` is a Pro-only feature; omit it so amateur
        # keys don't 400 with "Citations are only available to PRO subscribers".
    }
    # Podcasts ("audio") default to ~15–17 min on this API; cap at the
    # shortest preset so demo runs complete in ~3–5 min.
    if ac_type == "audio":
        body["duration"] = "short"
    if our_run_id:
        append_event(
            our_run_id, "autocontent", "tool.call",
            f"POST {_CREATE_URL} (outputType={ac_type})",
            data={"outputType": ac_type, "title": title, "brief_chars": len(brief)},
        )
    r = await client.post(_CREATE_URL, headers=_headers(), json=body)
    if r.status_code >= 400:
        body_text = r.text[:500]
        if _is_pro_error(body_text):
            if our_run_id:
                append_event(
                    our_run_id, "autocontent", "tool.skipped",
                    f"AutoContent {ac_type} requires Pro plan",
                    level="warn",
                    data={"status": r.status_code, "body": body_text[:300]},
                )
            raise AutoContentProRequiredError(
                "This output requires an AutoContent Pro plan — coming soon!"
            )
        if our_run_id:
            append_event(
                our_run_id, "autocontent", "tool.error",
                f"AutoContent create failed {r.status_code}",
                level="error",
                data={"status": r.status_code, "body": body_text[:300]},
            )
        raise RuntimeError(
            f"AutoContent create failed {r.status_code}: {body_text[:300]}"
        )
    data = r.json()
    rid = data.get("request_id") or data.get("id")
    if not rid:
        raise RuntimeError(f"AutoContent create missing request_id: {data}")
    if our_run_id:
        append_event(
            our_run_id, "autocontent", "tool.created",
            f"AutoContent job created (id={rid})",
            data={"request_id": rid, "outputType": ac_type},
        )
    return rid


async def _poll_until_done(
    client: httpx.AsyncClient, request_id: str, our_run_id: str | None
) -> dict:
    url = _STATUS_URL_TMPL.format(request_id=request_id)
    polls = 0
    started = time.monotonic()
    last_status: int | None = None
    while True:
        r = await client.get(url, headers=_headers())
        polls += 1
        if r.status_code >= 400:
            if our_run_id:
                append_event(
                    our_run_id, "autocontent", "tool.error",
                    f"AutoContent poll failed {r.status_code}",
                    level="error",
                    data={"status": r.status_code, "body": r.text[:300]},
                )
            raise RuntimeError(
                f"AutoContent poll failed {r.status_code}: {r.text[:300]}"
            )
        data = r.json()
        status = data.get("status")
        error_message = data.get("error_message")
        if our_run_id and isinstance(status, int) and status != last_status:
            append_event(
                our_run_id, "autocontent", "tool.status",
                f"AutoContent status={status} (poll #{polls}, "
                f"{time.monotonic() - started:.1f}s)",
                data={"status": status, "polls": polls, "request_id": request_id},
            )
            last_status = status
        if isinstance(status, int):
            if status == 100:
                # Even at "complete" status, some responses carry an error.
                if error_message and _is_pro_error(str(error_message)):
                    raise AutoContentProRequiredError(
                        "This output requires an AutoContent Pro plan — "
                        "coming soon!"
                    )
                return data
            if status < 0:
                err_str = str(error_message or data)
                if _is_pro_error(err_str):
                    raise AutoContentProRequiredError(
                        "This output requires an AutoContent Pro plan — "
                        "coming soon!"
                    )
                raise RuntimeError(
                    f"AutoContent failed status={status}: "
                    f"{error_message or data}"
                )
        await asyncio.sleep(_POLL_INTERVAL_SECONDS)


async def _download_to(
    client: httpx.AsyncClient, url: str, dest: Path
) -> None:
    # External URLs may not want our auth header — use a fresh client scope
    async with httpx.AsyncClient(timeout=300.0, follow_redirects=True) as c:
        async with c.stream("GET", url) as resp:
            if resp.status_code >= 400:
                raise RuntimeError(
                    f"Download failed {resp.status_code} for {url}"
                )
            with open(dest, "wb") as f:
                async for chunk in resp.aiter_bytes(64 * 1024):
                    if chunk:
                        f.write(chunk)


async def _run(
    run_id: str, artifact_id: str, output_type: str, brief: str
) -> Path:
    cfg = _OUTPUT_MAP.get(output_type)
    if cfg is None:
        raise ValueError(f"Unsupported AutoContent output_type: {output_type}")

    ac_type = cfg["ac"]
    ext = cfg["ext"]
    url_field = cfg["url_field"]
    dest = get_artifact_path(run_id, artifact_id, ext)

    # Trim brief and append per-type brevity guidance. Smaller payload = faster.
    short_brief = brief if len(brief) <= _BRIEF_CHAR_CAP else brief[:_BRIEF_CHAR_CAP] + "\n\n…"
    guidance = _OUTPUT_GUIDANCE.get(output_type, "Keep output concise.")
    title = (
        f"Research Output — {output_type.replace('_', ' ').title()}. "
        f"{guidance}"
    )

    async with httpx.AsyncClient(timeout=60.0) as client:
        request_id = await _create(client, ac_type, short_brief, title, run_id)
        completed = await _poll_until_done(client, request_id, run_id)

        if url_field:
            url = completed.get(url_field) or completed.get("document_url")
            if not url:
                raise RuntimeError(
                    f"AutoContent missing {url_field} in completion: "
                    f"{list(completed.keys())}"
                )
            append_event(
                run_id, "autocontent", "tool.download",
                f"Downloading {output_type} from {url[:80]}",
                data={"output_type": output_type, "url": url},
            )
            await _download_to(client, url, dest)
        else:
            content = (
                completed.get("response_text")
                or completed.get("document_content")
                or ""
            )
            if not content:
                raise RuntimeError(
                    f"AutoContent text output empty; fields: "
                    f"{list(completed.keys())}"
                )
            dest.write_text(content, encoding="utf-8")

    return dest


async def generate_autocontent(
    run_id: str, artifact_id: str, output_type: str, brief: str
) -> Path:
    """Create + fetch an AutoContent artifact.

    `output_type` is one of our OutputType literals (models.py). We map to
    AutoContent's outputType internally. Returns the written file path.
    """
    try:
        return await asyncio.wait_for(
            _run(run_id, artifact_id, output_type, brief),
            timeout=_OVERALL_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError as e:
        raise RuntimeError(
            f"AutoContent timed out after {_OVERALL_TIMEOUT_SECONDS}s"
        ) from e
