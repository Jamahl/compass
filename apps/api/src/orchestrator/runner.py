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
from ..store.artifacts_dir import artifacts_base
from ..store.contexts_dir import get_contexts_base, load_context_files
from ..store.events import append_event
from ..tools import llm, parallel
from . import writer


async def start(run_id: str, request: RunRequest) -> None:
    """Run research → synthesize → writer fan-out for a single run."""
    try:
        append_event(
            run_id, "runner", "run.start",
            f"Run started — template={request.template} depth={request.depth} "
            f"outputs={request.outputs}",
            data={
                "prompt": request.prompt[:500],
                "urls": request.urls,
                "template": request.template,
                "depth": request.depth,
                "outputs": request.outputs,
                "context_files": request.context_files,
            },
        )
        # ---- 1. Research -----------------------------------------------------
        runs_store.update_stage(run_id, "research", "running")
        append_event(
            run_id, "runner", "stage.start",
            "Stage research started",
            data={"stage": "research"},
        )

        # If the user selected context files, load them and prepend to the
        # prompt as an "Internal Context" block. Leaves urls/template/depth
        # untouched — context only affects the prompt text.
        research_prompt = request.prompt
        if request.context_files:
            base = get_contexts_base()
            loaded = load_context_files(request.context_files)
            loaded_names = [name for name, _ in loaded]
            missing = [
                f for f in request.context_files
                if f and not any(n.lower() == f.rsplit('.', 1)[0].lower() for n in loaded_names)
            ]
            if loaded:
                blocks = "\n\n".join(
                    f"## {name}\n{content}" for name, content in loaded
                )
                research_prompt = (
                    "INTERNAL CONTEXT — reference these documents when "
                    "generating findings:\n\n"
                    f"{blocks}\n\n"
                    "---\n\n"
                    "RESEARCH REQUEST:\n"
                    f"{request.prompt}"
                )
                append_event(
                    run_id, "runner", "context.loaded",
                    f"Loaded {len(loaded)} context file(s) into research prompt: "
                    f"{', '.join(loaded_names)}",
                    data={
                        "base_dir": str(base),
                        "files": loaded_names,
                        "requested": request.context_files,
                        "missing": missing,
                        "total_chars": sum(len(c) for _, c in loaded),
                        "prompt_chars": len(research_prompt),
                    },
                )
            else:
                append_event(
                    run_id, "runner", "context.empty",
                    f"Context requested but none loaded "
                    f"(base={base}, requested={request.context_files})",
                    level="warn",
                    data={
                        "base_dir": str(base),
                        "requested": request.context_files,
                        "base_exists": base.exists(),
                    },
                )
        else:
            append_event(
                run_id, "runner", "context.none",
                "No context files selected — using prompt only",
            )

        try:
            payload = await parallel.run_research(
                research_prompt,
                request.urls,
                request.template,
                request.depth,
                run_id=run_id,
            )
            runs_store.update_run(
                run_id, research_payload=json.dumps(payload)
            )
            runs_store.update_stage(run_id, "research", "done")
            append_event(
                run_id, "runner", "stage.done",
                "Stage research complete",
                data={
                    "stage": "research",
                    "payload_chars": len(json.dumps(payload, default=str)),
                },
            )
        except Exception as e:  # noqa: BLE001 — stage-level catch
            runs_store.update_stage(run_id, "research", "error", str(e))
            runs_store.update_run(run_id, status="failed")
            append_event(
                run_id, "runner", "stage.error",
                f"Stage research failed: {e}",
                level="error",
                data={"stage": "research", "error": str(e)},
            )
            return

        # Chat unlocks at this point (research_payload populated).
        runs_store.update_run(run_id, status="research_done")

        # ---- 2. Synthesize ---------------------------------------------------
        runs_store.update_stage(run_id, "synthesize", "running")
        append_event(
            run_id, "runner", "stage.start",
            "Stage synthesize started",
            data={"stage": "synthesize"},
        )
        try:
            brief = await llm.synthesize(payload, run_id=run_id)
            # Persist the synthesized brief as a sidecar markdown file so the
            # chat route can include it in context (higher signal than the raw
            # Parallel JSON payload). Best-effort; write failure must not break
            # the downstream writer fan-out.
            try:
                brief_path = artifacts_base() / run_id / "brief.md"
                brief_path.parent.mkdir(parents=True, exist_ok=True)
                brief_path.write_text(brief, encoding="utf-8")
            except OSError as brief_err:
                append_event(
                    run_id, "runner", "brief.sidecar_skip",
                    f"brief.md sidecar skipped: {brief_err}",
                    level="warn",
                )
            runs_store.update_stage(run_id, "synthesize", "done")
            append_event(
                run_id, "runner", "stage.done",
                "Stage synthesize complete",
                data={"stage": "synthesize", "brief_chars": len(brief)},
            )
        except Exception as e:  # noqa: BLE001
            runs_store.update_stage(run_id, "synthesize", "error", str(e))
            runs_store.update_run(run_id, status="failed")
            append_event(
                run_id, "runner", "stage.error",
                f"Stage synthesize failed: {e}",
                level="error",
                data={"stage": "synthesize", "error": str(e)},
            )
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

        append_event(
            run_id, "runner", "writer.fanout",
            f"Dispatching {len(pairs)} writer task(s)",
            data={"outputs": [otype for _, otype in pairs]},
        )

        results = await asyncio.gather(
            *[
                writer.generate_output(run_id, aid, otype, brief)
                for aid, otype in pairs
            ],
            return_exceptions=True,
        )

        # Writer.generate_output catches all internal errors and returns an
        # ArtifactMeta with status="error" — it never raises. The Exception
        # branch is reserved for unexpected failures asyncio.gather catches.
        ok = err = 0
        for (aid, otype), result in zip(pairs, results):
            if isinstance(result, Exception):
                err += 1
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
                append_event(
                    run_id, "writer", "artifact.error",
                    f"Writer {otype} failed: {result}",
                    level="error",
                    data={"output_type": otype, "error": str(result)},
                )
            else:
                if result.status == "error":
                    err += 1
                else:
                    ok += 1
                runs_store.upsert_artifact(run_id, result)

        # Run is "completed" even if some artifacts errored.
        runs_store.update_run(run_id, status="completed")
        append_event(
            run_id, "runner", "run.done",
            f"Run complete — {ok} ok, {err} failed",
            data={"ok": ok, "err": err},
        )

    except Exception as e:  # noqa: BLE001 — outer guard
        # Belt-and-braces: any unhandled exception must not kill the task.
        runs_store.update_run(run_id, status="failed")
        # Best-effort surface of the error on whatever stage is running.
        runs_store.update_stage(run_id, "runner", "error", str(e))
        append_event(
            run_id, "runner", "run.fatal",
            f"Run aborted: {e}",
            level="error",
            data={"error": str(e)},
        )
