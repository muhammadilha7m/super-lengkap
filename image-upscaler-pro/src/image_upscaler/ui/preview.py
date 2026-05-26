"""Preview panel with a before/after compare slider.

The slider is implemented on a ``tk.Canvas`` so we can clip the "after" image
to the right side of a draggable handle. This works without any extra deps.
"""

from __future__ import annotations

import logging
import tkinter as tk
from pathlib import Path

import customtkinter as ctk
from PIL import Image, ImageOps, ImageTk

from ..constants import JOB_STATUS_DONE
from ..core.job import Job
from . import theme

log = logging.getLogger(__name__)


class PreviewPanel(ctk.CTkFrame):
    """Shows the currently selected image with optional before/after compare."""

    PREVIEW_MAX = 1400

    def __init__(self, master, *, palette: theme.Palette) -> None:
        super().__init__(master, fg_color=palette.card, corner_radius=14)
        self._palette = palette

        self._job: Job | None = None
        self._before_path: Path | None = None
        self._after_path: Path | None = None
        self._before_full: Image.Image | None = None
        self._after_full: Image.Image | None = None
        self._before_disp: Image.Image | None = None
        self._after_disp: Image.Image | None = None
        self._before_tk: ImageTk.PhotoImage | None = None
        self._after_tk: ImageTk.PhotoImage | None = None
        self._handle_x_ratio: float = 0.5
        self._render_size: tuple[int, int] = (0, 0)
        self._dragging: bool = False

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=18, pady=(14, 6))
        header.grid_columnconfigure(1, weight=1)

        self.title_label = ctk.CTkLabel(
            header,
            text="Preview",
            font=theme.FONT_HEADING,
            text_color=palette.text,
            anchor="w",
        )
        self.title_label.grid(row=0, column=0, sticky="w")

        self.meta_label = ctk.CTkLabel(
            header,
            text="Pilih gambar dari antrian untuk melihat preview.",
            font=theme.FONT_SMALL,
            text_color=palette.text_muted,
            anchor="e",
        )
        self.meta_label.grid(row=0, column=1, sticky="e")

        self.canvas = tk.Canvas(
            self,
            bg=palette.card_alt,
            highlightthickness=0,
            bd=0,
        )
        self.canvas.grid(row=1, column=0, sticky="nsew", padx=14, pady=(0, 14))
        self.canvas.bind("<Configure>", self._on_canvas_resize)
        self.canvas.bind("<Button-1>", self._on_canvas_click)
        self.canvas.bind("<B1-Motion>", self._on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", lambda _e: self._end_drag())

        self._show_placeholder("Belum ada preview")

    # ----- Public API -----

    def apply_palette(self, palette: theme.Palette) -> None:
        self._palette = palette
        self.configure(fg_color=palette.card)
        self.canvas.configure(bg=palette.card_alt)
        self.title_label.configure(text_color=palette.text)
        self.meta_label.configure(text_color=palette.text_muted)
        self._redraw()

    def show_job(self, job: Job | None) -> None:
        self._job = job
        if job is None:
            self._before_full = None
            self._after_full = None
            self._before_path = None
            self._after_path = None
            self.title_label.configure(text="Preview")
            self.meta_label.configure(text="Pilih gambar dari antrian.")
            self._show_placeholder("Belum ada preview")
            return

        self._before_path = job.input_path
        self._after_path = (
            job.output_path
            if job.status == JOB_STATUS_DONE and job.output_path and job.output_path.exists()
            else None
        )

        self.title_label.configure(text=job.display_name)
        meta_text = ""
        if self._after_path:
            meta_text = "Seret slider untuk membandingkan sebelum / sesudah →"
        else:
            meta_text = "Status: belum diproses (preview = gambar asli)"
        self.meta_label.configure(text=meta_text)

        try:
            self._before_full = self._load_capped(job.input_path)
        except Exception as exc:  # pragma: no cover - depends on file
            log.warning("Failed to load preview source %s: %s", job.input_path, exc)
            self._before_full = None
            self._show_placeholder("Gagal memuat gambar")
            return

        if self._after_path:
            try:
                self._after_full = self._load_capped(self._after_path)
            except Exception as exc:  # pragma: no cover - depends on file
                log.warning("Failed to load after preview %s: %s", self._after_path, exc)
                self._after_full = None
        else:
            self._after_full = None

        self._handle_x_ratio = 0.5
        self._redraw()

    # ----- Canvas events -----

    def _on_canvas_resize(self, _event: tk.Event) -> None:
        self._redraw()

    def _on_canvas_click(self, event: tk.Event) -> None:
        if self._after_full is None:
            return
        self._dragging = True
        self._update_handle_from_event(event)

    def _on_canvas_drag(self, event: tk.Event) -> None:
        if self._after_full is None or not self._dragging:
            return
        self._update_handle_from_event(event)

    def _end_drag(self) -> None:
        self._dragging = False

    def _update_handle_from_event(self, event: tk.Event) -> None:
        width = max(1, self.canvas.winfo_width())
        ratio = max(0.0, min(1.0, event.x / width))
        self._handle_x_ratio = ratio
        self._draw_handle()

    # ----- Rendering -----

    def _redraw(self) -> None:
        cw = max(1, self.canvas.winfo_width())
        ch = max(1, self.canvas.winfo_height())
        if cw <= 2 or ch <= 2:
            return
        self.canvas.delete("all")
        if self._before_full is None:
            self._show_placeholder("Belum ada preview")
            return

        self._before_disp, render_size = self._fit(self._before_full, cw, ch)
        self._render_size = render_size
        self._before_tk = ImageTk.PhotoImage(self._before_disp)
        x = (cw - render_size[0]) // 2
        y = (ch - render_size[1]) // 2
        self.canvas.create_image(x, y, anchor="nw", image=self._before_tk, tags=("before",))

        if self._after_full is not None:
            after_resized = self._after_full.resize(render_size, Image.Resampling.LANCZOS)
            self._after_disp = after_resized
            self._after_tk = ImageTk.PhotoImage(after_resized)
            self.canvas.create_image(x, y, anchor="nw", image=self._after_tk, tags=("after",))
            self._apply_clip(x, y, render_size)
            self._draw_handle()
        else:
            self._draw_no_after_overlay(x, y, render_size)

    def _apply_clip(self, x: int, y: int, size: tuple[int, int]) -> None:
        # Tk canvas can't do real clipping, so we re-paste the "before" image
        # on top of the LEFT half of the after image to fake the slider.
        if self._before_disp is None or self._after_disp is None:
            return
        ratio = self._handle_x_ratio
        cut = int(size[0] * ratio)
        if cut <= 0:
            return
        left_slice = self._before_disp.crop((0, 0, cut, size[1]))
        self._left_slice_tk = ImageTk.PhotoImage(left_slice)
        self.canvas.create_image(x, y, anchor="nw", image=self._left_slice_tk, tags=("clip",))

    def _draw_handle(self) -> None:
        if self._after_full is None or self._before_disp is None:
            return
        cw = max(1, self.canvas.winfo_width())
        ch = max(1, self.canvas.winfo_height())
        size = self._render_size
        x = (cw - size[0]) // 2
        y = (ch - size[1]) // 2

        # Re-apply the clip so the visible slice updates as we drag.
        self.canvas.delete("clip")
        self.canvas.delete("handle")
        self._apply_clip(x, y, size)

        handle_x = x + int(size[0] * self._handle_x_ratio)
        accent = self._palette.primary
        # Vertical handle line
        self.canvas.create_line(
            handle_x,
            y,
            handle_x,
            y + size[1],
            fill=accent,
            width=2,
            tags=("handle",),
        )
        # Center knob
        r = 14
        self.canvas.create_oval(
            handle_x - r,
            y + size[1] // 2 - r,
            handle_x + r,
            y + size[1] // 2 + r,
            fill=accent,
            outline="#FFFFFF",
            width=2,
            tags=("handle",),
        )
        # Labels
        self.canvas.create_text(
            x + 12,
            y + 12,
            anchor="nw",
            text="BEFORE",
            fill="#FFFFFF",
            font=theme.FONT_TINY,
            tags=("handle",),
        )
        self.canvas.create_text(
            x + size[0] - 12,
            y + 12,
            anchor="ne",
            text="AFTER",
            fill="#FFFFFF",
            font=theme.FONT_TINY,
            tags=("handle",),
        )

    def _draw_no_after_overlay(self, x: int, y: int, size: tuple[int, int]) -> None:
        self.canvas.create_text(
            x + 12,
            y + size[1] - 18,
            anchor="sw",
            text="Belum di-upscale — jalankan batch untuk melihat hasil.",
            fill="#FFFFFF",
            font=theme.FONT_SMALL,
        )

    def _show_placeholder(self, text: str) -> None:
        self.canvas.delete("all")
        cw = max(1, self.canvas.winfo_width())
        ch = max(1, self.canvas.winfo_height())
        self.canvas.create_text(
            cw // 2,
            ch // 2,
            text=text,
            fill=self._palette.text_muted,
            font=theme.FONT_LABEL,
            anchor="center",
        )

    @staticmethod
    def _fit(img: Image.Image, max_w: int, max_h: int) -> tuple[Image.Image, tuple[int, int]]:
        iw, ih = img.size
        if iw == 0 or ih == 0:
            return img, (1, 1)
        scale = min(max_w / iw, max_h / ih, 1.0)
        new_size = (max(1, int(iw * scale)), max(1, int(ih * scale)))
        resized = img.resize(new_size, Image.Resampling.LANCZOS) if scale < 1.0 else img.copy()
        return resized, new_size

    @classmethod
    def _load_capped(cls, path: Path) -> Image.Image:
        with Image.open(path) as raw:
            img = ImageOps.exif_transpose(raw)
            if img.mode not in ("RGB", "RGBA"):
                img = img.convert("RGBA" if "A" in img.mode else "RGB")
            iw, ih = img.size
            max_side = cls.PREVIEW_MAX
            if max(iw, ih) > max_side:
                scale = max_side / max(iw, ih)
                img = img.resize(
                    (max(1, int(iw * scale)), max(1, int(ih * scale))),
                    Image.Resampling.LANCZOS,
                )
            return img.copy()
