"""Video renderer.

Glues the spectrum engine, subtitle engine and audio together. The renderer
streams frames into :mod:`export_engine` so we never have to materialise the
whole video in memory.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterator

import cv2
import numpy as np

from audio_analyzer import MusicAnalysis
from lyrics_generator import LyricsBundle
from spectrum_engine import SpectrumEngine, SpectrumStyle
from subtitle_engine import render_subtitle_layer
from app.core.logger import get_logger

log = get_logger(__name__)


@dataclass
class RenderSettings:
    width: int = 1920
    height: int = 1080
    fps: int = 30
    preview_scale: float = 1.0
    subtitle_y_ratio: float = 0.55
    subtitle_color: str = "#ffffff"
    subtitle_highlight: str = "#00e5ff"
    subtitle_font_scale: float = 1.6
    karaoke: bool = True
    show_subtitles: bool = True
    background_path: str | None = None


@dataclass
class RenderJob:
    analysis: MusicAnalysis
    lyrics: LyricsBundle
    spectrum_style: SpectrumStyle = field(default_factory=SpectrumStyle)
    settings: RenderSettings = field(default_factory=RenderSettings)

    @property
    def duration(self) -> float:
        return max(self.analysis.duration, 1.0)

    @property
    def frame_count(self) -> int:
        return max(1, int(self.duration * self.settings.fps))


# ---------------------------------------------------------------------------
# Frame generator
# ---------------------------------------------------------------------------


def iter_frames(
    job: RenderJob,
    *,
    progress: Callable[[int, int], None] | None = None,
    start: float = 0.0,
    end: float | None = None,
) -> Iterator[np.ndarray]:
    width, height = job.settings.width, job.settings.height
    engine = SpectrumEngine(job.spectrum_style, width=width, height=height)

    bg_video: cv2.VideoCapture | None = None
    if job.settings.background_path:
        path = job.settings.background_path
        try:
            bg_video = cv2.VideoCapture(path)
            if not bg_video.isOpened():
                bg_video = None
        except Exception:
            bg_video = None

    total = job.frame_count
    fps = job.settings.fps
    end = end if end is not None else job.duration

    start_frame = int(start * fps)
    end_frame = min(total, int(end * fps))

    for fidx in range(start_frame, end_frame):
        t = fidx / fps
        frame = engine.render(t, job.analysis)
        if bg_video is not None:
            ret, bg_frame = bg_video.read()
            if not ret:
                bg_video.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret, bg_frame = bg_video.read()
            if ret:
                bg_frame = cv2.resize(bg_frame, (width, height))
                frame = cv2.addWeighted(bg_frame, 0.45, frame, 0.85, 0)

        if job.settings.show_subtitles and job.lyrics.lines:
            frame = render_subtitle_layer(
                frame,
                job.lyrics,
                t,
                font_scale=job.settings.subtitle_font_scale,
                base_color=job.settings.subtitle_color,
                highlight_color=job.settings.subtitle_highlight,
                y_ratio=job.settings.subtitle_y_ratio,
                karaoke=job.settings.karaoke,
            )

        if progress is not None and fidx % 5 == 0:
            progress(fidx + 1, end_frame)
        yield frame

    if bg_video is not None:
        bg_video.release()


# ---------------------------------------------------------------------------
# Preview helper
# ---------------------------------------------------------------------------


def render_preview_frame(job: RenderJob, t: float) -> np.ndarray:
    """Render a single frame — used by the live preview widget."""
    engine = SpectrumEngine(job.spectrum_style, job.settings.width, job.settings.height)
    frame = engine.render(t, job.analysis)
    if job.settings.show_subtitles and job.lyrics.lines:
        frame = render_subtitle_layer(
            frame,
            job.lyrics,
            t,
            font_scale=job.settings.subtitle_font_scale,
            base_color=job.settings.subtitle_color,
            highlight_color=job.settings.subtitle_highlight,
            y_ratio=job.settings.subtitle_y_ratio,
            karaoke=job.settings.karaoke,
        )
    if job.settings.preview_scale != 1.0:
        new_w = int(job.settings.width * job.settings.preview_scale)
        new_h = int(job.settings.height * job.settings.preview_scale)
        frame = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)
    return frame


def render_thumbnail(job: RenderJob, *, at_ratio: float = 0.25) -> np.ndarray:
    """Render a thumbnail frame, ideally during a chorus / energetic peak."""
    t = max(0.0, min(job.duration - 0.1, job.duration * at_ratio))
    # Try to snap to an energetic moment if we have onsets
    onset = job.analysis.onset_env
    if onset.size > 0:
        hop = 512
        sr = job.analysis.sample_rate
        idx = int(np.argmax(onset))
        t = max(0.0, min(job.duration - 0.1, idx * hop / sr))
    return render_preview_frame(job, t)
