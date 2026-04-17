"""Writer — generate a single artifact for a run.

Dispatches on `output_type`:
  * Report types (`report_1pg`, `report_5pg`, `competitor_doc`) → LLM writes
    markdown, then `reportgen.generate_report_pdf` renders it to PDF.
  * Media types (`podcast`, `slides`, `video`) → AutoContent job.

Always returns an ArtifactMeta — errors are captured as status="error".
"""

from __future__ import annotations

import asyncio

from ..models import ArtifactMeta
from ..store import runs as runs_store
from ..store.events import append_event
from ..tools import autocontent, llm, reportgen
from ..tools.autocontent import AutoContentProRequiredError

_REPORT_TYPES = {"report_1pg", "report_5pg", "competitor_doc"}

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
            path = await asyncio.to_thread(
                reportgen.generate_report_pdf,
                run_id,
                artifact_id,
                content_md,
                title,
            )
        else:
            # podcast | slides | video
            path = await autocontent.generate_autocontent(
                run_id, artifact_id, output_type, brief
            )

        append_event(
            run_id, "writer", "artifact.done",
            f"Writer done: {output_type} → {path.name}",
            data={"output_type": output_type, "filename": path.name},
        )
        return ArtifactMeta(
            id=artifact_id,
            type=output_type,  # type: ignore[arg-type]
            status="done",
            filename=path.name,
        )
    except AutoContentProRequiredError:
        append_event(
            run_id, "writer", "artifact.skipped",
            f"{output_type} requires AutoContent Pro — skipped",
            level="warn",
            data={"output_type": output_type},
        )
        return ArtifactMeta(
            id=artifact_id,
            type=output_type,  # type: ignore[arg-type]
            status="error",
            filename="",
            error="Coming soon — requires AutoContent Pro plan",
        )
    except Exception as e:  # noqa: BLE001
        append_event(
            run_id, "writer", "artifact.error",
            f"Writer {output_type} error: {e}",
            level="error",
            data={"output_type": output_type, "error": str(e)},
        )
        return ArtifactMeta(
            id=artifact_id,
            type=output_type,  # type: ignore[arg-type]
            status="error",
            filename="",
            error=str(e),
        )
