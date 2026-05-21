"""Subtitle / karaoke renderer + LRC/SRT importer & exporter."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable, Sequence

import cv2
import numpy as np

from lyrics_generator import LyricLine, LyricsBundle, LyricWord
from spectrum_engine import palette_at, hex_to_bgr


# ---------------------------------------------------------------------------
# Subtitle drawing
# ---------------------------------------------------------------------------


def _put_text_centered(
    img: np.ndarray,
    text: str,
    *,
    y: int,
    font_scale: float,
    color: tuple[int, int, int],
    thickness: int,
    outline: bool = True,
) -> None:
    if not text:
        return
    font = cv2.FONT_HERSHEY_DUPLEX
    (tw, th), _ = cv2.getTextSize(text, font, font_scale, thickness)
    x = (img.shape[1] - tw) // 2
    if outline:
        cv2.putText(img, text, (x, y), font, font_scale, (0, 0, 0), thickness + 6, cv2.LINE_AA)
    cv2.putText(img, text, (x, y), font, font_scale, color, thickness, cv2.LINE_AA)


def _karaoke_progress(words: Sequence[LyricWord], t: float) -> tuple[int, float]:
    """Return ``(current_word_idx, progress_in_word)``."""
    if not words:
        return 0, 0.0
    for i, w in enumerate(words):
        if t < w.end:
            denom = max(w.duration, 1e-3)
            return i, max(0.0, min(1.0, (t - w.start) / denom))
    return len(words) - 1, 1.0


def render_subtitle_layer(
    frame: np.ndarray,
    bundle: LyricsBundle,
    t: float,
    *,
    font_scale: float = 1.6,
    base_color: str = "#ffffff",
    highlight_color: str = "#00e5ff",
    y_ratio: float = 0.5,
    karaoke: bool = True,
    glow: bool = True,
) -> np.ndarray:
    h, w = frame.shape[:2]
    active = next((ln for ln in bundle.lines if ln.start <= t <= ln.end), None)
    if active is None:
        # show upcoming line as a faded teaser
        upcoming = next((ln for ln in bundle.lines if ln.start - t < 0.6 and ln.start > t), None)
        if upcoming is None:
            return frame
        active = upcoming
        teaser = True
    else:
        teaser = False

    y = int(h * y_ratio)
    base = hex_to_bgr(base_color)
    hi = hex_to_bgr(highlight_color)
    thickness = 3

    overlay = frame.copy()

    if karaoke and active.words:
        idx, prog = _karaoke_progress(active.words, t)
        # Build text: words[:idx] fully highlighted, words[idx] gradient, rest base
        # Render whole line in base color first
        full_text = active.text
        _put_text_centered(overlay, full_text, y=y, font_scale=font_scale, color=base, thickness=thickness)
        # Then overlay the highlighted portion using a mask:
        cumulative = " ".join(w.text for w in active.words[:idx])
        if cumulative:
            font = cv2.FONT_HERSHEY_DUPLEX
            (full_tw, _), _ = cv2.getTextSize(full_text, font, font_scale, thickness)
            (cur_tw, _), _ = cv2.getTextSize(cumulative + (" " if idx > 0 else ""), font, font_scale, thickness)
            (word_tw, _), _ = cv2.getTextSize(active.words[idx].text, font, font_scale, thickness)
            x_start = (w - full_tw) // 2
            x_hi_end = x_start + cur_tw + int(word_tw * prog)
            # Draw highlight by drawing the full text with a stencil to the left of x_hi_end
            stencil = np.zeros_like(frame)
            _put_text_centered(stencil, full_text, y=y, font_scale=font_scale, color=hi, thickness=thickness, outline=False)
            mask = np.zeros((h, w), dtype=np.uint8)
            mask[:, : max(0, x_hi_end)] = 255
            stencil = cv2.bitwise_and(stencil, stencil, mask=mask)
            overlay = cv2.add(overlay, stencil)
        else:
            # Highlight first word as it begins
            font = cv2.FONT_HERSHEY_DUPLEX
            (full_tw, _), _ = cv2.getTextSize(full_text, font, font_scale, thickness)
            (word_tw, _), _ = cv2.getTextSize(active.words[0].text, font, font_scale, thickness)
            x_start = (w - full_tw) // 2
            x_hi_end = x_start + int(word_tw * prog)
            stencil = np.zeros_like(frame)
            _put_text_centered(stencil, full_text, y=y, font_scale=font_scale, color=hi, thickness=thickness, outline=False)
            mask = np.zeros((h, w), dtype=np.uint8)
            mask[:, : max(0, x_hi_end)] = 255
            stencil = cv2.bitwise_and(stencil, stencil, mask=mask)
            overlay = cv2.add(overlay, stencil)
    else:
        color = base
        if teaser:
            color = tuple(int(c * 0.5) for c in base)  # type: ignore[assignment]
        _put_text_centered(overlay, active.text, y=y, font_scale=font_scale, color=color, thickness=thickness)

    if glow:
        glow_layer = cv2.GaussianBlur(overlay, (0, 0), sigmaX=8, sigmaY=8)
        overlay = cv2.addWeighted(overlay, 1.0, glow_layer, 0.35, 0)
    return overlay


# ---------------------------------------------------------------------------
# LRC / SRT import + export
# ---------------------------------------------------------------------------


_LRC_RE = re.compile(r"\[(\d+):(\d+(?:\.\d+)?)\](.*)")
_SRT_TIME = re.compile(r"(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)")


def _srt_time_to_sec(h: str, m: str, s: str, ms: str) -> float:
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0


def import_lrc(text: str) -> list[LyricLine]:
    raw_lines: list[tuple[float, str]] = []
    for line in text.splitlines():
        match = _LRC_RE.match(line.strip())
        if not match:
            continue
        minute, second, content = match.groups()
        t = int(minute) * 60 + float(second)
        if content.strip():
            raw_lines.append((t, content.strip()))
    raw_lines.sort(key=lambda x: x[0])
    lines: list[LyricLine] = []
    for i, (start, text) in enumerate(raw_lines):
        end = raw_lines[i + 1][0] if i + 1 < len(raw_lines) else start + 4.0
        words_text = text.split()
        per_word = max(0.1, (end - start) / max(1, len(words_text)))
        cursor = start
        words: list[LyricWord] = []
        for w in words_text:
            words.append(LyricWord(text=w, start=cursor, end=cursor + per_word))
            cursor += per_word
        lines.append(LyricLine(text=text, start=start, end=end, words=words))
    return lines


def import_srt(text: str) -> list[LyricLine]:
    blocks = re.split(r"\n\s*\n", text.strip())
    lines: list[LyricLine] = []
    for block in blocks:
        block_lines = [b for b in block.splitlines() if b.strip()]
        if len(block_lines) < 2:
            continue
        time_line = block_lines[1] if block_lines[0].isdigit() else block_lines[0]
        match = _SRT_TIME.search(time_line)
        if not match:
            continue
        groups = match.groups()
        start = _srt_time_to_sec(*groups[:4])
        end = _srt_time_to_sec(*groups[4:])
        text_part = " ".join(block_lines[2:] if block_lines[0].isdigit() else block_lines[1:])
        words_text = text_part.split()
        per_word = max(0.1, (end - start) / max(1, len(words_text)))
        cursor = start
        words: list[LyricWord] = []
        for w in words_text:
            words.append(LyricWord(text=w, start=cursor, end=cursor + per_word))
            cursor += per_word
        lines.append(LyricLine(text=text_part, start=start, end=end, words=words))
    return lines


def export_srt(lines: Iterable[LyricLine]) -> str:
    def fmt(t: float) -> str:
        ms = int(round((t - int(t)) * 1000))
        if ms >= 1000:
            ms = 999
        h = int(t) // 3600
        m = (int(t) % 3600) // 60
        s = int(t) % 60
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    out = []
    for i, line in enumerate(lines, start=1):
        out.append(str(i))
        out.append(f"{fmt(line.start)} --> {fmt(line.end)}")
        out.append(line.text)
        out.append("")
    return "\n".join(out)


def export_lrc(lines: Iterable[LyricLine]) -> str:
    def fmt(t: float) -> str:
        m = int(t) // 60
        s = t - m * 60
        return f"[{m:02d}:{s:05.2f}]"

    return "\n".join(f"{fmt(line.start)}{line.text}" for line in lines)


def write_subtitles(bundle: LyricsBundle, output_dir: Path, *, stem: str) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    srt_path = output_dir / f"{stem}.srt"
    lrc_path = output_dir / f"{stem}.lrc"
    srt_path.write_text(export_srt(bundle.lines), encoding="utf-8")
    lrc_path.write_text(export_lrc(bundle.lines), encoding="utf-8")
    return {"srt": srt_path, "lrc": lrc_path}
