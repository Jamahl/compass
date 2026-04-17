"""ElevenLabs pipeline — independent of AutoContent.

Two output types:
  * ``elevenlabs_audio`` → TTS narration of the brief → MP3
  * ``elevenlabs_video`` → TTS narration + generated title-card still → MP4

Runs fully parallel to AutoContent / reportgen. No shared state.

Docs: https://elevenlabs.io/docs/api-reference/introduction
TTS endpoint: POST /v1/text-to-speech/{voice_id}

ElevenLabs has no public text-to-video endpoint, so the "video" here is a
simple narrated title card: PNG (Pillow) + MP3 (TTS) muxed with ffmpeg
(binary shipped via imageio-ffmpeg, so no apt-get needed).
"""

from __future__ import annotations

import asyncio
import os
import re
import subprocess
from pathlib import Path

import httpx
from imageio_ffmpeg import get_ffmpeg_exe
from PIL import Image, ImageDraw, ImageFont

from src.config import ELEVENLABS_API_KEY
from src.store.artifacts_dir import get_artifact_path
from src.store.events import append_event

_BASE = "https://api.elevenlabs.io"
_TTS_URL_TMPL = f"{_BASE}/v1/text-to-speech/{{voice_id}}"

# Default voice — George, freely available on all plans.
# Override by setting ELEVENLABS_VOICE_ID env var if desired.
_DEFAULT_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "JBFqnCBsd6RMkjVDRZzb")
_DEFAULT_MODEL_ID = os.getenv("ELEVENLABS_MODEL_ID", "eleven_turbo_v2_5")
_OUTPUT_FORMAT = "mp3_44100_128"

# TTS character cap. ElevenLabs bills per character; keep demo runs cheap.
_TTS_CHAR_CAP = 2500

# Overall timeout for a single ElevenLabs output (generous for long narrations).
_OVERALL_TIMEOUT_SECONDS = 600


class ElevenLabsKeyMissingError(RuntimeError):
    """Raised when ELEVENLABS_API_KEY is not configured."""


def _headers() -> dict[str, str]:
    if not ELEVENLABS_API_KEY:
        raise ElevenLabsKeyMissingError(
            "ELEVENLABS_API_KEY not set — add it to .env to enable ElevenLabs outputs."
        )
    return {
        "xi-api-key": ELEVENLABS_API_KEY,
        "accept": "audio/mpeg",
        "content-type": "application/json",
    }


# --- Narration prep ---------------------------------------------------------

_MARKDOWN_PATTERNS = [
    (re.compile(r"```.*?```", re.DOTALL), " "),   # fenced code blocks
    (re.compile(r"`([^`]*)`"), r"\1"),             # inline code
    (re.compile(r"!\[[^\]]*\]\([^)]*\)"), " "),    # images
    (re.compile(r"\[([^\]]+)\]\([^)]+\)"), r"\1"), # links → link text
    (re.compile(r"^#{1,6}\s*", re.MULTILINE), ""), # heading hashes
    (re.compile(r"(\*\*|__)(.+?)\1"), r"\2"),      # bold
    (re.compile(r"(\*|_)(.+?)\1"), r"\2"),         # italics
    (re.compile(r"^\s*[-*+]\s+", re.MULTILINE), "- "),  # bullets → "- "
    (re.compile(r"\|"), " "),                      # table pipes
    (re.compile(r"\s+"), " "),                     # collapse whitespace
]


def _markdown_to_speech(md: str) -> str:
    """Strip markdown → clean sentence text for TTS."""
    text = md
    for pat, repl in _MARKDOWN_PATTERNS:
        text = pat.sub(repl, text)
    return text.strip()


def _prep_narration(brief: str) -> str:
    text = _markdown_to_speech(brief)
    if len(text) <= _TTS_CHAR_CAP:
        return text
    # Trim at the last sentence boundary before the cap.
    head = text[:_TTS_CHAR_CAP]
    cut = max(head.rfind(". "), head.rfind("? "), head.rfind("! "))
    return head[: cut + 1] if cut > 0 else head


