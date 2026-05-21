"""Lyric / metadata generator powered by Groq.

The generator takes a ``MusicAnalysis`` and produces structured lyric data:

* lines (verse + chorus + hook)
* word-level timing (auto-distributed across the song)
* metadata (title, hashtags, description, thumbnail text)

Timings are derived from beat positions when available, otherwise the song
duration is split evenly.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import numpy as np

from ai_engine import AIEngine
from audio_analyzer import MusicAnalysis
from app.core.logger import get_logger

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class LyricWord:
    text: str
    start: float
    end: float

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)


@dataclass
class LyricLine:
    text: str
    start: float
    end: float
    words: list[LyricWord] = field(default_factory=list)
    kind: str = "verse"  # verse, chorus, hook, bridge, outro

    def as_dict(self) -> dict:
        return {
            "text": self.text,
            "start": float(self.start),
            "end": float(self.end),
            "kind": self.kind,
            "words": [
                {"text": w.text, "start": float(w.start), "end": float(w.end)} for w in self.words
            ],
        }


@dataclass
class LyricsBundle:
    title: str = "Untitled"
    description: str = ""
    hashtags: list[str] = field(default_factory=list)
    thumbnail_text: str = ""
    lines: list[LyricLine] = field(default_factory=list)
    mood: str = "balanced"
    palette: list[str] = field(default_factory=list)
    raw_text: str = ""

    def as_dict(self) -> dict:
        return {
            "title": self.title,
            "description": self.description,
            "hashtags": list(self.hashtags),
            "thumbnail_text": self.thumbnail_text,
            "mood": self.mood,
            "palette": list(self.palette),
            "lines": [line.as_dict() for line in self.lines],
            "raw_text": self.raw_text,
        }

    def save(self, path: Path) -> None:
        path.write_text(json.dumps(self.as_dict(), indent=2, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "LyricsBundle":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        lines: list[LyricLine] = []
        for line in data.get("lines", []):
            words = [LyricWord(**w) for w in line.get("words", [])]
            lines.append(
                LyricLine(
                    text=line["text"],
                    start=float(line.get("start", 0.0)),
                    end=float(line.get("end", 0.0)),
                    words=words,
                    kind=line.get("kind", "verse"),
                )
            )
        return cls(
            title=data.get("title", "Untitled"),
            description=data.get("description", ""),
            hashtags=list(data.get("hashtags", [])),
            thumbnail_text=data.get("thumbnail_text", ""),
            lines=lines,
            mood=data.get("mood", "balanced"),
            palette=list(data.get("palette", [])),
            raw_text=data.get("raw_text", ""),
        )


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------


SYSTEM_PROMPT_LYRICS = (
    "Kamu adalah penulis lirik profesional yang menulis dalam Bahasa Indonesia. "
    "Tulis lirik yang natural, emosional, mudah dinyanyikan, dan cocok untuk video "
    "musik / lyric spectrum. Selalu kembalikan struktur jelas: [Verse], [Chorus], "
    "[Hook] / [Bridge] sesuai konteks. Hindari kata yang sulit dinyanyikan."
)

SYSTEM_PROMPT_META = (
    "Kamu adalah copywriter untuk konten musik di YouTube / TikTok / Reels. "
    "Berikan output JSON valid dengan kunci: title, description, hashtags (list), "
    "thumbnail_text (singkat, maks 6 kata). Jangan menulis kalimat di luar JSON."
)


def _split_into_lines(raw: str) -> list[tuple[str, str]]:
    """Return ``(kind, line)`` tuples from raw model output."""
    out: list[tuple[str, str]] = []
    current_kind = "verse"
    for raw_line in raw.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        lower = line.lower()
        if lower.startswith("[") and lower.endswith("]"):
            tag = lower.strip("[] ").split()[0]
            if "chor" in tag:
                current_kind = "chorus"
            elif "hook" in tag:
                current_kind = "hook"
            elif "bridge" in tag:
                current_kind = "bridge"
            elif "outro" in tag:
                current_kind = "outro"
            else:
                current_kind = "verse"
            continue
        # Strip leading dashes / bullets
        clean = line.lstrip("-•* ").strip()
        if clean:
            out.append((current_kind, clean))
    return out


def _time_lines(
    pairs: list[tuple[str, str]],
    duration: float,
    beat_times: Iterable[float] | np.ndarray,
) -> list[LyricLine]:
    if not pairs:
        return []

    beat_arr = np.asarray(list(beat_times), dtype=np.float32)
    n_lines = len(pairs)

    # Skip a small intro before the first line
    intro = min(2.5, max(0.5, duration * 0.05))
    body = max(duration - intro - 0.5, 1.0)

    # Choose line boundaries: prefer beat-aligned spacing.
    if beat_arr.size >= n_lines + 1:
        # Pick evenly spaced beats across the song
        idx = np.linspace(0, beat_arr.size - 1, n_lines + 1).astype(int)
        boundaries = beat_arr[idx]
    else:
        boundaries = np.linspace(intro, intro + body, n_lines + 1, dtype=np.float32)

    lines: list[LyricLine] = []
    for i, (kind, text) in enumerate(pairs):
        start = float(boundaries[i])
        end = float(boundaries[i + 1])
        if end <= start:
            end = start + max(0.5, body / n_lines)
        words_text = text.split()
        if not words_text:
            continue
        per_word = (end - start) / len(words_text)
        words = []
        cursor = start
        for w in words_text:
            words.append(LyricWord(text=w, start=cursor, end=cursor + per_word))
            cursor += per_word
        lines.append(LyricLine(text=text, start=start, end=end, words=words, kind=kind))
    return lines


class LyricsGenerator:
    """Generate lyric bundles using the AI engine."""

    def __init__(self, ai: AIEngine | None = None) -> None:
        self.ai = ai or AIEngine()

    # ----- public -------------------------------------------------------
    def generate(
        self,
        analysis: MusicAnalysis,
        *,
        theme: str = "kebebasan dan harapan",
        language: str = "Indonesia",
        style: str | None = None,
        target_lines: int = 12,
    ) -> LyricsBundle:
        style = style or analysis.vibe
        prompt = self._build_prompt(analysis, theme=theme, language=language, style=style, target_lines=target_lines)
        result = self.ai.chat(SYSTEM_PROMPT_LYRICS, prompt)
        raw = result.text
        pairs = _split_into_lines(raw)
        if not pairs:
            pairs = [("verse", "Lampu kota memantul di mataku"), ("chorus", "Bawa aku ke langit malam")]
        lines = _time_lines(pairs, max(analysis.duration, 8.0), analysis.beat_times)

        meta = self._generate_meta(analysis, theme=theme, style=style)
        return LyricsBundle(
            title=meta.get("title", "Untitled"),
            description=meta.get("description", ""),
            hashtags=list(meta.get("hashtags", [])),
            thumbnail_text=meta.get("thumbnail_text", ""),
            lines=lines,
            mood=analysis.mood,
            palette=list(analysis.suggested_palette),
            raw_text=raw,
        )

    def rewrite(self, bundle: LyricsBundle, *, instruction: str) -> LyricsBundle:
        """Rewrite an existing bundle while preserving timings."""
        joined = "\n".join(line.text for line in bundle.lines)
        prompt = (
            f"Tulis ulang lirik berikut dengan instruksi: {instruction}. "
            "Pertahankan jumlah baris dan jumlah kata per baris semirip mungkin. "
            "Output hanya lirik, satu baris per baris.\n\n" + joined
        )
        result = self.ai.chat(SYSTEM_PROMPT_LYRICS, prompt)
        new_lines = [ln.strip() for ln in result.text.splitlines() if ln.strip()]
        # Best-effort replacement, keep timings
        for line, new_text in zip(bundle.lines, new_lines):
            if not new_text:
                continue
            line.text = new_text
            if line.words:
                step = (line.end - line.start) / max(1, len(new_text.split()))
                cursor = line.start
                line.words = []
                for w in new_text.split():
                    line.words.append(LyricWord(text=w, start=cursor, end=cursor + step))
                    cursor += step
        bundle.raw_text = result.text
        return bundle

    # ----- helpers ------------------------------------------------------
    def _build_prompt(
        self,
        analysis: MusicAnalysis,
        *,
        theme: str,
        language: str,
        style: str,
        target_lines: int,
    ) -> str:
        return (
            f"Tulis lirik lagu dalam bahasa {language}.\n"
            f"Tema: {theme}.\n"
            f"Gaya / vibe: {style}.\n"
            f"BPM: {analysis.bpm:.0f} | Mood: {analysis.mood} | Genre indikatif: {analysis.genre_hint}.\n"
            f"Durasi lagu: {analysis.duration:.1f} detik.\n"
            f"Target jumlah baris: sekitar {target_lines}.\n"
            "Struktur: gunakan tag [Verse], [Chorus], [Hook] atau [Bridge] di awal section. "
            "Tulis hanya tag + baris lirik, tanpa penjelasan."
        )

    def _generate_meta(self, analysis: MusicAnalysis, *, theme: str, style: str) -> dict:
        prompt = (
            "Buat metadata untuk satu lagu / video musik berdasarkan data berikut.\n"
            f"Tema: {theme}\nGaya: {style}\nMood: {analysis.mood}\nGenre: {analysis.genre_hint}\n"
            f"BPM: {analysis.bpm:.0f}\nDurasi: {analysis.duration:.1f}s\n"
            "Kembalikan JSON valid dengan key title, description, hashtags (list of 5-8), thumbnail_text."
        )
        data = self.ai.chat_json(SYSTEM_PROMPT_META, prompt)
        # Defensive defaults
        return {
            "title": str(data.get("title") or "Untitled"),
            "description": str(data.get("description") or "Generated by Spectrum AI."),
            "hashtags": [str(h) for h in (data.get("hashtags") or [])][:10],
            "thumbnail_text": str(data.get("thumbnail_text") or ""),
        }
