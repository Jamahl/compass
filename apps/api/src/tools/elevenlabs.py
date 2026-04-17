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

# TTS character cap for the audio-only output. ElevenLabs bills per character.
_TTS_CHAR_CAP = 2500

# Narration cap for the VIDEO output. ~15 chars/sec speaking rate → ~40s.
# Target video length 30–60s per user spec.
_TTS_CHAR_CAP_VIDEO = 600

# Number of animated scenes in a video (Ken-Burns pan+zoom across N stills).
_VIDEO_SCENE_COUNT = 5

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


def _prep_narration(brief: str, cap: int = _TTS_CHAR_CAP) -> str:
    text = _markdown_to_speech(brief)
    if len(text) <= cap:
        return text
    # Trim at the last sentence boundary before the cap.
    head = text[:cap]
    cut = max(head.rfind(". "), head.rfind("? "), head.rfind("! "))
    return head[: cut + 1] if cut > 0 else head


# --- TTS --------------------------------------------------------------------

async def _synthesize_mp3(
    brief: str, dest: Path, run_id: str | None, voice_id: str,
    char_cap: int = _TTS_CHAR_CAP,
) -> None:
    narration = _prep_narration(brief, char_cap)
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


# --- Scene-image rendering --------------------------------------------------

_TITLE_W, _TITLE_H = 1280, 720
_BG = (15, 23, 42)       # slate-900
_ACCENT = (99, 102, 241) # indigo-500
_TEXT = (241, 245, 249)  # slate-100
_MUTED = (148, 163, 184) # slate-400

# A rotating palette of accent colours so consecutive scenes look distinct.
_SCENE_ACCENTS = [
    (99, 102, 241),   # indigo
    (16, 185, 129),   # emerald
    (244, 114, 182),  # pink
    (251, 146, 60),   # orange
    (14, 165, 233),   # sky
]


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
    """Single-card render (used by the audio-only preview — not the video)."""
    img = Image.new("RGB", (_TITLE_W, _TITLE_H), _BG)
    draw = ImageDraw.Draw(img)

    draw.rectangle([0, 0, 12, _TITLE_H], fill=_ACCENT)

    kicker_font = _pick_font(36)
    draw.text((80, 120), "BetterLabs Compass", font=kicker_font, fill=_MUTED)

    title_font = _pick_font(72)
    title = _first_heading_or_sentence(brief)
    for i, line in enumerate(_wrap(title, title_font, _TITLE_W - 160)[:3]):
        draw.text((80, 200 + i * 90), line, font=title_font, fill=_TEXT)

    foot_font = _pick_font(28)
    draw.text(
        (80, _TITLE_H - 80),
        "Narrated research brief · ElevenLabs",
        font=foot_font,
        fill=_MUTED,
    )
    img.save(out_png, "PNG", optimize=True)


def _split_scenes(brief: str, n: int) -> list[tuple[str, str]]:
    """Pull up to ``n`` (title, body) pairs from the brief for multi-scene video.

    Scene 1 is always the opening title; remaining scenes pull from headings
    first, then sentences.
    """
    text = _markdown_to_speech(brief)
    # Headings are the strongest structure signal; fall back to sentences.
    headings: list[str] = []
    for line in brief.splitlines():
        s = line.strip()
        if s.startswith("#"):
            headings.append(s.lstrip("#").strip())

    # Sentence tokenizer (no NLTK — naive split is fine for demo copy).
    sentences = [
        s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()
    ]

    title = _first_heading_or_sentence(brief)
    scenes: list[tuple[str, str]] = [
        (title, sentences[0][:140] if sentences else "Research brief"),
    ]

    # Prefer headings for subsequent scenes; top-up with sentences.
    pool: list[str] = list(dict.fromkeys([*headings[1:], *sentences[1:]]))
    for chunk in pool:
        if len(scenes) >= n:
            break
        short = chunk[:140]
        if short and all(short != s[1] for s in scenes):
            scenes.append((f"Scene {len(scenes) + 1}", short))

    # Pad with a closing scene if we still have fewer than n.
    while len(scenes) < n:
        scenes.append(("Summary", "Generated by BetterLabs Compass"))
    return scenes[:n]


