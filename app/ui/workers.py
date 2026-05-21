"""Qt worker threads for long-running tasks.

Each worker emits ``progress``/``finished``/``failed`` signals so the UI can
display status without freezing.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, QThread, Signal

from ai_engine import AIEngine
from audio_analyzer import AudioAnalyzer, MusicAnalysis
from export_engine import ExportSettings, VideoExporter
from lyrics_generator import LyricsBundle, LyricsGenerator
from renderer import RenderJob


class _BaseWorker(QObject):
    progress = Signal(int, int, str)
    failed = Signal(str)

    def start_in_thread(self) -> QThread:
        thread = QThread()
        self.moveToThread(thread)
        thread.started.connect(self.run)  # type: ignore[attr-defined]
        return thread

    def run(self) -> None:  # pragma: no cover - overridden
        raise NotImplementedError


class AnalyzeWorker(_BaseWorker):
    finished = Signal(object)  # MusicAnalysis

    def __init__(self, path: str, sample_rate: int = 44100) -> None:
        super().__init__()
        self.path = path
        self.sample_rate = sample_rate

    def run(self) -> None:
        try:
            self.progress.emit(0, 1, "Memuat audio…")
            analyzer = AudioAnalyzer(sample_rate=self.sample_rate)
            analysis = analyzer.analyze(self.path)
            self.progress.emit(1, 1, "Analisis selesai")
            self.finished.emit(analysis)
        except Exception as exc:  # pragma: no cover - defensive
            self.failed.emit(str(exc))


class LyricsWorker(_BaseWorker):
    finished = Signal(object)  # LyricsBundle

    def __init__(self, analysis: MusicAnalysis, theme: str = "", style: str | None = None) -> None:
        super().__init__()
        self.analysis = analysis
        self.theme = theme or "kebebasan dan harapan"
        self.style = style

    def run(self) -> None:
        try:
            self.progress.emit(0, 1, "Generate lirik dengan Groq…")
            ai = AIEngine()
            gen = LyricsGenerator(ai=ai)
            bundle = gen.generate(self.analysis, theme=self.theme, style=self.style)
            self.progress.emit(1, 1, "Lirik selesai")
            self.finished.emit(bundle)
        except Exception as exc:  # pragma: no cover - defensive
            self.failed.emit(str(exc))


class RewriteLyricsWorker(_BaseWorker):
    finished = Signal(object)

    def __init__(self, bundle: LyricsBundle, instruction: str) -> None:
        super().__init__()
        self.bundle = bundle
        self.instruction = instruction

    def run(self) -> None:
        try:
            ai = AIEngine()
            gen = LyricsGenerator(ai=ai)
            self.progress.emit(0, 1, "Rewrite lirik…")
            updated = gen.rewrite(self.bundle, instruction=self.instruction)
            self.progress.emit(1, 1, "Selesai")
            self.finished.emit(updated)
        except Exception as exc:
            self.failed.emit(str(exc))


class ExportWorker(_BaseWorker):
    finished = Signal(str)  # output path

    def __init__(self, job: RenderJob, settings: ExportSettings) -> None:
        super().__init__()
        self.job = job
        self.settings = settings

    def run(self) -> None:
        try:
            exporter = VideoExporter(self.settings)

            def report(i: int, total: int) -> None:
                self.progress.emit(i, total, f"Render {i}/{total} frame")

            path = exporter.export(self.job, progress=report)
            self.finished.emit(str(path))
        except Exception as exc:
            self.failed.emit(str(exc))
