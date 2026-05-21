"""Qt worker threads for long-running tasks.

Each worker emits ``progress``/``finished``/``failed`` signals so the UI can
display status without freezing. Workers are designed to be created and then
handed to :func:`start_worker` (in ``main_window``) which keeps a Python
reference to both the worker QObject and its QThread for the duration of the
run — this prevents the worker from being garbage-collected by Python while
the C++ side is still using it (the classic PySide segfault pattern).
"""
from __future__ import annotations

import traceback
from typing import Optional

from PySide6.QtCore import QObject, QThread, Signal

from ai_engine import AIEngine
from audio_analyzer import AudioAnalyzer, MusicAnalysis
from export_engine import ExportSettings, VideoExporter
from lyrics_generator import LyricsBundle, LyricsGenerator
from renderer import RenderJob
from app.core.logger import get_logger

log = get_logger(__name__)


class _BaseWorker(QObject):
    """Common signals for all background workers."""

    progress = Signal(int, int, str)
    failed = Signal(str)

    def safe_run(self) -> None:
        try:
            self._do_run()
        except Exception as exc:
            tb = traceback.format_exc()
            log.error("Worker error: %s\n%s", exc, tb)
            self.failed.emit(str(exc))

    def _do_run(self) -> None:  # pragma: no cover - subclasses override
        raise NotImplementedError


class AnalyzeWorker(_BaseWorker):
    finished = Signal(object)  # MusicAnalysis

    def __init__(self, path: str, sample_rate: int = 44100) -> None:
        super().__init__()
        self.path = path
        self.sample_rate = sample_rate

    def _do_run(self) -> None:
        self.progress.emit(0, 1, "Memuat audio…")
        analyzer = AudioAnalyzer(sample_rate=self.sample_rate)
        analysis = analyzer.analyze(self.path)
        self.progress.emit(1, 1, "Analisis selesai")
        self.finished.emit(analysis)


class LyricsWorker(_BaseWorker):
    finished = Signal(object)  # LyricsBundle

    def __init__(self, analysis: MusicAnalysis, theme: str = "", style: Optional[str] = None) -> None:
        super().__init__()
        self.analysis = analysis
        self.theme = theme or "kebebasan dan harapan"
        self.style = style

    def _do_run(self) -> None:
        self.progress.emit(0, 1, "Generate lirik dengan Groq…")
        ai = AIEngine()
        gen = LyricsGenerator(ai=ai)
        bundle = gen.generate(self.analysis, theme=self.theme, style=self.style)
        self.progress.emit(1, 1, "Lirik selesai")
        self.finished.emit(bundle)


class RewriteLyricsWorker(_BaseWorker):
    finished = Signal(object)

    def __init__(self, bundle: LyricsBundle, instruction: str) -> None:
        super().__init__()
        self.bundle = bundle
        self.instruction = instruction

    def _do_run(self) -> None:
        ai = AIEngine()
        gen = LyricsGenerator(ai=ai)
        self.progress.emit(0, 1, "Rewrite lirik…")
        updated = gen.rewrite(self.bundle, instruction=self.instruction)
        self.progress.emit(1, 1, "Selesai")
        self.finished.emit(updated)


class ExportWorker(_BaseWorker):
    finished = Signal(str)  # output path

    def __init__(self, job: RenderJob, settings: ExportSettings) -> None:
        super().__init__()
        self.job = job
        self.settings = settings

    def _do_run(self) -> None:
        exporter = VideoExporter(self.settings)

        def report(i: int, total: int) -> None:
            self.progress.emit(i, total, f"Render {i}/{total} frame")

        path = exporter.export(self.job, progress=report)
        self.finished.emit(str(path))