def _render_scene_card(
    title: str, body: str, accent: tuple[int, int, int], out_png: Path
) -> None:
    img = Image.new("RGB", (_TITLE_W, _TITLE_H), _BG)
    draw = ImageDraw.Draw(img)

    # Accent bar with scene-specific colour.
    draw.rectangle([0, 0, 16, _TITLE_H], fill=accent)

    # Kicker (brand).
    kicker_font = _pick_font(32)
    draw.text((80, 80), "BetterLabs Compass", font=kicker_font, fill=_MUTED)

    # Title (wrapped, up to 3 lines).
    title_font = _pick_font(68)
    y = 160
    for line in _wrap(title, title_font, _TITLE_W - 160)[:3]:
        draw.text((80, y), line, font=title_font, fill=_TEXT)
        y += 84

    # Body (wrapped, up to 3 lines).
    body_font = _pick_font(32)
    y += 20
    for line in _wrap(body, body_font, _TITLE_W - 160)[:3]:
        draw.text((80, y), line, font=body_font, fill=(203, 213, 225))
        y += 44

    # Footer.
    foot_font = _pick_font(24)
    draw.text(
        (80, _TITLE_H - 60),
        "Narrated with ElevenLabs",
        font=foot_font,
        fill=_MUTED,
    )
    img.save(out_png, "PNG", optimize=True)


# --- ffmpeg: probe + animate + mux -----------------------------------------

_FPS = 30
_MIN_SCENE_SECONDS = 3.0   # floor so cuts don't feel jarring
_MAX_TOTAL_SECONDS = 60.0  # user spec: 30-60s
_MIN_TOTAL_SECONDS = 20.0  # audio-duration fallback floor


def _probe_mp3_duration(mp3: Path) -> float:
    """Read the audio duration by asking ffmpeg to parse the file.

    imageio-ffmpeg ships ffmpeg but not ffprobe; ffmpeg's stderr still
    prints `Duration: HH:MM:SS.xx` when invoked with `-i` and no output.
    Returns seconds; falls back to a conservative estimate on parse error.
    """
    ffmpeg = get_ffmpeg_exe()
    result = subprocess.run(
        [ffmpeg, "-i", str(mp3)],
        capture_output=True, text=True,
    )
    match = re.search(
        r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", result.stderr or ""
    )
    if not match:
        return 40.0
    h, m, s = int(match.group(1)), int(match.group(2)), float(match.group(3))
    return h * 3600 + m * 60 + s


def _render_scene_clip(png: Path, out_mp4: Path, duration: float) -> None:
    """Render one Ken-Burns clip: slow zoom-in on the PNG for ``duration`` s.

    Uses zoompan with ``d=1`` so the zoom state advances one step per INPUT
    frame (smooth, no reset). The input is `-loop 1 -framerate FPS -t D`
    which produces exactly D*FPS frames of the same image — each triggers
    one zoompan tick.
    """
    ffmpeg = get_ffmpeg_exe()
    frames = int(duration * _FPS)
    zoom_step = 0.15 / max(frames, 1)  # end zoom ≈ 1.15x
    # Upscale the source first so zoompan doesn't have to upsize a 1280x720
    # image (would look pixelated when zoomed beyond 1.0x).
    vf = (
        f"scale=2560:1440,"
        f"zoompan=z='min(zoom+{zoom_step:.6f},1.15)':"
        f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
        f"d=1:s={_TITLE_W}x{_TITLE_H}:fps={_FPS}"
    )
    cmd = [
        ffmpeg, "-y", "-loglevel", "error",
        "-loop", "1", "-framerate", str(_FPS), "-t", f"{duration:.3f}",
        "-i", str(png),
        "-vf", vf,
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-r", str(_FPS),
        str(out_mp4),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"ffmpeg scene render failed (rc={result.returncode}): "
            f"{result.stderr[-400:]}"
        )


