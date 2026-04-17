"""Runs route — create a new research run and poll its state.

See project_overview.md sections 5 and 6 for the route contract and lifecycle.
"""

from __future__ import annotations

import asyncio
from uuid import uuid4

from fastapi import APIRouter, HTTPException

from ..models import RunRequest, RunState
from ..orchestrator import runner
from ..store import runs as runs_store

router = APIRouter()


@router.post("/runs")
async def create_run(req: RunRequest) -> dict[str, str]:
    """Create a new run, kick off the orchestrator task, return the run id."""
    run_id = str(uuid4())
    runs_store.create_run(run_id, req)
    asyncio.create_task(runner.start(run_id, req))
    return {"run_id": run_id}


@router.get("/runs")
def list_runs_route() -> list[dict]:
    """Return a compact newest-first summary of recent runs for the UI."""
    rows = runs_store.list_runs(limit=50)
    return [
        {
            "run_id": r.run_id,
            "created_at": r.created_at or "",
            "status": r.status,
            "prompt": r.request.prompt if r.request else "",
            "outputs": r.request.outputs if r.request else [],
        }
        for r in rows
    ]


@router.get("/runs/{run_id}")
async def get_run(run_id: str) -> RunState:
    """Return the full RunState for polling clients, or 404 if missing."""
    state = runs_store.get_run(run_id)
    if state is None:
        raise HTTPException(status_code=404, detail="run not found")
    return state
