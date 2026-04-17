"""Runner — top-level orchestration for a single run.

Sequence (see project_overview.md section 6):
  1. research     — Parallel Task API
  2. synthesize   — LLM distils brief from research payload
  3. fan-out      — one writer task per requested output, gathered concurrently

The function is wrapped in an outer try/except so that an unexpected exception
never kills the background task silently; on top-level failure the run status
is set to "failed".
"""

from __future__ import annotations

import asyncio
import json
from uuid import uuid4

from ..models import ArtifactMeta, RunRequest
from ..store import runs as runs_store
from ..tools import llm, parallel
from . import writer


async def start(run_id: str, request: RunRequest) -> None:
    """Run research → synthesize → writer fan-out for a single run."""
    try:
        # ---- 1. Research -----------------------------------------------------
        runs_store.update_stage(run_id, "research", "running")
        try:
            payload = await parallel.run_research(
                request.prompt,
                request.urls,
                request.template,
                request.depth,
            )
            runs_store.update_run(
                run_id, research_payload=json.dumps(payload)
            )
            runs_store.update_stage(run_id, "research", "done")
        except Exception as e:  # noqa: BLE001 — stage-level catch
            runs_store.update_stage(run_id, "research", "error", str(e))
            runs_store.update_run(run_id, status="failed")
            return

        # Chat unlocks at this point (research_payload populated).
        runs_store.update_run(run_id, status="research_done")

        # ---- 2. Synthesize ---------------------------------------------------
        runs_store.update_stage(run_id, "synthesize", "running")
        try:
            brief = await llm.synthesize(payload)
            runs_store.update_stage(run_id, "synthesize", "done")
        except Exception as e:  # noqa: BLE001
            runs_store.update_stage(run_id, "synthesize", "error", str(e))
            runs_store.update_run(run_id, status="failed")
            return

        # ---- 3. Writer fan-out ----------------------------------------------
        pairs: list[tuple[str, str]] = []
        for output_type in request.outputs:
            artifact_id = str(uuid4())
            meta = ArtifactMeta(
                id=artifact_id,
                type=output_type,
                status="pending",
                filename="",
            )
            runs_store.upsert_artifact(run_id, meta)
            pairs.append((artifact_id, output_type))

        results = await asyncio.gather(
            *[
                writer.generate_output(run_id, aid, otype, brief)
                for aid, otype in pairs
            ],
            return_exceptions=True,
        )

        for (aid, otype), result in zip(pairs, results):
            if isinstance(result, Exception):
                runs_store.upsert_artifact(
                    run_id,
                    ArtifactMeta(
                        id=aid,
                        type=otype,
                        status="error",
                        filename="",
                        error=str(result),
                    ),
                )
            else:
                runs_store.upsert_artifact(run_id, result)

        # Run is "completed" even if some artifacts errored.
        runs_store.update_run(run_id, status="completed")

    except Exception as e:  # noqa: BLE001 — outer guard
        # Belt-and-braces: any unhandled exception must not kill the task.
        runs_store.update_run(run_id, status="failed")
        # Best-effort surface of the error on whatever stage is running.
        runs_store.update_stage(run_id, "runner", "error", str(e))