def _concat_and_mux(
    clips: list[Path], mp3: Path, mp4: Path, tmp_dir: Path
) -> None:
    """Concatenate scene clips and mux the narration track."""
    ffmpeg = get_ffmpeg_exe()
    # concat demuxer wants a file listing inputs.
    list_path = tmp_dir / "concat.txt"
    list_path.write_text(
        "\n".join(f"file '{p.as_posix()}'" for p in clips) + "\n",
        encoding="utf-8",
    )
    cmd = [
        ffmpeg, "-y", "-loglevel", "error",
        "-f", "concat", "-safe", "0", "-i", str(list_path),
        "-i", str(mp3),
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "160k",
        "-shortest",
        "-movflags", "+faststart",
        str(mp4),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    try:
        list_path.unlink()
    except OSError:
        pass
    if result.returncode != 0:
        raise RuntimeError(
            f"ffmpeg concat/mux failed (rc={result.returncode}): "
            f"{result.stderr[-500:]}"
        )


def _render_animated_video(
    scene_pngs: list[Path], mp3: Path, mp4: Path,
    narration_seconds: float,
) -> None:
    """Build the final animated MP4.

    1. Compute per-scene duration so total stays within 30–60s (clamped to
       narration length so audio isn't cut mid-sentence).
    2. Render a Ken-Burns clip per scene.
    3. Concat clips + mux narration.
    """
    n = len(scene_pngs)
    total = max(_MIN_TOTAL_SECONDS, min(_MAX_TOTAL_SECONDS, narration_seconds))
    per_scene = max(_MIN_SCENE_SECONDS, total / n)

    clip_paths: list[Path] = []
    for i, png in enumerate(scene_pngs):
        clip = png.with_suffix(".clip.mp4")
        _render_scene_clip(png, clip, per_scene)
        clip_paths.append(clip)

    try:
        _concat_and_mux(clip_paths, mp3, mp4, tmp_dir=mp4.parent)
    finally:
        for clip in clip_paths:
            try:
                clip.unlink()
            except OSError:
                pass


# --- Public API -------------------------------------------------------------

async def _run_audio(run_id: str, artifact_id: str, brief: str) -> Path:
    dest = get_artifact_path(run_id, artifact_id, "mp3")
    await _synthesize_mp3(brief, dest, run_id, _DEFAULT_VOICE_ID)
    return dest


async def _run_video(run_id: str, artifact_id: str, brief: str) -> Path:
    """Build a 30–60s narrated explainer video from the brief.

    Pipeline:
      1. ElevenLabs TTS → MP3 narration (char-capped to ~40s of speech).
      2. Split brief into N scenes; render each as a Pillow PNG title card.
      3. ffmpeg filter_complex applies a Ken-Burns zoom to each still and
         concatenates them, then muxes the narration audio with `-shortest`.

    Intermediates are prefixed `{artifact_id}__…` so the artifact route's
    `{id}.*` glob never picks them up over the final MP4.
    """
    mp4_path = get_artifact_path(run_id, artifact_id, "mp4")
    run_dir = mp4_path.parent
    mp3_path = run_dir / f"{artifact_id}__narration.mp3"
    scene_paths: list[Path] = [
        run_dir / f"{artifact_id}__scene_{i}.png"
        for i in range(_VIDEO_SCENE_COUNT)
    ]

    # 1) Synthesize narration (shorter cap for video → hits ~30–60s target).
    await _synthesize_mp3(
        brief, mp3_path, run_id, _DEFAULT_VOICE_ID,
        char_cap=_TTS_CHAR_CAP_VIDEO,
    )

    # 2) Split brief + render each scene image.
    scenes = _split_scenes(brief, _VIDEO_SCENE_COUNT)
    append_event(
        run_id, "elevenlabs", "report.render",
        f"Rendering {_VIDEO_SCENE_COUNT} scene cards",
        data={"size": f"{_TITLE_W}x{_TITLE_H}", "scenes": len(scenes)},
    )

    def _render_all() -> None:
        for i, ((title, body), path) in enumerate(zip(scenes, scene_paths)):
            accent = _SCENE_ACCENTS[i % len(_SCENE_ACCENTS)]
            _render_scene_card(title, body, accent, path)

    await asyncio.to_thread(_render_all)

    # 3) Probe narration duration, then build Ken-Burns MP4 clamped to 30–60s.
    duration = await asyncio.to_thread(_probe_mp3_duration, mp3_path)
    append_event(
        run_id, "elevenlabs", "tool.call",
        f"ffmpeg Ken-Burns render ({_VIDEO_SCENE_COUNT} scenes, audio={duration:.1f}s)",
        data={
            "mp3": mp3_path.name,
            "mp4": mp4_path.name,
            "audio_seconds": duration,
            "scene_count": _VIDEO_SCENE_COUNT,
        },
    )
    await asyncio.to_thread(
        _render_animated_video, scene_paths, mp3_path, mp4_path, duration
    )

    # Clean up intermediates — the served artifact is the MP4 only.
    for tmp in (mp3_path, *scene_paths):
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
