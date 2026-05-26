"""Queue panel — list of pending/running/done jobs with toolbar."""

from __future__ import annotations

from collections.abc import Callable

import customtkinter as ctk

from ..constants import (
    JOB_STATUS_CANCELLED,
    JOB_STATUS_DONE,
    JOB_STATUS_FAILED,
    JOB_STATUS_PENDING,
    JOB_STATUS_RUNNING,
    JOB_STATUS_SKIPPED,
)
from ..core.job import Job
from . import theme
from .widgets import IconButton, StatCard

_STATUS_GLYPH = {
    JOB_STATUS_PENDING: "○",
    JOB_STATUS_RUNNING: "●",
    JOB_STATUS_DONE: "✓",
    JOB_STATUS_FAILED: "✕",
    JOB_STATUS_SKIPPED: "⤼",
    JOB_STATUS_CANCELLED: "⊘",
}

_STATUS_LABEL = {
    JOB_STATUS_PENDING: "Menunggu",
    JOB_STATUS_RUNNING: "Memproses…",
    JOB_STATUS_DONE: "Selesai",
    JOB_STATUS_FAILED: "Gagal",
    JOB_STATUS_SKIPPED: "Dilewati",
    JOB_STATUS_CANCELLED: "Dibatalkan",
}


class QueuePanel(ctk.CTkFrame):
    def __init__(
        self,
        master,
        *,
        palette: theme.Palette,
        on_add_files: Callable[[], None],
        on_add_folder: Callable[[], None],
        on_clear: Callable[[], None],
        on_remove_selected: Callable[[], None],
        on_select: Callable[[int], None],
        on_start: Callable[[], None],
        on_pause_resume: Callable[[], None],
        on_cancel: Callable[[], None],
        on_open_output: Callable[[], None],
    ) -> None:
        super().__init__(master, fg_color=palette.bg, corner_radius=0)
        self._palette = palette
        self._on_select = on_select
        self._row_widgets: list[QueueRow] = []
        self._selected_index: int | None = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # ---- Toolbar ----
        toolbar = ctk.CTkFrame(self, fg_color="transparent")
        toolbar.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 12))
        toolbar.grid_columnconfigure(2, weight=1)

        left_group = ctk.CTkFrame(toolbar, fg_color="transparent")
        left_group.grid(row=0, column=0, sticky="w")

        self.btn_add = IconButton(
            left_group,
            glyph="＋",
            text="Tambah File",
            command=on_add_files,
            palette=palette,
            kind="primary",
            width=130,
        )
        self.btn_add.grid(row=0, column=0, padx=(0, 6))

        self.btn_folder = IconButton(
            left_group,
            glyph="🗀",
            text="Folder",
            command=on_add_folder,
            palette=palette,
            kind="secondary",
            width=110,
        )
        self.btn_folder.grid(row=0, column=1, padx=(0, 6))

        self.btn_remove = IconButton(
            left_group,
            glyph="−",
            text="Hapus",
            command=on_remove_selected,
            palette=palette,
            kind="secondary",
            width=90,
        )
        self.btn_remove.grid(row=0, column=2, padx=(0, 6))

        self.btn_clear = IconButton(
            left_group,
            glyph="🗑",
            text="Clear",
            command=on_clear,
            palette=palette,
            kind="secondary",
            width=90,
        )
        self.btn_clear.grid(row=0, column=3, padx=(0, 6))

        self.btn_open_output = IconButton(
            left_group,
            glyph="↗",
            text="Output",
            command=on_open_output,
            palette=palette,
            kind="secondary",
            width=100,
        )
        self.btn_open_output.grid(row=0, column=4, padx=(0, 6))

        right_group = ctk.CTkFrame(toolbar, fg_color="transparent")
        right_group.grid(row=0, column=99, sticky="e")

        self.btn_start = IconButton(
            right_group,
            glyph="▶",
            text="Mulai",
            command=on_start,
            palette=palette,
            kind="success",
            width=110,
        )
        self.btn_start.grid(row=0, column=0, padx=(0, 6))

        self.btn_pause = IconButton(
            right_group,
            glyph="⏸",
            text="Jeda",
            command=on_pause_resume,
            palette=palette,
            kind="secondary",
            width=90,
        )
        self.btn_pause.grid(row=0, column=1, padx=(0, 6))

        self.btn_cancel = IconButton(
            right_group,
            glyph="■",
            text="Batal",
            command=on_cancel,
            palette=palette,
            kind="danger",
            width=90,
        )
        self.btn_cancel.grid(row=0, column=2)

        # ---- Stats row ----
        stats = ctk.CTkFrame(self, fg_color="transparent")
        stats.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 12))
        for i in range(4):
            stats.grid_columnconfigure(i, weight=1)
        self.card_total = StatCard(stats, label="Total", value="0", accent=palette.info, palette=palette)
        self.card_done = StatCard(stats, label="Selesai", value="0", accent=palette.success, palette=palette)
        self.card_failed = StatCard(stats, label="Gagal", value="0", accent=palette.danger, palette=palette)
        self.card_remaining = StatCard(stats, label="Sisa", value="0", accent=palette.warning, palette=palette)
        self.card_total.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.card_done.grid(row=0, column=1, sticky="ew", padx=(0, 8))
        self.card_failed.grid(row=0, column=2, sticky="ew", padx=(0, 8))
        self.card_remaining.grid(row=0, column=3, sticky="ew")

        # ---- Scrollable list ----
        self.list_frame = ctk.CTkScrollableFrame(
            self,
            fg_color=palette.card,
            corner_radius=14,
            label_text="",
        )
        self.list_frame.grid(row=2, column=0, sticky="nsew", padx=20, pady=(0, 8))
        self.list_frame.grid_columnconfigure(0, weight=1)

        # Empty-state placeholder
        self.empty_label = ctk.CTkLabel(
            self.list_frame,
            text=(
                "Tarik & lepas gambar atau folder ke sini\n"
                "atau klik “＋ Tambah File” untuk memulai."
            ),
            font=theme.FONT_LABEL,
            text_color=palette.text_muted,
            justify="center",
        )
        self.empty_label.grid(row=0, column=0, pady=80, padx=40)

        # Overall progress bar
        self.progress_bar = ctk.CTkProgressBar(
            self,
            progress_color=palette.primary,
            fg_color=palette.card,
            height=10,
            corner_radius=6,
        )
        self.progress_bar.grid(row=3, column=0, sticky="ew", padx=20, pady=(0, 8))
        self.progress_bar.set(0.0)

        self.set_running(False, paused=False)

    # ----- Public API -----

    def render_jobs(self, jobs: list[Job]) -> None:
        for w in self._row_widgets:
            w.destroy()
        self._row_widgets.clear()
        if self.empty_label.winfo_exists():
            self.empty_label.grid_forget()

        if not jobs:
            self.empty_label.grid(row=0, column=0, pady=80, padx=40)
        else:
            for index, job in enumerate(jobs):
                row = QueueRow(
                    self.list_frame,
                    palette=self._palette,
                    job=job,
                    index=index,
                    on_click=lambda i=index: self._handle_select(i),
                )
                row.grid(row=index, column=0, sticky="ew", padx=8, pady=4)
                self._row_widgets.append(row)
            self._restore_selection_highlight()

        self._refresh_stats(jobs)

    def update_job(self, index: int, job: Job) -> None:
        if 0 <= index < len(self._row_widgets):
            self._row_widgets[index].refresh(job)

    def refresh_stats(self, jobs: list[Job]) -> None:
        self._refresh_stats(jobs)

    def set_overall_progress(self, value: float) -> None:
        self.progress_bar.set(max(0.0, min(1.0, value)))

    def set_running(self, running: bool, paused: bool) -> None:
        self.btn_start.configure(state="disabled" if running else "normal")
        if running:
            self.btn_pause.configure(
                state="normal",
                text="  ▶  Lanjutkan" if paused else "  ⏸  Jeda",
            )
            self.btn_cancel.configure(state="normal")
        else:
            self.btn_pause.configure(state="disabled", text="  ⏸  Jeda")
            self.btn_cancel.configure(state="disabled")

    def selected_index(self) -> int | None:
        return self._selected_index

    def select_index(self, index: int | None) -> None:
        self._selected_index = index
        self._restore_selection_highlight()

    # ----- Internal -----

    def _handle_select(self, index: int) -> None:
        self.select_index(index)
        self._on_select(index)

    def _restore_selection_highlight(self) -> None:
        for i, row in enumerate(self._row_widgets):
            row.set_selected(i == self._selected_index)

    def _refresh_stats(self, jobs: list[Job]) -> None:
        total = len(jobs)
        done = sum(1 for j in jobs if j.status == JOB_STATUS_DONE)
        failed = sum(
            1 for j in jobs if j.status in (JOB_STATUS_FAILED, JOB_STATUS_CANCELLED)
        )
        skipped = sum(1 for j in jobs if j.status == JOB_STATUS_SKIPPED)
        remaining = total - done - failed - skipped
        self.card_total.set_value(str(total))
        self.card_done.set_value(str(done))
        self.card_failed.set_value(str(failed))
        self.card_remaining.set_value(str(remaining))
        if total:
            self.set_overall_progress((done + failed + skipped) / total)
        else:
            self.set_overall_progress(0.0)


