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
from pathlib import Path

import httpx

from src.config import AUTOCONTENT_API_KEY
from src.store.artifacts_dir import get_artifact_path

_BASE = "https://api.autocontentapi.com"
_CREATE_URL = f"{_BASE}/content/Create"
_STATUS_URL_TMPL = f"{_BASE}/content/Status/{{request_id}}"

_POLL_INTERVAL_SECONDS = 5
_OVERALL_TIMEOUT_SECONDS = 900

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
    client: httpx.AsyncClient, ac_type: str, brief: str, title: str
) -> str:
    body = {
        "resources": [{"type": "text", "content": brief}],
        "outputType": ac_type,
        "text": title,
        "includeCitations": True,
    }
    r = await client.post(_CREATE_URL, headers=_headers(), json=body)
    if r.status_code >= 400:
        raise RuntimeError(
            f"AutoContent create failed {r.status_code}: {r.text[:300]}"
        )
    data = r.json()
    rid = data.get("request_id") or data.get("id")
    if not rid:
        raise RuntimeError(f"AutoContent create missing request_id: {data}")
    return rid


async def _poll_until_done(
    client: httpx.AsyncClient, request_id: str
) -> dict:
    url = _STATUS_URL_TMPL.format(request_id=request_id)
    while True:
        r = await client.get(url, headers=_headers())
        if r.status_code >= 400:
            raise RuntimeError(
                f"AutoContent poll failed {r.status_code}: {r.text[:300]}"
            )
        data = r.json()
        status = data.get("status")
        if isinstance(status, int):
            if status == 100:
                return data
            if status < 0:
                raise RuntimeError(
                    f"AutoContent failed status={status}: "
                    f"{data.get('error_message') or data}"
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
    title = f"Research Output — {output_type.replace('_', ' ').title()}"

    async with httpx.AsyncClient(timeout=60.0) as client:
        request_id = await _create(client, ac_type, brief, title)
        completed = await _poll_until_done(client, request_id)

        if url_field:
            url = completed.get(url_field) or completed.get("document_url")
            if not url:
                raise RuntimeError(
                    f"AutoContent missing {url_field} in completion: "
                    f"{list(completed.keys())}"
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
