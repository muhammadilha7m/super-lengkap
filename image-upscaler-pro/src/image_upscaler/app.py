"""Main application — wires the UI, config, engines, and worker together."""

from __future__ import annotations

import contextlib
import logging
import os
import platform
import queue
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import TYPE_CHECKING

import customtkinter as ctk

from .config import AppConfig
from .constants import (
    APP_NAME,
    ENGINE_REALESRGAN,
    UI_DEFAULT_HEIGHT,
    UI_DEFAULT_WIDTH,
    UI_MIN_HEIGHT,
    UI_MIN_WIDTH,
)
from .core.job import Job
from .core.worker import BatchWorker, WorkerEvent
from .engine import LanczosEngine, RealEsrganEngine, UpscaleEngine, UpscaleOptions
from .engine.realesrgan import find_realesrgan_binary
from .ui import theme
from .ui.dnd import get_dnd_root_class, register_drop_target
from .ui.preview import PreviewPanel
from .ui.queue_panel import QueuePanel
from .ui.sidebar import Sidebar
from .ui.statusbar import StatusBar
from .utils.notifications import play_done_sound, show_desktop_notification
from .utils.paths import expand_paths

if TYPE_CHECKING:
    pass

log = logging.getLogger(__name__)


def _make_root() -> ctk.CTk:
    """Create a Tk root, preferring the drag-and-drop enabled subclass."""
    dnd_cls = get_dnd_root_class()
    if dnd_cls is not None:
        try:
            return dnd_cls()
        except Exception as exc:  # pragma: no cover - depends on env
            log.warning("DnD root init failed (%s); falling back to plain CTk.", exc)
    return ctk.CTk()


