"""Parallel Task API client.

Wraps Parallel's deep-research Task API (verified against live API 2026-04-17):
- POST /v1/tasks/runs with x-api-key header creates a task run.
- GET  /v1/tasks/runs/{run_id} polls status.
- GET  /v1/tasks/runs/{run_id}/result returns the final output + citations.

Raises RuntimeError on failure or overall 1800s timeout.
"""

from __future__ import annotations

import asyncio
import time

import httpx

from src.config import PARALLEL_API_KEY
from src.store.events import append_event

_BASE_URL = "https://api.parallel.ai"
_CREATE_URL = f"{_BASE_URL}/v1/tasks/runs"
_POLL_URL_TMPL = f"{_BASE_URL}/v1/tasks/runs/{{run_id}}"
_RESULT_URL_TMPL = f"{_BASE_URL}/v1/tasks/runs/{{run_id}}/result"

_DEPTH_TO_TIER = {
    "quick": "base",
    "standard": "core",
    "deep": "pro",
    "exhaustive": "ultra",
}

_POLL_INTERVAL_SECONDS = 5
_OVERALL_TIMEOUT_SECONDS = 1800
_TERMINAL_STATUSES = {"completed", "failed", "cancelled"}


def _headers() -> dict[str, str]:
    return {
        "x-api-key": PARALLEL_API_KEY or "",
        "content-type": "application/json",
    }


def _build_input(prompt: str, urls: list[str], template: str) -> str:
    """Merge urls + template hint into the task input string.

    Parallel's basic output_schema doesn't accept a separate sources/template
    field; we fold them into the prompt text so the agent sees them.
    """
    parts = [prompt.strip()]
    if template and template != "custom":
        parts.append(f"\nResearch template: {template.replace('_', ' ')}.")
    if urls:
        url_list = "\n".join(f"- {u}" for u in urls if u.strip())
        parts.append(f"\nPrioritise these sources when relevant:\n{url_list}")
    return "\n".join(parts)


async def _create_task(
    client: httpx.AsyncClient,
    prompt_input: str,
    tier: str,
    our_run_id: str | None,
) -> str:
    body = {
        "input": prompt_input,
        "processor": tier,
        "task_spec": {"output_schema": {"type": "text"}},
    }
    if our_run_id:
        append_event(
            our_run_id, "parallel", "tool.call",
            f"POST {_CREATE_URL} (tier={tier})",
            data={
                "tier": tier,
                "input_chars": len(prompt_input),
                "input_preview": prompt_input[:400],
            },
        )
    resp = await client.post(_CREATE_URL, headers=_headers(), json=body)
    if resp.status_code >= 400:
        if our_run_id:
            append_event(
                our_run_id, "parallel", "tool.error",
                f"Parallel create failed {resp.status_code}",
                level="error",
                data={"status": resp.status_code, "body": resp.text[:300]},
            )
        raise RuntimeError(
            f"Parallel create failed {resp.status_code}: {resp.text[:300]}"
        )
    data = resp.json()
    run_id = data.get("run_id") or data.get("id")
    if not run_id:
        raise RuntimeError(f"Parallel create response missing run_id: {data}")
    if our_run_id:
        append_event(
            our_run_id, "parallel", "tool.created",
            f"Parallel task created (id={run_id})",
            data={"parallel_run_id": run_id},
        )
    return run_id


async def _poll_until_terminal(
    client: httpx.AsyncClient, run_id: str, our_run_id: str | None
) -> dict:
    url = _POLL_URL_TMPL.format(run_id=run_id)
    polls = 0
    started = time.monotonic()
    last_status: str | None = None
    while True:
        resp = await client.get(url, headers=_headers())
        polls += 1
        if resp.status_code >= 400:
            if our_run_id:
                append_event(
                    our_run_id, "parallel", "tool.error",
                    f"Parallel poll failed {resp.status_code}",
                    level="error",
                    data={"status": resp.status_code, "body": resp.text[:300]},
                )
            raise RuntimeError(
                f"Parallel poll failed {resp.status_code}: {resp.text[:300]}"
            )
        data = resp.json()
        status = (data.get("status") or "").lower()
        # Skip logging an empty/transient status to avoid a noise event on
        # the first poll if Parallel hasn't assigned one yet.
        if our_run_id and status and status != last_status:
            append_event(
                our_run_id, "parallel", "tool.status",
                f"Parallel status → {status} (poll #{polls}, "
                f"{time.monotonic() - started:.1f}s)",
                data={"status": status, "polls": polls},
            )
            last_status = status
        if status in _TERMINAL_STATUSES:
            if status != "completed":
                err = data.get("error") or data.get("message") or status
                raise RuntimeError(f"Parallel task {status}: {err}")
            return data
        await asyncio.sleep(_POLL_INTERVAL_SECONDS)


async def _fetch_result(
    client: httpx.AsyncClient, run_id: str, our_run_id: str | None
) -> dict:
    url = _RESULT_URL_TMPL.format(run_id=run_id)
    # /result blocks until done; generous timeout
    resp = await client.get(url, headers=_headers(), timeout=300.0)
    if resp.status_code >= 400:
        if our_run_id:
            append_event(
                our_run_id, "parallel", "tool.error",
                f"Parallel result failed {resp.status_code}",
                level="error",
                data={"status": resp.status_code, "body": resp.text[:300]},
            )
        raise RuntimeError(
            f"Parallel result failed {resp.status_code}: {resp.text[:300]}"
        )
    result = resp.json()
    if our_run_id:
        append_event(
            our_run_id, "parallel", "tool.result",
            f"Parallel result fetched ({len(resp.content)} bytes)",
            data={
                "bytes": len(resp.content),
                "keys": list(result.keys()) if isinstance(result, dict) else None,
            },
        )
    return result


async def _run(
    prompt: str,
    urls: list[str],
    template: str,
    tier: str,
    our_run_id: str | None,
) -> dict:
    prompt_input = _build_input(prompt, urls, template)
    async with httpx.AsyncClient(timeout=60.0) as client:
        run_id = await _create_task(client, prompt_input, tier, our_run_id)
        await _poll_until_terminal(client, run_id, our_run_id)
        return await _fetch_result(client, run_id, our_run_id)


async def run_research(
    prompt: str,
    urls: list[str],
    template: str,
    depth: str,
    *,
    run_id: str | None = None,
) -> dict:
    """Run a Parallel deep-research task and return the completed result dict.

    Raises RuntimeError on upstream failure or overall timeout.
    """
    tier = _DEPTH_TO_TIER.get(depth)
    if tier is None:
        raise ValueError(
            f"Unknown depth '{depth}'. Expected one of {sorted(_DEPTH_TO_TIER)}."
        )

    try:
        return await asyncio.wait_for(
            _run(prompt, urls, template, tier, run_id),
            timeout=_OVERALL_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError as e:
        if run_id:
            append_event(
                run_id, "parallel", "tool.timeout",
                f"Parallel research timed out after {_OVERALL_TIMEOUT_SECONDS}s",
                level="error",
            )
        raise RuntimeError(
            f"Parallel research timed out after {_OVERALL_TIMEOUT_SECONDS}s"
        ) from e
