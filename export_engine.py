"""Export pipeline.

Frames are piped directly into FFmpeg over stdin (raw BGR -> H264) and the
audio track from the original song is muxed in via a second input. We rely on
``imageio_ffmpeg`` so users don't need to install FFmpeg manually.
"""
from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import cv2
import numpy as np

from renderer import RenderJob, iter_frames
from app.core.logger import get_logger

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# FFmpeg discovery
# ---------------------------------------------------------------------------


def find_ffmpeg() -> str:
    binary = shutil.which("ffmpeg")
    if binary:
        return binary
    try:
        import imageio_ffmpeg  # type: ignore

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as exc:  # pragma: no cover - depends on env
        raise RuntimeError("FFmpeg tidak ditemukan. Install ffmpeg sistem atau imageio-ffmpeg.") from exc


def detect_gpu_encoder(preferred: str = "auto") -> str:
    """Return an FFmpeg video codec name. ``preferred`` may be auto/nvidia/amd/intel/cpu."""
    if preferred == "cpu":
        return "libx264"
    candidates = {
        "nvidia": "h264_nvenc",
        "amd": "h264_amf",
        "intel": "h264_qsv",
    }
    if preferred in candidates:
        return candidates[preferred]
    if preferred == "auto":
        try:
            ffmpeg = find_ffmpeg()
            out = subprocess.run(
                [ffmpeg, "-hide_banner", "-encoders"], check=False, capture_output=True, text=True
            ).stdout
            for label, name in (("h264_nvenc", "h264_nvenc"), ("h264_amf", "h264_amf"), ("h264_qsv", "h264_qsv")):
                if name in out:
                    return label
        except Exception:
            pass
    return "libx264"


# ---------------------------------------------------------------------------
# Export config
# ---------------------------------------------------------------------------


@dataclass
class ExportSettings:
    output_path: Path
    codec: str = "libx264"
    crf: int = 18
    preset: str = "medium"
    audio_bitrate: str = "192k"
    pixel_format: str = "yuv420p"
    extra_args: list[str] = field(default_factory=list)
    gpu: str = "auto"
    resolution: tuple[int, int] | None = None


# ---------------------------------------------------------------------------
# Exporter
# ---------------------------------------------------------------------------


class VideoExporter:
    """Stream rendered frames through FFmpeg to disk."""

    def __init__(self, settings: ExportSettings) -> None:
        self.settings = settings
        self.ffmpeg_path = find_ffmpeg()

    def export(
        self,
        job: RenderJob,
        *,
        progress: Callable[[int, int], None] | None = None,
        start: float = 0.0,
        end: float | None = None,
    ) -> Path:
        out = Path(self.settings.output_path)
        out.parent.mkdir(parents=True, exist_ok=True)

        width = job.settings.width
        height = job.settings.height
        if self.settings.resolution is not None:
            width, height = self.settings.resolution
        fps = job.settings.fps
        codec = self.settings.codec
        if codec == "auto":
            codec = detect_gpu_encoder(self.settings.gpu)

        cmd: list[str] = [
            self.ffmpeg_path, "-y",
            "-loglevel", "error",
            "-f", "rawvideo",
            "-pix_fmt", "bgr24",
            "-s", f"{job.settings.width}x{job.settings.height}",
            "-r", str(fps),
            "-i", "pipe:0",
        ]
        # Audio input (optional)
        audio_in = job.analysis.path
        has_audio = audio_in and Path(audio_in).exists()
        if has_audio:
            cmd += ["-i", str(audio_in)]

        # Output args
        if (width, height) != (job.settings.width, job.settings.height):
            cmd += ["-vf", f"scale={width}:{height}"]
        cmd += [
            "-c:v", codec,
            "-pix_fmt", self.settings.pixel_format,
        ]
        if codec == "libx264":
            cmd += ["-crf", str(self.settings.crf), "-preset", self.settings.preset]
        if has_audio:
            cmd += ["-c:a", "aac", "-b:a", self.settings.audio_bitrate, "-shortest"]
        cmd += list(self.settings.extra_args)
        cmd += [str(out)]

        log.info("FFmpeg cmd: %s", " ".join(cmd))
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        assert proc.stdin is not None

        total_frames = job.frame_count
        try:
            for i, frame in enumerate(iter_frames(job, progress=None, start=start, end=end)):
                # Always feed at native res; FFmpeg handles downscale via -vf.
                if frame.shape[1] != job.settings.width or frame.shape[0] != job.settings.height:
                    frame = cv2.resize(frame, (job.settings.width, job.settings.height))
                proc.stdin.write(frame.tobytes())
                if progress is not None and i % 5 == 0:
                    progress(i + 1, total_frames)
            proc.stdin.close()
            stderr = proc.stderr.read() if proc.stderr else b""
            ret = proc.wait()
            if ret != 0:
                log.error("FFmpeg failed: %s", stderr.decode("utf-8", errors="ignore"))
                raise RuntimeError(stderr.decode("utf-8", errors="ignore") or f"ffmpeg exit {ret}")
        except BrokenPipeError as exc:
            stderr = proc.stderr.read() if proc.stderr else b""
            log.error("FFmpeg pipe broken: %s", stderr.decode("utf-8", errors="ignore"))
            raise RuntimeError(stderr.decode("utf-8", errors="ignore") or "ffmpeg pipe error") from exc

        if progress is not None:
            progress(total_frames, total_frames)
        return out


# ---------------------------------------------------------------------------
# High-level helpers
# ---------------------------------------------------------------------------


def render_thumbnail_image(image: np.ndarray, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), image)
    return path


RESOLUTIONS = {
    "720p":  (1280, 720),
    "1080p": (1920, 1080),
    "1440p": (2560, 1440),
    "4k":    (3840, 2160),
}


def resolution_pair(name: str) -> tuple[int, int]:
    return RESOLUTIONS.get(name.lower(), (1920, 1080))