class QueueRow(ctk.CTkFrame):
    def __init__(
        self,
        master,
        *,
        palette: theme.Palette,
        job: Job,
        index: int,
        on_click: Callable[[], None],
    ) -> None:
        super().__init__(master, fg_color=palette.card_alt, corner_radius=10, height=64)
        self._palette = palette
        self._on_click = on_click
        self._selected = False
        self.grid_propagate(False)
        self.grid_columnconfigure(1, weight=1)

        self.status_dot = ctk.CTkLabel(
            self,
            text=_STATUS_GLYPH.get(job.status, "○"),
            font=(theme.FONT_FAMILY, 18, "bold"),
            text_color=self._status_color(job.status),
            width=36,
        )
        self.status_dot.grid(row=0, column=0, rowspan=2, padx=(12, 10), pady=8, sticky="w")

        self.name_label = ctk.CTkLabel(
            self,
            text=job.display_name,
            font=theme.FONT_LABEL_BOLD,
            text_color=palette.text,
            anchor="w",
        )
        self.name_label.grid(row=0, column=1, sticky="ew", padx=(0, 8), pady=(8, 0))

        self.detail_label = ctk.CTkLabel(
            self,
            text=self._detail_text(job),
            font=theme.FONT_SMALL,
            text_color=palette.text_muted,
            anchor="w",
        )
        self.detail_label.grid(row=1, column=1, sticky="ew", padx=(0, 8), pady=(0, 8))

        self.progress = ctk.CTkProgressBar(
            self,
            progress_color=palette.primary,
            fg_color=palette.card,
            height=4,
            corner_radius=2,
            width=160,
        )
        self.progress.grid(row=0, column=2, rowspan=2, padx=(0, 16), pady=8, sticky="e")
        self.progress.set(job.progress)

        # Bind click on all child widgets so the entire row is clickable.
        for w in (self, self.status_dot, self.name_label, self.detail_label, self.progress):
            w.bind("<Button-1>", lambda _e: self._on_click())

    def refresh(self, job: Job) -> None:
        self.status_dot.configure(
            text=_STATUS_GLYPH.get(job.status, "○"),
            text_color=self._status_color(job.status),
        )
        self.name_label.configure(text=job.display_name)
        self.detail_label.configure(text=self._detail_text(job))
        self.progress.set(job.progress)

    def set_selected(self, selected: bool) -> None:
        if self._selected == selected:
            return
        self._selected = selected
        self.configure(
            fg_color=self._palette.primary if selected else self._palette.card_alt,
        )
        text_color = "#FFFFFF" if selected else self._palette.text
        muted = "#E5E7EB" if selected else self._palette.text_muted
        self.name_label.configure(text_color=text_color)
        self.detail_label.configure(text_color=muted)

    def _detail_text(self, job: Job) -> str:
        status = _STATUS_LABEL.get(job.status, job.status)
        if job.status == JOB_STATUS_DONE and job.output_path:
            return f"{status} · {job.output_path.name}"
        if job.message:
            return f"{status} · {job.message}"
        return status

    def _status_color(self, status: str) -> str:
        p = self._palette
        return {
            JOB_STATUS_PENDING: p.text_muted,
            JOB_STATUS_RUNNING: p.info,
            JOB_STATUS_DONE: p.success,
            JOB_STATUS_FAILED: p.danger,
            JOB_STATUS_SKIPPED: p.warning,
            JOB_STATUS_CANCELLED: p.warning,
        }.get(status, p.text_muted)
