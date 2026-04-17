"""Parallel Task API client.

Wraps Parallel's deep-research Task API (verified against live API 2026-04-17):
- POST /v1/tasks/runs with x-api-key header creates a task run.
- GET  /v1/tasks/runs/{run_id} polls status.
- GET  /v1/tasks/runs/{run_id}/result returns the final output + citations.

Raises RuntimeError on failure or overall 600s timeout.
"""

from __future__ import annotations

import asyncio

import httpx

from src.config import PARALLEL_API_KEY

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
_OVERALL_TIMEOUT_SECONDS = 600
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
    client: httpx.AsyncClient, prompt_input: str, tier: str
) -> str:
    body = {
        "input": prompt_input,
        "processor": tier,
        "task_spec": {"output_schema": {"type": "text"}},
    }
    resp = await client.post(_CREATE_URL, headers=_headers(), json=body)
    if resp.status_code >= 400:
        raise RuntimeError(
            f"Parallel create failed {resp.status_code}: {resp.text[:300]}"
        )
    data = resp.json()
    run_id = data.get("run_id") or data.get("id")
    if not run_id:
        raise RuntimeError(f"Parallel create response missing run_id: {data}")
    return run_id


async def _poll_until_terminal(
    client: httpx.AsyncClient, run_id: str
) -> dict:
    url = _POLL_URL_TMPL.format(run_id=run_id)
    while True:
        resp = await client.get(url, headers=_headers())
        if resp.status_code >= 400:
            raise RuntimeError(
                f"Parallel poll failed {resp.status_code}: {resp.text[:300]}"
            )
        data = resp.json()
        status = (data.get("status") or "").lower()
        if status in _TERMINAL_STATUSES:
            if status != "completed":
                err = data.get("error") or data.get("message") or status
                raise RuntimeError(f"Parallel task {status}: {err}")
            return data
        await asyncio.sleep(_POLL_INTERVAL_SECONDS)


async def _fetch_result(client: httpx.AsyncClient, run_id: str) -> dict:
    url = _RESULT_URL_TMPL.format(run_id=run_id)
    # /result blocks until done; generous timeout
    resp = await client.get(url, headers=_headers(), timeout=300.0)
    if resp.status_code >= 400:
        raise RuntimeError(
            f"Parallel result failed {resp.status_code}: {resp.text[:300]}"
        )
    return resp.json()


async def _run(prompt: str, urls: list[str], template: str, tier: str) -> dict:
    prompt_input = _build_input(prompt, urls, template)
    async with httpx.AsyncClient(timeout=60.0) as client:
        run_id = await _create_task(client, prompt_input, tier)
        await _poll_until_terminal(client, run_id)
        return await _fetch_result(client, run_id)


async def run_research(
    prompt: str, urls: list[str], template: str, depth: str
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
            _run(prompt, urls, template, tier),
            timeout=_OVERALL_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError as e:
        raise RuntimeError(
            f"Parallel research timed out after {_OVERALL_TIMEOUT_SECONDS}s"
        ) from e
