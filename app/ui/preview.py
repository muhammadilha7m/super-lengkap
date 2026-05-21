"""Live preview widget — renders frames on a QTimer."""
from __future__ import annotations

import time

import cv2
import numpy as np
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QLabel, QSizePolicy

from renderer import RenderJob, render_preview_frame


class PreviewWidget(QLabel):
    """Renders a single preview frame, repeatedly, at the configured FPS."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumSize(640, 360)
        self.setAlignment(Qt.AlignCenter)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setText("Pilih audio untuk mulai")
        self.setStyleSheet("color: #6c6c8e; font-size: 14px;")

        self._job: RenderJob | None = None
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._start_time = 0.0
        self._pause_offset = 0.0
        self._paused = True
        self._fps = 30
        self._last_fps_calc = time.time()
        self._frames_drawn = 0
        self.fps_callback = None  # type: ignore[assignment]

    # ----- public --------------------------------------------------------
    def set_job(self, job: RenderJob | None) -> None:
        self._job = job
        if job is None:
            self.setText("Pilih audio untuk mulai")
            self._timer.stop()
            return
        self._fps = max(15, min(60, int(self.parent_fps() or job.settings.fps)))
        self._pause_offset = 0.0
        self._start_time = time.time()
        self._paused = False
        self._render_once(0.0)
        self._timer.start(max(16, int(1000 / self._fps)))

    def play(self) -> None:
        if self._job is None:
            return
        if self._paused:
            self._start_time = time.time() - self._pause_offset
            self._paused = False
            self._timer.start(max(16, int(1000 / self._fps)))

    def pause(self) -> None:
        if not self._paused and self._job is not None:
            self._pause_offset = time.time() - self._start_time
            self._paused = True
            self._timer.stop()

    def stop(self) -> None:
        self._paused = True
        self._pause_offset = 0.0
        self._timer.stop()
        if self._job is not None:
            self._render_once(0.0)

    def parent_fps(self) -> int | None:
        try:
            return int(self.window().property("preview_fps") or 0) or None
        except Exception:
            return None

    # ----- internal ------------------------------------------------------
    def _tick(self) -> None:
        if self._job is None or self._paused:
            return
        t = (time.time() - self._start_time) % max(1e-3, self._job.duration)
        self._render_once(t)
        self._frames_drawn += 1
        now = time.time()
        if now - self._last_fps_calc >= 1.0:
            fps = self._frames_drawn / (now - self._last_fps_calc)
            self._frames_drawn = 0
            self._last_fps_calc = now
            if self.fps_callback is not None:
                self.fps_callback(fps)

    def _render_once(self, t: float) -> None:
        assert self._job is not None
        frame = render_preview_frame(self._job, t)
        self._set_frame(frame)

    def _set_frame(self, frame: np.ndarray) -> None:
        # BGR -> RGB
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, _ = rgb.shape
        bytes_per_line = 3 * w
        image = QImage(rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
        pix = QPixmap.fromImage(image)
        pix = pix.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.setPixmap(pix)