class App:
    """Top-level application controller."""

    def __init__(self) -> None:
        self.config = AppConfig.load()

        ctk.set_appearance_mode(self.config.appearance_mode)
        ctk.set_default_color_theme("blue")

        self.root = _make_root()
        self.root.title(APP_NAME)
        self.root.geometry(f"{UI_DEFAULT_WIDTH}x{UI_DEFAULT_HEIGHT}")
        self.root.minsize(UI_MIN_WIDTH, UI_MIN_HEIGHT)

        self.palette = theme.palette_for(self.config.appearance_mode, self.config.accent_color)
        self.root.configure(fg_color=self.palette.bg)

        self.jobs: list[Job] = []
        self.worker: BatchWorker | None = None
        self.event_queue: queue.Queue[WorkerEvent] = queue.Queue()
        self._poll_after_id: str | None = None

        self._build_layout()
        self._register_dnd()
        self._refresh_engine_status()

        self.root.bind("<Control-o>", lambda _e: self._add_files())
        self.root.bind("<Control-O>", lambda _e: self._add_folder())
        self.root.bind("<F5>", lambda _e: self._start_batch())
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self._poll_events()

    # ------------------------------------------------------------------ Layout

    def _build_layout(self) -> None:
        self.root.grid_columnconfigure(0, weight=0, minsize=320)
        self.root.grid_columnconfigure(1, weight=0, minsize=880)
        self.root.grid_columnconfigure(2, weight=1, minsize=380)
        self.root.grid_rowconfigure(0, weight=1)

        self.sidebar = Sidebar(
            self.root,
            config=self.config,
            palette=self.palette,
            on_change=self._on_config_change,
            on_browse_output=self._browse_output_dir,
            on_browse_realesrgan=self._browse_realesrgan,
            on_appearance_change=self._on_appearance_change,
            on_accent_change=self._on_accent_change,
        )
        self.sidebar.grid(row=0, column=0, rowspan=2, sticky="nsw")

        self.queue_panel = QueuePanel(
            self.root,
            palette=self.palette,
            on_add_files=self._add_files,
            on_add_folder=self._add_folder,
            on_clear=self._clear_queue,
            on_remove_selected=self._remove_selected,
            on_select=self._on_queue_select,
            on_start=self._start_batch,
            on_pause_resume=self._toggle_pause,
            on_cancel=self._cancel_batch,
            on_open_output=self._open_output_dir,
        )
        self.queue_panel.grid(row=0, column=1, sticky="nsew")

        self.preview = PreviewPanel(self.root, palette=self.palette)
        self.preview.grid(row=0, column=2, sticky="nsew", padx=(8, 20), pady=(20, 8))

        self.statusbar = StatusBar(self.root, palette=self.palette)
        self.statusbar.grid(row=1, column=1, columnspan=2, sticky="ew")

    def _register_dnd(self) -> None:
        def _on_paths(paths: list[Path]) -> None:
            self._add_paths(paths)

        ok_root = register_drop_target(self.root, _on_paths)
        try:
            ok_queue = register_drop_target(self.queue_panel.list_frame, _on_paths)
        except Exception as exc:  # pragma: no cover - depends on env
            log.debug("DnD on list_frame failed: %s", exc)
            ok_queue = False
        if not (ok_root or ok_queue):
            log.info("Drag & drop not active in this session.")

    # ------------------------------------------------------------------ Engine

    def _build_engine(self) -> tuple[UpscaleEngine, str, bool]:
        """Resolve the active engine based on current settings. Returns (engine, message, ok)."""
        if self.config.engine == ENGINE_REALESRGAN:
            engine = RealEsrganEngine(binary_override=self.config.realesrgan_binary)
            ok, msg = engine.available()
            return engine, msg, ok
        return LanczosEngine(), "", True

    def _refresh_engine_status(self) -> None:
        engine, msg, ok = self._build_engine()
        self.sidebar.show_realesrgan_controls(self.config.engine == ENGINE_REALESRGAN)
        if self.config.engine == ENGINE_REALESRGAN and not ok:
            self.sidebar.set_engine_warning(msg)
            self.statusbar.set_engine(f"Real-ESRGAN ({msg.split('.')[0]})", ok=False)
        else:
            self.sidebar.set_engine_warning("")
            self.statusbar.set_engine(engine.display_name, ok=True)

    # ------------------------------------------------------------------ Actions

    def _add_files(self) -> None:
        types = [
            ("Gambar", "*.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff"),
            ("Semua file", "*.*"),
        ]
        initial = self.config.recent_input_dirs[0] if self.config.recent_input_dirs else None
        files = filedialog.askopenfilenames(
            parent=self.root,
            title="Pilih gambar",
            filetypes=types,
            initialdir=initial,
        )
        if not files:
            return
        self._add_paths([Path(f) for f in files])

    def _add_folder(self) -> None:
        initial = self.config.recent_input_dirs[0] if self.config.recent_input_dirs else None
        folder = filedialog.askdirectory(
            parent=self.root,
            title="Pilih folder berisi gambar",
            initialdir=initial,
        )
        if not folder:
            return
        self._add_paths([Path(folder)])

    def _add_paths(self, raw_paths: list[Path]) -> None:
        if not raw_paths:
            return
        files = expand_paths(raw_paths, recursive=self.config.recursive_folder_scan)
        if not files:
            messagebox.showinfo(
                APP_NAME,
                "Tidak ada gambar yang didukung pada lokasi tersebut.",
                parent=self.root,
            )
            return

        existing = {j.input_path.resolve() for j in self.jobs}
        added = 0
        for f in files:
            r = f.resolve()
            if r in existing:
                continue
            self.jobs.append(Job(input_path=r))
            existing.add(r)
            added += 1

        if files:
            self.config.remember_input_dir(str(files[0].parent))

        self.statusbar.set_message(f"{added} gambar ditambahkan ke antrian.")
        self._render_jobs()

    def _clear_queue(self) -> None:
        if self.worker and self.worker.is_running:
            messagebox.showwarning(APP_NAME, "Tidak bisa membersihkan saat batch berjalan.")
            return
        self.jobs.clear()
        self.queue_panel.select_index(None)
        self.preview.show_job(None)
        self._render_jobs()
        self.statusbar.set_message("Antrian dibersihkan.")

    def _remove_selected(self) -> None:
        idx = self.queue_panel.selected_index()
        if idx is None:
            return
        if self.worker and self.worker.is_running:
            messagebox.showwarning(APP_NAME, "Tidak bisa menghapus saat batch berjalan.")
            return
        if 0 <= idx < len(self.jobs):
            del self.jobs[idx]
            self.queue_panel.select_index(None)
            self.preview.show_job(None)
            self._render_jobs()

    def _on_queue_select(self, index: int) -> None:
        if 0 <= index < len(self.jobs):
            self.preview.show_job(self.jobs[index])

    def _start_batch(self) -> None:
        if self.worker and self.worker.is_running:
            return
        if not self.jobs:
            messagebox.showinfo(APP_NAME, "Tambahkan gambar dulu ke antrian.")
            return

        engine, msg, ok = self._build_engine()
        if not ok:
            response = messagebox.askyesno(
                APP_NAME,
                f"{msg}\n\nLanjutkan dengan engine Lanczos (klasik)?",
                parent=self.root,
            )
            if not response:
                return
            engine = LanczosEngine()

        options = UpscaleOptions(
            scale=int(self.config.scale),
            output_format=self.config.output_format,
            jpeg_quality=int(self.config.jpeg_quality),
            webp_quality=int(self.config.webp_quality),
            preserve_exif=self.config.preserve_exif,
            model=self.config.realesrgan_model,
        )

        # Reset state for any non-finished jobs so they get re-run.
        for job in self.jobs:
            if job.status not in ("done", "skipped"):
                job.status = "pending"
                job.progress = 0.0
                job.message = ""
                job.output_path = None

        self.worker = BatchWorker(
            engine=engine,
            options=options,
            jobs=[j for j in self.jobs if j.status == "pending"],
            output_dir=self.config.output_dir,
            conflict_mode=self.config.conflict_mode,
            event_queue=self.event_queue,
        )
        self.worker.start()
        self.queue_panel.set_running(True, paused=False)
        self.statusbar.set_message(f"Memproses {len(self.worker.jobs)} gambar dengan {engine.display_name}…", "info")
        self._render_jobs()

    def _toggle_pause(self) -> None:
        if not self.worker or not self.worker.is_running:
            return
        if self.worker.is_paused:
            self.worker.resume()
        else:
            self.worker.pause()

    def _cancel_batch(self) -> None:
        if not self.worker:
            return
        if not messagebox.askyesno(APP_NAME, "Batalkan batch?", parent=self.root):
            return
        self.worker.cancel()
        self.statusbar.set_message("Membatalkan…", "warning")

    def _open_output_dir(self) -> None:
        target = self.config.output_dir
        if not target:
            done = [j for j in self.jobs if j.output_path]
            if done:
                target = str(done[-1].output_path.parent)
        if not target or not Path(target).exists():
            messagebox.showinfo(APP_NAME, "Folder output belum ada.")
            return
        self._open_in_explorer(target)

    @staticmethod
    def _open_in_explorer(path: str) -> None:
        try:
            if sys.platform.startswith("win"):
                os.startfile(path)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception as exc:  # pragma: no cover - depends on env
            log.warning("Open explorer failed: %s", exc)

    # ------------------------------------------------------------------ Config

    def _on_config_change(self) -> None:
        previous_engine = self.config.engine
        self.sidebar.collect_into(self.config)
        self._save_config_safe()
        if previous_engine != self.config.engine:
            self._refresh_engine_status()
        else:
            self.statusbar.set_engine(self._build_engine()[0].display_name, ok=True)

    def _on_appearance_change(self, mode: str) -> None:
        self.config.appearance_mode = mode
        ctk.set_appearance_mode(mode)
        self._rebuild_palette()

    def _on_accent_change(self, accent: str) -> None:
        self.config.accent_color = accent
        self._rebuild_palette()

    def _rebuild_palette(self) -> None:
        self.palette = theme.palette_for(self.config.appearance_mode, self.config.accent_color)
        self.root.configure(fg_color=self.palette.bg)
        # Rebuild the UI panels (cheapest way to re-skin everything in CTk).
        for child in self.root.winfo_children():
            child.destroy()
        self._build_layout()
        self._register_dnd()
        self._render_jobs()
        self._refresh_engine_status()
        self._save_config_safe()

    def _save_config_safe(self) -> None:
        try:
            self.config.save()
        except OSError as exc:
            log.warning("Could not persist config: %s", exc)

    def _browse_output_dir(self) -> None:
        initial = self.config.output_dir or (
            self.config.recent_output_dirs[0] if self.config.recent_output_dirs else None
        )
        folder = filedialog.askdirectory(
            parent=self.root,
            title="Pilih folder output (kosongkan untuk simpan di samping file sumber)",
            initialdir=initial,
        )
        if folder is None:
            return
        self.sidebar.update_output_dir(folder)
        self.config.output_dir = folder
        if folder:
            self.config.remember_output_dir(folder)
        self._save_config_safe()

    def _browse_realesrgan(self) -> None:
        types = [("Executable", "*.exe *"), ("Semua file", "*.*")]
        initial = self.config.realesrgan_binary or None
        path = filedialog.askopenfilename(
            parent=self.root,
            title="Pilih realesrgan-ncnn-vulkan",
            filetypes=types,
            initialfile=initial,
        )
        if not path:
            return
        # Validate quickly
        confirmed = find_realesrgan_binary(path)
        if confirmed is None:
            messagebox.showerror(APP_NAME, "File tidak ditemukan / tidak valid.", parent=self.root)
            return
        self.config.realesrgan_binary = str(confirmed)
        self.sidebar.update_realesrgan_path(str(confirmed))
        self._save_config_safe()
        self._refresh_engine_status()

    # ------------------------------------------------------------------ Rendering

    def _render_jobs(self) -> None:
        self.queue_panel.render_jobs(self.jobs)
        sel = self.queue_panel.selected_index()
        if sel is not None and 0 <= sel < len(self.jobs):
            self.preview.show_job(self.jobs[sel])

    # ------------------------------------------------------------------ Events

    def _poll_events(self) -> None:
        try:
            while True:
                event = self.event_queue.get_nowait()
                self._handle_event(event)
        except queue.Empty:
            pass
        finally:
            self._poll_after_id = self.root.after(80, self._poll_events)

    def _handle_event(self, event: WorkerEvent) -> None:
        if event.kind == "batch_started":
            self.statusbar.set_message("Batch dimulai.", "info")
            self.queue_panel.set_running(True, paused=False)
        elif event.kind in ("job_started", "job_progress", "job_done", "job_failed", "job_skipped"):
            if event.job:
                self._refresh_job(event.job)
        elif event.kind == "batch_paused":
            self.queue_panel.set_running(True, paused=True)
            self.statusbar.set_message("Dijeda.", "warning")
        elif event.kind == "batch_resumed":
            self.queue_panel.set_running(True, paused=False)
            self.statusbar.set_message("Dilanjutkan.", "info")
        elif event.kind in ("batch_finished", "batch_cancelled"):
            self.queue_panel.set_running(False, paused=False)
            self._render_jobs()
            done = sum(1 for j in self.jobs if j.status == "done")
            failed = sum(1 for j in self.jobs if j.status in ("failed", "cancelled"))
            if event.kind == "batch_cancelled":
                self.statusbar.set_message(f"Batch dibatalkan. {done} selesai, {failed} gagal.", "warning")
            else:
                self.statusbar.set_message(f"Batch selesai. {done} berhasil, {failed} gagal.", "success")
                if self.config.play_sound_on_done:
                    threading.Thread(target=play_done_sound, daemon=True).start()
                if self.config.show_desktop_notification:
                    threading.Thread(
                        target=show_desktop_notification,
                        args=(APP_NAME, f"{done} gambar di-upscale, {failed} gagal."),
                        daemon=True,
                    ).start()
            self.worker = None

    def _refresh_job(self, job: Job) -> None:
        for i, j in enumerate(self.jobs):
            if j is job or j.input_path == job.input_path:
                self.jobs[i] = job
                self.queue_panel.update_job(i, job)
                self.queue_panel.refresh_stats(self.jobs)
                if self.queue_panel.selected_index() == i:
                    self.preview.show_job(job)
                return

    # ------------------------------------------------------------------ Lifecycle

    def _on_close(self) -> None:
        if self.worker and self.worker.is_running:
            if not messagebox.askyesno(
                APP_NAME, "Batch sedang berjalan. Yakin mau keluar?", parent=self.root
            ):
                return
            self.worker.cancel()
            self.worker.join(timeout=2.0)
        if self._poll_after_id:
            with contextlib.suppress(tk.TclError, ValueError):
                self.root.after_cancel(self._poll_after_id)
        self._save_config_safe()
        self.root.destroy()

    def run(self) -> None:
        try:
            self.root.mainloop()
        finally:
            self._save_config_safe()


def run() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    log.info("Starting %s on %s %s", APP_NAME, platform.system(), platform.release())
    app = App()
    app.run()
