"""Audio analyzer.

Wraps librosa to extract everything the renderer / AI need:

* sample data + sample rate
* duration
* tempo / BPM + beat frames
* RMS energy envelope
* onset envelope
* mel spectrogram (for the visualizer)
* mood / energy / vibe heuristics (used by the AI prompt builder)

The analyzer never throws on a bad file — it logs and returns a
``MusicAnalysis`` with sensible fallbacks so the rest of the app keeps running.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import numpy as np

from app.core.logger import get_logger

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class MusicAnalysis:
    """All information extracted from an audio file."""

    path: str = ""
    sample_rate: int = 44100
    duration: float = 0.0
    samples: np.ndarray = field(default_factory=lambda: np.zeros(0, dtype=np.float32))
    bpm: float = 120.0
    beat_times: np.ndarray = field(default_factory=lambda: np.zeros(0, dtype=np.float32))
    onset_env: np.ndarray = field(default_factory=lambda: np.zeros(0, dtype=np.float32))
    rms: np.ndarray = field(default_factory=lambda: np.zeros(0, dtype=np.float32))
    mel_db: np.ndarray = field(default_factory=lambda: np.zeros((0, 0), dtype=np.float32))
    spectral_centroid: float = 0.0
    chroma_mean: np.ndarray = field(default_factory=lambda: np.zeros(12, dtype=np.float32))
    energy: float = 0.0
    mood: str = "balanced"
    genre_hint: str = "pop"
    vibe: str = "modern"
    suggested_palette: list[str] = field(default_factory=lambda: ["#00e5ff", "#7c4dff", "#ff4081"])

    def as_dict(self) -> dict:
        return {
            "path": self.path,
            "sample_rate": self.sample_rate,
            "duration": float(self.duration),
            "bpm": float(self.bpm),
            "beat_count": int(self.beat_times.size),
            "energy": float(self.energy),
            "mood": self.mood,
            "genre_hint": self.genre_hint,
            "vibe": self.vibe,
            "spectral_centroid": float(self.spectral_centroid),
            "suggested_palette": list(self.suggested_palette),
        }


# ---------------------------------------------------------------------------
# Analyzer
# ---------------------------------------------------------------------------


_MOODS = {
    "calm": ["#1f3a93", "#2c3e50", "#16a085"],
    "balanced": ["#00e5ff", "#7c4dff", "#ff4081"],
    "energetic": ["#ff5722", "#ffeb3b", "#ff00aa"],
    "dark": ["#0d0d23", "#3a0ca3", "#b5179e"],
    "dreamy": ["#a18cd1", "#fbc2eb", "#84fab0"],
}


class AudioAnalyzer:
    """High-level audio analysis using librosa."""

    def __init__(
        self,
        sample_rate: int = 44100,
        fft_size: int = 2048,
        hop_length: int = 512,
        n_mels: int = 128,
    ) -> None:
        self.sample_rate = sample_rate
        self.fft_size = fft_size
        self.hop_length = hop_length
        self.n_mels = n_mels

    # ----- IO -----------------------------------------------------------
    def load(self, path: str | Path) -> tuple[np.ndarray, int]:
        import librosa

        log.info("Loading audio: %s", path)
        samples, sr = librosa.load(str(path), sr=self.sample_rate, mono=True)
        return samples.astype(np.float32, copy=False), int(sr)

    # ----- Full pipeline ------------------------------------------------
    def analyze(self, path: str | Path) -> MusicAnalysis:
        import librosa

        try:
            samples, sr = self.load(path)
        except Exception as exc:
            log.error("Audio load failed: %s", exc)
            return MusicAnalysis(path=str(path))

        if samples.size == 0:
            log.warning("Empty audio file")
            return MusicAnalysis(path=str(path), sample_rate=sr)

        duration = float(samples.size / sr)
        try:
            tempo, beats = librosa.beat.beat_track(y=samples, sr=sr, hop_length=self.hop_length)
            beat_times = librosa.frames_to_time(beats, sr=sr, hop_length=self.hop_length)
        except Exception as exc:
            log.warning("Beat tracking failed: %s", exc)
            tempo, beat_times = 120.0, np.zeros(0, dtype=np.float32)

        try:
            onset_env = librosa.onset.onset_strength(y=samples, sr=sr, hop_length=self.hop_length)
        except Exception:
            onset_env = np.zeros(max(1, samples.size // self.hop_length), dtype=np.float32)

        try:
            rms = librosa.feature.rms(y=samples, frame_length=self.fft_size, hop_length=self.hop_length)[0]
        except Exception:
            rms = np.zeros_like(onset_env, dtype=np.float32)

        try:
            mel = librosa.feature.melspectrogram(
                y=samples,
                sr=sr,
                n_fft=self.fft_size,
                hop_length=self.hop_length,
                n_mels=self.n_mels,
            )
            mel_db = librosa.power_to_db(mel, ref=np.max).astype(np.float32)
        except Exception:
            mel_db = np.zeros((self.n_mels, len(onset_env)), dtype=np.float32)

        try:
            sc = float(librosa.feature.spectral_centroid(y=samples, sr=sr).mean())
        except Exception:
            sc = 0.0

        try:
            chroma_mean = librosa.feature.chroma_stft(y=samples, sr=sr).mean(axis=1).astype(np.float32)
        except Exception:
            chroma_mean = np.zeros(12, dtype=np.float32)

        energy = float(np.clip(rms.mean() * 4.0, 0.0, 1.0)) if rms.size else 0.0
        bpm_value = float(np.asarray(tempo).flatten()[0]) if np.asarray(tempo).size else 120.0
        mood = self._estimate_mood(bpm_value, energy, sc)
        genre_hint = self._estimate_genre(bpm_value, sc)
        vibe = self._estimate_vibe(mood, energy)

        return MusicAnalysis(
            path=str(path),
            sample_rate=sr,
            duration=duration,
            samples=samples,
            bpm=bpm_value,
            beat_times=np.asarray(beat_times, dtype=np.float32),
            onset_env=onset_env.astype(np.float32),
            rms=rms.astype(np.float32),
            mel_db=mel_db,
            spectral_centroid=sc,
            chroma_mean=chroma_mean,
            energy=energy,
            mood=mood,
            genre_hint=genre_hint,
            vibe=vibe,
            suggested_palette=_MOODS.get(mood, _MOODS["balanced"]),
        )

    # ----- Mood / genre / palette heuristics ----------------------------
    @staticmethod
    def _estimate_mood(bpm: float, energy: float, centroid: float) -> str:
        if energy > 0.65 and bpm > 120:
            return "energetic"
        if energy < 0.25 and bpm < 95:
            return "calm"
        if centroid > 3500 and energy > 0.45:
            return "dreamy"
        if centroid < 1500 and energy < 0.4:
            return "dark"
        return "balanced"

    @staticmethod
    def _estimate_genre(bpm: float, centroid: float) -> str:
        if bpm > 145 and centroid > 3000:
            return "edm"
        if 120 < bpm <= 145:
            return "pop"
        if 95 < bpm <= 120:
            return "hiphop" if centroid < 2500 else "rnb"
        if bpm <= 95:
            return "ballad"
        return "pop"

    @staticmethod
    def _estimate_vibe(mood: str, energy: float) -> str:
        if mood == "energetic":
            return "neon-night"
        if mood == "dreamy":
            return "pastel-dream"
        if mood == "dark":
            return "cinematic-noir"
        if mood == "calm":
            return "warm-acoustic"
        return "modern-glow" if energy > 0.5 else "soft-ambient"


# ---------------------------------------------------------------------------
# Per-frame helpers used by the visualizer
# ---------------------------------------------------------------------------


def spectrum_bands(
    samples: np.ndarray,
    sr: int,
    center_sec: float,
    fft_size: int,
    bands: int,
    log_scale: bool = True,
) -> np.ndarray:
    """Return ``bands`` normalised magnitudes centred at ``center_sec``."""
    if samples.size == 0:
        return np.zeros(bands, dtype=np.float32)

    center = int(center_sec * sr)
    half = fft_size // 2
    start = max(0, center - half)
    end = start + fft_size
    chunk = samples[start:end]
    if chunk.size < fft_size:
        pad = np.zeros(fft_size - chunk.size, dtype=samples.dtype)
        chunk = np.concatenate([chunk, pad])

    window = np.hanning(fft_size).astype(samples.dtype)
    spectrum = np.abs(np.fft.rfft(chunk * window))[:fft_size // 2]

    if log_scale:
        n_bins = spectrum.size
        edges = np.unique(np.logspace(0, np.log10(n_bins), bands + 1).astype(int))
        if edges.size < bands + 1:
            edges = np.linspace(0, n_bins, bands + 1, dtype=int)
        out = np.zeros(bands, dtype=np.float32)
        for i in range(bands):
            s = edges[i]
            e = max(s + 1, edges[i + 1])
            out[i] = float(spectrum[s:e].mean())
    else:
        chunked = np.array_split(spectrum, bands)
        out = np.array([float(c.mean()) if c.size else 0.0 for c in chunked], dtype=np.float32)

    peak = float(out.max()) or 1.0
    return np.clip(out / peak, 0.0, 1.0)


def beat_strength_at(time_sec: float, beat_times: Iterable[float], window: float = 0.12) -> float:
    """Return 0..1 strength reflecting how close ``time_sec`` is to a beat."""
    arr = np.asarray(list(beat_times), dtype=np.float32)
    if arr.size == 0:
        return 0.0
    delta = np.min(np.abs(arr - time_sec))
    return float(max(0.0, 1.0 - delta / window))
