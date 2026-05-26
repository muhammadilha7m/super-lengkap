"""Threaded batch worker.

Workers run jobs sequentially on a background thread and publish events into a
``queue.Queue`` so the Tk UI can drain it via ``after(...)``. This keeps the UI
fully responsive and avoids touching Tk from non-main threads.
"""

from __future__ import annotations

import logging
import queue
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from ..constants import (
    JOB_STATUS_CANCELLED,
    JOB_STATUS_DONE,
    JOB_STATUS_FAILED,
    JOB_STATUS_RUNNING,
    JOB_STATUS_SKIPPED,
)
from ..engine.base import EngineError, UpscaleEngine, UpscaleOptions
from ..utils.paths import resolve_output_path, safe_file_size
from .job import Job

log = logging.getLogger(__name__)

EventKind = Literal[
    "batch_started",
    "job_started",
    "job_progress",
    "job_done",
    "job_failed",
    "job_skipped",
    "batch_paused",
    "batch_resumed",
    "batch_finished",
    "batch_cancelled",
]


@dataclass
class WorkerEvent:
    kind: EventKind
    job: Job | None = None
    message: str = ""


class BatchWorker:
    """Run a list of :class:`Job` items through an :class:`UpscaleEngine`."""

    def __init__(
        self,
        engine: UpscaleEngine,
        options: UpscaleOptions,
        jobs: list[Job],
        output_dir: str,
        conflict_mode: str,
        event_queue: queue.Queue[WorkerEvent],
    ) -> None:
        self.engine = engine
        self.options = options
        self.jobs = jobs
        self.output_dir = output_dir
        self.conflict_mode = conflict_mode
        self.events = event_queue

        self._cancel_event = threading.Event()
        self._pause_event = threading.Event()
        self._pause_event.set()  # set = running, clear = paused
        self._thread: threading.Thread | None = None
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def is_paused(self) -> bool:
        return not self._pause_event.is_set()

    def start(self) -> None:
        if self._running:
            return
        self._cancel_event.clear()
        self._pause_event.set()
        self._running = True
        self._thread = threading.Thread(target=self._run, name="BatchWorker", daemon=True)
        self._thread.start()

    def pause(self) -> None:
        if not self._running:
            return
        self._pause_event.clear()
        self.events.put(WorkerEvent("batch_paused"))

    def resume(self) -> None:
        if not self._running:
            return
        self._pause_event.set()
        self.events.put(WorkerEvent("batch_resumed"))

    def cancel(self) -> None:
        self._cancel_event.set()
        self._pause_event.set()  # unblock anyone waiting

    def join(self, timeout: float | None = None) -> None:
        if self._thread:
            self._thread.join(timeout)

    def _run(self) -> None:
        self.events.put(WorkerEvent("batch_started"))
        finished_kind: EventKind = "batch_finished"
        try:
            for job in self.jobs:
                if self._cancel_event.is_set():
                    job.status = JOB_STATUS_CANCELLED
                    self.events.put(WorkerEvent("job_failed", job=job, message="cancelled"))
                    finished_kind = "batch_cancelled"
                    continue

                self._pause_event.wait()
                if self._cancel_event.is_set():
                    job.status = JOB_STATUS_CANCELLED
                    self.events.put(WorkerEvent("job_failed", job=job, message="cancelled"))
                    finished_kind = "batch_cancelled"
                    continue

                self._run_one(job)
        finally:
            self._running = False
            self.events.put(WorkerEvent(finished_kind))

    def _run_one(self, job: Job) -> None:
        job.status = JOB_STATUS_RUNNING
        job.progress = 0.05
        job.message = ""
        self.events.put(WorkerEvent("job_started", job=job))

        output_path = resolve_output_path(
            input_path=job.input_path,
            output_dir=self.output_dir,
            output_format=self.options.output_format,
            scale=self.options.scale,
            conflict_mode=self.conflict_mode,
        )
        if output_path is None:
            job.status = JOB_STATUS_SKIPPED
            job.message = "Sudah ada (skip)"
            job.progress = 1.0
            self.events.put(WorkerEvent("job_skipped", job=job))
            return

        job.output_path = output_path
        job.in_size_bytes = safe_file_size(job.input_path)

        started = time.time()
        try:
            self.engine.upscale(job.input_path, output_path, self.options, self._cancel_event)
        except EngineError as exc:
            if str(exc) == "cancelled":
                job.status = JOB_STATUS_CANCELLED
                job.message = "Dibatalkan"
            else:
                job.status = JOB_STATUS_FAILED
                job.message = str(exc)
            self.events.put(WorkerEvent("job_failed", job=job, message=job.message))
            return
        except Exception as exc:  # pragma: no cover - defensive
            log.exception("Unexpected engine error for %s", job.input_path)
            job.status = JOB_STATUS_FAILED
            job.message = f"Error tak terduga: {exc}"
            self.events.put(WorkerEvent("job_failed", job=job, message=job.message))
            return

        job.out_size_bytes = safe_file_size(output_path)
        job.duration_s = time.time() - started
        job.status = JOB_STATUS_DONE
        job.progress = 1.0
        job.message = f"Selesai dalam {job.duration_s:.1f}s"
        self.events.put(WorkerEvent("job_done", job=job))


def build_jobs(input_paths: list[Path]) -> list[Job]:
    """Helper to materialize :class:`Job` instances from file paths."""
    return [Job(input_path=p) for p in input_paths]