# --- TTS --------------------------------------------------------------------

async def _synthesize_mp3(
    brief: str, dest: Path, run_id: str | None, voice_id: str
) -> None:
    narration = _prep_narration(brief)
    if not narration:
        raise RuntimeError("ElevenLabs TTS: narration empty after prep.")

    url = _TTS_URL_TMPL.format(voice_id=voice_id)
    # ElevenLabs takes `output_format` as a query param, not in the JSON body.
    params = {"output_format": _OUTPUT_FORMAT}
    body = {
        "text": narration,
        "model_id": _DEFAULT_MODEL_ID,
    }

    if run_id:
        append_event(
            run_id, "elevenlabs", "tool.call",
            f"POST {url} (chars={len(narration)}, voice={voice_id})",
            data={"chars": len(narration), "voice": voice_id, "model": _DEFAULT_MODEL_ID},
        )

    async with httpx.AsyncClient(timeout=300.0) as client:
        async with client.stream(
            "POST", url, headers=_headers(), params=params, json=body
        ) as resp:
            if resp.status_code >= 400:
                body_text = (await resp.aread()).decode("utf-8", errors="replace")[:500]
                if run_id:
                    append_event(
                        run_id, "elevenlabs", "tool.error",
                        f"ElevenLabs TTS failed {resp.status_code}",
                        level="error",
                        data={"status": resp.status_code, "body": body_text[:300]},
                    )
                raise RuntimeError(
                    f"ElevenLabs TTS failed {resp.status_code}: {body_text[:300]}"
                )
            with open(dest, "wb") as f:
                async for chunk in resp.aiter_bytes(64 * 1024):
                    if chunk:
                        f.write(chunk)

    if run_id:
        append_event(
            run_id, "elevenlabs", "tool.download",
            f"TTS complete → {dest.name} ({dest.stat().st_size} bytes)",
            data={"bytes": dest.stat().st_size, "filename": dest.name},
        )


# --- Title-card image -------------------------------------------------------

_TITLE_W, _TITLE_H = 1280, 720
_BG = (15, 23, 42)       # slate-900
_ACCENT = (99, 102, 241) # indigo-500
_TEXT = (241, 245, 249)  # slate-100
_MUTED = (148, 163, 184) # slate-400


def _pick_font(size: int) -> ImageFont.ImageFont:
    """Use the first available system font; fall back to default bitmap font."""
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


def _first_heading_or_sentence(brief: str) -> str:
    for line in brief.splitlines():
        stripped = line.strip().lstrip("#").strip()
        if stripped:
            return stripped[:80]
    return "Research Brief"


