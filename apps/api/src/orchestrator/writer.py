"""Writer — generate a single artifact for a run.

Dispatches on `output_type`:
  * Report types (`report_1pg`, `report_5pg`, `competitor_doc`) → LLM writes
    markdown, then `reportgen.generate_report_pdf` renders it to PDF.
  * ElevenLabs types (`elevenlabs_audio`, `elevenlabs_video`) → independent
    TTS pipeline in `tools.elevenlabs` (does not touch AutoContent).
  * Everything else (podcast / slides / video / infographic / briefing_doc /
    faq / study_guide / timeline / quiz / datatable / text) → AutoContent job.

Always returns an ArtifactMeta — errors are captured as status="error".
"""

from __future__ import annotations

import asyncio

from ..models import ArtifactMeta
from ..store import runs as runs_store
from ..store.artifacts_dir import artifacts_base
from ..store.events import append_event
from ..tools import autocontent, elevenlabs, llm, reportgen
from ..tools.autocontent import AutoContentProRequiredError
from ..tools.elevenlabs import ElevenLabsKeyMissingError

_REPORT_TYPES = {"report_1pg", "report_5pg", "competitor_doc"}
_ELEVENLABS_TYPES = {"elevenlabs_audio", "elevenlabs_video"}

_REPORT_TITLES: dict[str, str] = {
    "report_1pg": "One-Page Research Brief",
    "report_5pg": "In-Depth Research Report",
    "competitor_doc": "Competitor Analysis",
}


async def generate_output(
    run_id: str,
    artifact_id: str,
    output_type: str,
    brief: str,
) -> ArtifactMeta:
    """Run a single output job and return its final ArtifactMeta."""
    # Mark artifact as running in the store.
    runs_store.upsert_artifact(
        run_id,
        ArtifactMeta(
            id=artifact_id,
            type=output_type,  # type: ignore[arg-type]
            status="running",
            filename="",
        ),
    )
    append_event(
        run_id, "writer", "artifact.start",
        f"Writer start: {output_type}",
        data={"output_type": output_type, "artifact_id": artifact_id},
    )

    try:
        if output_type in _REPORT_TYPES:
            content_md = await llm.write_report(
                brief, output_type, run_id=run_id
            )
            title = _REPORT_TITLES[output_type]
            append_event(
                run_id, "writer", "report.render",
                f"Rendering PDF for {output_type} ({len(content_md)} md chars)",
                data={"output_type": output_type, "md_chars": len(content_md)},
            )
            # Persist source markdown as a sidecar so the chat route can
            # fold report content into its context (PDFs aren't text-readable).
            # Best-effort — failure here does not block PDF render.
            if content_md.strip():
                try:
                    sidecar = artifacts_base() / run_id / f"{artifact_id}.md"
                    sidecar.parent.mkdir(parents=True, exist_ok=True)
                    sidecar.write_text(
                        f"# {title}\n\n{content_md}", encoding="utf-8"
                    )
                except OSError as sidecar_err:
                    append_event(
                        run_id, "writer", "report.sidecar_skip",
                        f"Report sidecar .md skipped: {sidecar_err}",
                        level="warn",
                        data={"output_type": output_type},
                    )
            path = await asyncio.to_thread(
                reportgen.generate_report_pdf,
                run_id,
                artifact_id,
                content_md,
                title,
            )
        elif output_type in _ELEVENLABS_TYPES:
            # Independent pipeline — does not touch AutoContent / reportgen.
            path = await elevenlabs.generate_elevenlabs(
                run_id, artifact_id, output_type, brief
            )
        else:
            # podcast | slides | video | infographic | briefing_doc | text ...
            path = await autocontent.generate_autocontent(
                run_id, artifact_id, output_type, brief
            )

        done_meta = ArtifactMeta(
            id=artifact_id,
            type=output_type,  # type: ignore[arg-type]
            status="done",
            filename=path.name,
        )
        runs_store.upsert_artifact(run_id, done_meta)
        append_event(
            run_id, "writer", "artifact.done",
            f"Writer done: {output_type} → {path.name}",
            data={"output_type": output_type, "filename": path.name},
        )
        return done_meta
    except ElevenLabsKeyMissingError as e:
        err_meta = ArtifactMeta(
            id=artifact_id,
            type=output_type,  # type: ignore[arg-type]
            status="error",
            filename="",
            error=str(e),
        )
        runs_store.upsert_artifact(run_id, err_meta)
        append_event(
            run_id, "writer", "artifact.skipped",
            f"{output_type} skipped — ELEVENLABS_API_KEY not set",
            level="warn",
            data={"output_type": output_type},
        )
        return err_meta
    except AutoContentProRequiredError:
        err_meta = ArtifactMeta(
            id=artifact_id,
            type=output_type,  # type: ignore[arg-type]
            status="error",
            filename="",
            error="Coming soon — requires AutoContent Pro plan",
        )
        runs_store.upsert_artifact(run_id, err_meta)
        append_event(
            run_id, "writer", "artifact.skipped",
            f"{output_type} requires AutoContent Pro — skipped",
            level="warn",
            data={"output_type": output_type},
        )
        return err_meta
    except Exception as e:  # noqa: BLE001
        err_meta = ArtifactMeta(
            id=artifact_id,
            type=output_type,  # type: ignore[arg-type]
            status="error",
            filename="",
            error=str(e),
        )
        runs_store.upsert_artifact(run_id, err_meta)
        append_event(
            run_id, "writer", "artifact.error",
            f"Writer {output_type} error: {e}",
            level="error",
            data={"output_type": output_type, "error": str(e)},
        )
        return err_meta
