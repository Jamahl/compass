"""Artifact download / preview route.

Serves artifact files stored under the artifacts base directory by
resolving the artifact ID to the first matching file on disk.

By default serves inline (so PDFs / media / images render in the browser).
Pass ``?download=1`` to force a download.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from ..store.artifacts_dir import artifacts_base

router = APIRouter()


_MEDIA_TYPES: dict[str, str] = {
    ".pdf": "application/pdf",
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".m4a": "audio/mp4",
    ".mp4": "video/mp4",
    ".webm": "video/webm",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".svg": "image/svg+xml",
    ".md": "text/markdown; charset=utf-8",
    ".txt": "text/plain; charset=utf-8",
    ".pptx": (
        "application/vnd.openxmlformats-officedocument"
        ".presentationml.presentation"
    ),
}


def _guess_media_type(path: Path) -> str:
    return _MEDIA_TYPES.get(path.suffix.lower(), "application/octet-stream")


@router.get("/artifacts/{artifact_id}")
def get_artifact(artifact_id: str, download: int = 0) -> FileResponse:
    """Return the artifact file matching ``artifact_id`` by basename.

    - Default: ``Content-Disposition: inline`` so the browser can render/play
      it directly (PDF, audio, video, image).
    - ``?download=1``: ``attachment`` to force a Save-As.
    """
    base: Path = artifacts_base()
    match: Path | None = next(base.rglob(f"{artifact_id}.*"), None)
    if match is None or not match.is_file():
        raise HTTPException(status_code=404, detail="artifact not found")

    media_type: str = _guess_media_type(match)
    disposition = "attachment" if download else "inline"
    return FileResponse(
        path=match,
        filename=match.name,
        media_type=media_type,
        headers={
            "Content-Disposition": f'{disposition}; filename="{match.name}"',
        },
    )
