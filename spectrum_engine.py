"""Spectrum visualizer.

The engine produces an ``RGB`` numpy frame for a given time-stamp. Supported
modes:

* ``bar``       – classic bottom bars
* ``mirror``    – mirrored top + bottom bars
* ``wave``      – smooth waveform line
* ``circular``  – radial bars around a centre
* ``rgb``       – chromatic-split bars (R/G/B offset)
* ``neon``      – glowing neon bars with halo
* ``particles`` – bass / beat reactive particles overlay
* ``dual``      – left bars + right circular

The renderer accepts a ``SpectrumStyle`` dataclass — built either by the user
in the UI or auto-generated from a :class:`MusicAnalysis`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

import cv2
import numpy as np

from audio_analyzer import MusicAnalysis, beat_strength_at, spectrum_bands


# ---------------------------------------------------------------------------
# Style dataclass
# ---------------------------------------------------------------------------


@dataclass
class SpectrumStyle:
    mode: str = "bar"
    bands: int = 64
    sensitivity: float = 1.0
    smoothing: float = 0.8
    glow: bool = True
    motion_blur: float = 0.15
    palette: list[str] = field(default_factory=lambda: ["#00e5ff", "#7c4dff", "#ff4081"])
    background: list[str] = field(default_factory=lambda: ["#0a0a1a", "#1a0a2e"])
    beat_flash: float = 0.1
    rgb_split: float = 0.0
    film_grain: float = 0.05
    vignette: float = 0.3
    particle_count: int = 60


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def hex_to_bgr(color: str) -> tuple[int, int, int]:
    c = color.lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    r = int(c[0:2], 16)
    g = int(c[2:4], 16)
    b = int(c[4:6], 16)
    return (b, g, r)


def lerp_color(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    t = max(0.0, min(1.0, t))
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))  # type: ignore[return-value]


def palette_at(palette: Sequence[str], t: float) -> tuple[int, int, int]:
    if not palette:
        return (255, 255, 255)
    if len(palette) == 1:
        return hex_to_bgr(palette[0])
    t = max(0.0, min(1.0, t))
    scaled = t * (len(palette) - 1)
    i = int(scaled)
    frac = scaled - i
    if i >= len(palette) - 1:
        return hex_to_bgr(palette[-1])
    return lerp_color(hex_to_bgr(palette[i]), hex_to_bgr(palette[i + 1]), frac)


def make_gradient_background(width: int, height: int, colors: Sequence[str], angle: float = 90.0) -> np.ndarray:
    if not colors:
        return np.zeros((height, width, 3), dtype=np.uint8)
    n = len(colors)
    grad = np.linspace(0, 1, height, dtype=np.float32)
    rows = []
    for t in grad:
        rows.append(palette_at(colors, float(t)))
    column = np.array(rows, dtype=np.uint8)
    img = np.repeat(column[:, None, :], width, axis=1)
    if angle == 0:
        img = cv2.transpose(img)
    return img


def vignette(img: np.ndarray, strength: float) -> np.ndarray:
    if strength <= 0:
        return img
    h, w = img.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    cy, cx = h / 2.0, w / 2.0
    d = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    d /= d.max()
    mask = np.clip(1.0 - d * strength * 1.5, 0.0, 1.0)[:, :, None]
    return (img.astype(np.float32) * mask).astype(np.uint8)


def add_film_grain(img: np.ndarray, strength: float) -> np.ndarray:
    if strength <= 0:
        return img
    h, w = img.shape[:2]
    noise = np.random.randn(h, w, 1).astype(np.float32) * (255.0 * strength)
    out = img.astype(np.float32) + noise
    return np.clip(out, 0, 255).astype(np.uint8)


def rgb_split(img: np.ndarray, offset: int) -> np.ndarray:
    if offset <= 0:
        return img
    b, g, r = cv2.split(img)
    M_r = np.float32([[1, 0, offset], [0, 1, 0]])
    M_b = np.float32([[1, 0, -offset], [0, 1, 0]])
    r = cv2.warpAffine(r, M_r, (img.shape[1], img.shape[0]))
    b = cv2.warpAffine(b, M_b, (img.shape[1], img.shape[0]))
    return cv2.merge([b, g, r])


def beat_flash_layer(width: int, height: int, intensity: float, color: tuple[int, int, int]) -> np.ndarray:
    if intensity <= 0:
        return np.zeros((height, width, 3), dtype=np.uint8)
    layer = np.zeros((height, width, 3), dtype=np.uint8)
    layer[:] = color
    return (layer.astype(np.float32) * intensity).astype(np.uint8)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class SpectrumEngine:
    """Stateful per-render visualizer.

    A single instance is reused while rendering one project so the smoothing
    buffer & particle field stay consistent across frames.
    """

    def __init__(self, style: SpectrumStyle, width: int, height: int) -> None:
        self.style = style
        self.width = width
        self.height = height
        self._smoothed = np.zeros(style.bands, dtype=np.float32)
        rng = np.random.default_rng(seed=42)
        self._particles = rng.random((style.particle_count, 4)).astype(np.float32)
        # Columns: x, y, size, hue
        self._bg_cache: np.ndarray | None = None

    # ----- factory ------------------------------------------------------
    @classmethod
    def from_analysis(
        cls,
        analysis: MusicAnalysis,
        width: int,
        height: int,
        *,
        mode: str | None = None,
        bands: int = 64,
    ) -> "SpectrumEngine":
        style = SpectrumStyle(
            mode=mode or _auto_mode(analysis),
            bands=bands,
            palette=list(analysis.suggested_palette),
            background=_auto_background(analysis),
            sensitivity=_auto_sensitivity(analysis),
            beat_flash=0.18 if analysis.mood == "energetic" else 0.08,
            rgb_split=2.0 if analysis.mood in ("energetic", "dark") else 0.0,
            film_grain=0.04 if analysis.mood in ("dark", "calm") else 0.02,
            vignette=0.35,
            particle_count=80 if analysis.mood == "energetic" else 50,
        )
        return cls(style=style, width=width, height=height)

    # ----- per-frame ----------------------------------------------------
    def render(self, t: float, analysis: MusicAnalysis) -> np.ndarray:
        bg = self._background()
        bands = spectrum_bands(
            analysis.samples,
            analysis.sample_rate or 44100,
            t,
            fft_size=2048,
            bands=self.style.bands,
            log_scale=True,
        )
        bands *= self.style.sensitivity
        # Smoothing
        a = self.style.smoothing
        self._smoothed = a * self._smoothed + (1 - a) * bands

        beat = beat_strength_at(t, analysis.beat_times, window=0.18)

        frame = bg.copy()
        mode = self.style.mode
        if mode == "bar":
            frame = self._draw_bars(frame, self._smoothed)
        elif mode == "mirror":
            frame = self._draw_bars(frame, self._smoothed, mirror=True)
        elif mode == "wave":
            frame = self._draw_wave(frame, self._smoothed)
        elif mode == "circular":
            frame = self._draw_circular(frame, self._smoothed, beat)
        elif mode == "rgb":
            frame = self._draw_bars(frame, self._smoothed)
            frame = rgb_split(frame, offset=int(4 + 8 * beat))
        elif mode == "neon":
            frame = self._draw_bars(frame, self._smoothed, glow_boost=1.6)
        elif mode == "dual":
            frame = self._draw_bars(frame, self._smoothed, half="left")
            frame = self._draw_circular(frame, self._smoothed, beat, radius_ratio=0.22)
        else:  # particles + bars fallback
            frame = self._draw_bars(frame, self._smoothed)

        # particles always overlaid (subtle if disabled by count=0)
        if self.style.particle_count > 0:
            frame = self._draw_particles(frame, beat)

        # beat flash & effects
        if self.style.beat_flash > 0:
            flash = beat_flash_layer(self.width, self.height, self.style.beat_flash * beat, palette_at(self.style.palette, 0.0))
            frame = cv2.add(frame, flash)
        if self.style.rgb_split > 0 and mode != "rgb":
            frame = rgb_split(frame, offset=int(self.style.rgb_split + beat * 3))
        if self.style.vignette > 0:
            frame = vignette(frame, self.style.vignette)
        if self.style.film_grain > 0:
            frame = add_film_grain(frame, self.style.film_grain)
        return frame

    # ----- drawing primitives ------------------------------------------
    def _background(self) -> np.ndarray:
        if self._bg_cache is None:
            self._bg_cache = make_gradient_background(self.width, self.height, self.style.background)
        return self._bg_cache.copy()

    def _draw_bars(
        self,
        frame: np.ndarray,
        bands: np.ndarray,
        *,
        mirror: bool = False,
        half: str | None = None,
        glow_boost: float = 1.0,
    ) -> np.ndarray:
        h, w = frame.shape[:2]
        usable_w = w if half is None else w // 2
        offset_x = 0 if half != "right" else w // 2
        bar_w = max(2, usable_w // (len(bands) + 1))
        gap = max(1, bar_w // 4)
        baseline = int(h * 0.85)
        max_height = int(h * 0.65)

        for i, v in enumerate(bands):
            x = offset_x + (i + 1) * (bar_w + gap) - bar_w
            bar_h = int(max_height * float(v))
            color = palette_at(self.style.palette, i / max(1, len(bands) - 1))
            top = baseline - bar_h
            cv2.rectangle(frame, (x, top), (x + bar_w, baseline), color, -1)
            if mirror:
                cv2.rectangle(frame, (x, baseline + 4), (x + bar_w, baseline + 4 + bar_h), color, -1)
            if self.style.glow:
                # cheap glow by alpha-blending a blurred copy
                glow = np.zeros_like(frame)
                cv2.rectangle(glow, (x - 2, top - 2), (x + bar_w + 2, baseline + 2), color, -1)
                glow = cv2.GaussianBlur(glow, (0, 0), sigmaX=8 * glow_boost, sigmaY=8 * glow_boost)
                frame = cv2.addWeighted(frame, 1.0, glow, 0.6, 0)
        return frame

    def _draw_wave(self, frame: np.ndarray, bands: np.ndarray) -> np.ndarray:
        h, w = frame.shape[:2]
        center_y = int(h * 0.6)
        amp = int(h * 0.25)
        pts: list[tuple[int, int]] = []
        for i, v in enumerate(bands):
            x = int(i * (w / max(1, len(bands) - 1)))
            y = center_y - int(amp * (float(v) * 2 - 0.0) * (1 if i % 2 == 0 else -1))
            pts.append((x, y))
        if len(pts) >= 2:
            color = palette_at(self.style.palette, 0.5)
            cv2.polylines(frame, [np.array(pts, dtype=np.int32)], False, color, thickness=3, lineType=cv2.LINE_AA)
            if self.style.glow:
                glow = np.zeros_like(frame)
                cv2.polylines(glow, [np.array(pts, dtype=np.int32)], False, color, thickness=10, lineType=cv2.LINE_AA)
                glow = cv2.GaussianBlur(glow, (0, 0), sigmaX=14, sigmaY=14)
                frame = cv2.addWeighted(frame, 1.0, glow, 0.6, 0)
        return frame

    def _draw_circular(
        self,
        frame: np.ndarray,
        bands: np.ndarray,
        beat: float,
        radius_ratio: float = 0.25,
    ) -> np.ndarray:
        h, w = frame.shape[:2]
        cx, cy = w // 2, h // 2
        base_r = int(min(w, h) * radius_ratio * (1.0 + 0.05 * beat))
        max_len = int(min(w, h) * 0.18)
        for i, v in enumerate(bands):
            angle = 2 * np.pi * i / len(bands)
            r1 = base_r
            r2 = base_r + int(max_len * float(v))
            x1 = int(cx + np.cos(angle) * r1)
            y1 = int(cy + np.sin(angle) * r1)
            x2 = int(cx + np.cos(angle) * r2)
            y2 = int(cy + np.sin(angle) * r2)
            color = palette_at(self.style.palette, i / max(1, len(bands) - 1))
            cv2.line(frame, (x1, y1), (x2, y2), color, thickness=4, lineType=cv2.LINE_AA)
        if self.style.glow:
            glow = cv2.GaussianBlur(frame, (0, 0), sigmaX=12, sigmaY=12)
            frame = cv2.addWeighted(frame, 1.0, glow, 0.35, 0)
        return frame

    def _draw_particles(self, frame: np.ndarray, beat: float) -> np.ndarray:
        h, w = frame.shape[:2]
        intensity = 0.5 + 0.5 * beat
        for i in range(self._particles.shape[0]):
            px, py, size, hue = self._particles[i]
            # Drift upward, wrap around
            py = (py - 0.002 * (0.5 + beat)) % 1.0
            self._particles[i, 1] = py
            x = int(px * w)
            y = int(py * h)
            radius = int(2 + size * 6)
            color = palette_at(self.style.palette, float(hue))
            color = tuple(int(c * intensity) for c in color)  # type: ignore[assignment]
            cv2.circle(frame, (x, y), radius, color, -1, lineType=cv2.LINE_AA)
        if self.style.glow:
            glow = cv2.GaussianBlur(frame, (0, 0), sigmaX=5, sigmaY=5)
            frame = cv2.addWeighted(frame, 1.0, glow, 0.25, 0)
        return frame


# ---------------------------------------------------------------------------
# Heuristics
# ---------------------------------------------------------------------------


def _auto_mode(analysis: MusicAnalysis) -> str:
    if analysis.mood == "energetic":
        return "neon"
    if analysis.mood == "dreamy":
        return "wave"
    if analysis.mood == "dark":
        return "circular"
    if analysis.mood == "calm":
        return "mirror"
    return "bar"


def _auto_sensitivity(analysis: MusicAnalysis) -> float:
    if analysis.energy > 0.6:
        return 1.05
    if analysis.energy < 0.25:
        return 1.4
    return 1.2


def _auto_background(analysis: MusicAnalysis) -> list[str]:
    table = {
        "energetic": ["#170028", "#3a0ca3", "#560bad"],
        "dreamy": ["#1a0f3d", "#3d246c", "#7a3ba5"],
        "dark": ["#05050f", "#100a1a", "#1b0a2a"],
        "calm": ["#0a1a2e", "#16213e", "#1b3a4b"],
        "balanced": ["#0a0a1a", "#1a0a2e", "#0a1a2e"],
    }
    return table.get(analysis.mood, table["balanced"])