def _wrap(text: str, font: ImageFont.ImageFont, max_w: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    cur: list[str] = []
    for w in words:
        trial = " ".join(cur + [w])
        bbox = font.getbbox(trial)
        if bbox[2] - bbox[0] > max_w and cur:
            lines.append(" ".join(cur))
            cur = [w]
        else:
            cur.append(w)
    if cur:
        lines.append(" ".join(cur))
    return lines


def _render_title_card(brief: str, out_png: Path) -> None:
    img = Image.new("RGB", (_TITLE_W, _TITLE_H), _BG)
    draw = ImageDraw.Draw(img)

    # Accent bar (left edge).
    draw.rectangle([0, 0, 12, _TITLE_H], fill=_ACCENT)

    # Kicker.
    kicker_font = _pick_font(36)
    draw.text((80, 120), "BetterLabs Compass", font=kicker_font, fill=_MUTED)

    # Title (wrapped).
    title_font = _pick_font(72)
    title = _first_heading_or_sentence(brief)
    for i, line in enumerate(_wrap(title, title_font, _TITLE_W - 160)[:3]):
        draw.text((80, 200 + i * 90), line, font=title_font, fill=_TEXT)

    # Footer.
    foot_font = _pick_font(28)
    draw.text(
        (80, _TITLE_H - 80),
        "Narrated research brief · ElevenLabs",
        font=foot_font,
        fill=_MUTED,
    )

    img.save(out_png, "PNG", optimize=True)


# --- ffmpeg mux -------------------------------------------------------------

def _mux_png_mp3_to_mp4(png: Path, mp3: Path, mp4: Path) -> None:
    """Combine a single still image with an MP3 into an MP4.

    Uses the ffmpeg binary bundled with imageio-ffmpeg (no apt-get needed).
    """
    ffmpeg = get_ffmpeg_exe()
    cmd = [
        ffmpeg, "-y",
        "-loop", "1", "-i", str(png),   # looped still image
        "-i", str(mp3),                 # audio track
        "-c:v", "libx264", "-tune", "stillimage", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "160k",
        "-shortest",                    # stop when audio ends
        "-movflags", "+faststart",
        str(mp4),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"ffmpeg mux failed (rc={result.returncode}): "
            f"{result.stderr[-400:]}"
        )


# --- Public API -------------------------------------------------------------

async def _run_audio(run_id: str, artifact_id: str, brief: str) -> Path:
    dest = get_artifact_path(run_id, artifact_id, "mp3")
    await _synthesize_mp3(brief, dest, run_id, _DEFAULT_VOICE_ID)
    return dest


async def _run_video(run_id: str, artifact_id: str, brief: str) -> Path:
    # Intermediate files must NOT match `{artifact_id}.*` — the artifact route
    # uses `rglob(f"{artifact_id}.*")` to resolve downloads, so a stale temp
    # file with that prefix could be served instead of the final MP4. Using
    # `{artifact_id}__*` keeps them out of that glob (literal `.` required).
    mp4_path = get_artifact_path(run_id, artifact_id, "mp4")
    run_dir = mp4_path.parent
    mp3_path = run_dir / f"{artifact_id}__narration.mp3"
    png_path = run_dir / f"{artifact_id}__card.png"

    # 1) Synthesize narration.
    await _synthesize_mp3(brief, mp3_path, run_id, _DEFAULT_VOICE_ID)

    # 2) Render title card (Pillow — CPU, offload from event loop).
    append_event(
        run_id, "elevenlabs", "report.render",
        "Rendering title-card PNG",
        data={"size": f"{_TITLE_W}x{_TITLE_H}"},
    )
    await asyncio.to_thread(_render_title_card, brief, png_path)

    # 3) Mux PNG + MP3 → MP4 (ffmpeg — blocking subprocess, offload).
    append_event(
        run_id, "elevenlabs", "tool.call",
        "ffmpeg mux PNG+MP3 → MP4",
        data={"png": png_path.name, "mp3": mp3_path.name, "mp4": mp4_path.name},
    )
    await asyncio.to_thread(_mux_png_mp3_to_mp4, png_path, mp3_path, mp4_path)

    # Clean up intermediates — the served artifact is the MP4 only.
    for tmp in (mp3_path, png_path):
        try:
            tmp.unlink()
        except OSError:
            pass

    return mp4_path


async def generate_elevenlabs(
    run_id: str, artifact_id: str, output_type: str, brief: str
) -> Path:
    """Dispatch to the right ElevenLabs pipeline.

    `output_type` is one of ``elevenlabs_audio`` | ``elevenlabs_video``.
    """
    if output_type == "elevenlabs_audio":
        coro = _run_audio(run_id, artifact_id, brief)
    elif output_type == "elevenlabs_video":
        coro = _run_video(run_id, artifact_id, brief)
    else:
        raise ValueError(f"Unsupported ElevenLabs output_type: {output_type}")

    try:
        return await asyncio.wait_for(coro, timeout=_OVERALL_TIMEOUT_SECONDS)
    except asyncio.TimeoutError as e:
        raise RuntimeError(
            f"ElevenLabs timed out after {_OVERALL_TIMEOUT_SECONDS}s"
        ) from e
