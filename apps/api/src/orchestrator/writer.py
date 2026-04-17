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

    try:
        if output_type in _REPORT_TYPES:
            content_md = await llm.write_report(brief, output_type)
            title = _REPORT_TITLES[output_type]
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

        return ArtifactMeta(
            id=artifact_id,
            type=output_type,  # type: ignore[arg-type]
            status="done",
            filename=path.name,
        )
    except AutoContentProRequiredError:
        return ArtifactMeta(
            id=artifact_id,
            type=output_type,  # type: ignore[arg-type]
            status="error",
            filename="",
            error="Coming soon — requires AutoContent Pro plan",
        )
    except Exception as e:  # noqa: BLE001
        return ArtifactMeta(
            id=artifact_id,
            type=output_type,  # type: ignore[arg-type]
            status="error",
            filename="",
            error=str(e),
        )
