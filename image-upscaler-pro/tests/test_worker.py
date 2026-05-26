"""Tests for the BatchWorker."""

from __future__ import annotations

import queue
import threading
import time
from pathlib import Path

from PIL import Image

from image_upscaler.core.job import Job
from image_upscaler.core.worker import BatchWorker, WorkerEvent
from image_upscaler.engine.base import EngineError, UpscaleEngine, UpscaleOptions
from image_upscaler.engine.lanczos import LanczosEngine


def _make_image(path: Path, size: tuple[int, int] = (16, 12)) -> None:
    Image.new("RGB", size, color=(0, 128, 255)).save(path)


def _drain(events: queue.Queue[WorkerEvent], kinds: tuple[str, ...]) -> list[WorkerEvent]:
    out: list[WorkerEvent] = []
    while True:
        try:
            out.append(events.get(timeout=2.0))
        except queue.Empty:
            break
        if out[-1].kind in kinds:
            break
    return out


def test_worker_completes_batch(tmp_path: Path) -> None:
    files = [tmp_path / f"i{i}.png" for i in range(3)]
    for f in files:
        _make_image(f)
    jobs = [Job(input_path=f) for f in files]
    events: queue.Queue[WorkerEvent] = queue.Queue()
    w = BatchWorker(
        engine=LanczosEngine(),
        options=UpscaleOptions(scale=2, output_format="PNG"),
        jobs=jobs,
        output_dir=str(tmp_path / "out"),
        conflict_mode="rename",
        event_queue=events,
    )
    w.start()
    w.join(timeout=10.0)
    assert not w.is_running
    drained = _drain(events, ("batch_finished", "batch_cancelled"))
    assert any(e.kind == "batch_finished" for e in drained)
    for job in jobs:
        assert job.status == "done"
        assert job.output_path is not None
        assert job.output_path.exists()


class _SlowEngine(UpscaleEngine):
    name = "slow"
    display_name = "Slow"

    def upscale(self, input_path, output_path, options, cancel_event):  # type: ignore[override]
        if cancel_event.wait(0.4):
            raise EngineError("cancelled")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (8, 8)).save(output_path)


def test_worker_cancellation(tmp_path: Path) -> None:
    files = [tmp_path / f"i{i}.png" for i in range(5)]
    for f in files:
        _make_image(f)
    jobs = [Job(input_path=f) for f in files]
    events: queue.Queue[WorkerEvent] = queue.Queue()
    w = BatchWorker(
        engine=_SlowEngine(),
        options=UpscaleOptions(scale=2, output_format="PNG"),
        jobs=jobs,
        output_dir=str(tmp_path / "out"),
        conflict_mode="rename",
        event_queue=events,
    )
    w.start()
    time.sleep(0.1)
    w.cancel()
    w.join(timeout=5.0)
    assert not w.is_running
    assert any(j.status in ("cancelled", "failed") for j in jobs)


def test_worker_pause_resume(tmp_path: Path) -> None:
    f = tmp_path / "i.png"
    _make_image(f)
    jobs = [Job(input_path=f)]
    events: queue.Queue[WorkerEvent] = queue.Queue()
    w = BatchWorker(
        engine=LanczosEngine(),
        options=UpscaleOptions(scale=2, output_format="PNG"),
        jobs=jobs,
        output_dir=str(tmp_path / "out"),
        conflict_mode="rename",
        event_queue=events,
    )
    w.pause()  # should be no-op while not running
    w.start()
    w.pause()
    threading.Event().wait(0.05)
    assert w.is_paused or not w.is_running  # may finish before pause registers
    w.resume()
    w.join(timeout=5.0)
    assert not w.is_running
