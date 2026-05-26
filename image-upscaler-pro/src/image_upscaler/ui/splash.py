"""Splash screen — branded animated intro shown while the main app initialises.

The splash is a borderless Toplevel that:
- Fades in (alpha 0.0 -> 1.0)
- Shows logo, "Image Upscaler Pro By BASIS", a tagline, and an animated loading bar
- Stays visible for a minimum duration, then fades out and destroys itself.
"""

from __future__ import annotations

import contextlib
import math
import tkinter as tk
from collections.abc import Callable

from ..constants import APP_VERSION

SPLASH_W = 560
SPLASH_H = 340
MIN_DURATION_MS = 2200
FADE_IN_MS = 380
FADE_OUT_MS = 280
BAR_STEP_MS = 16

BG_GRADIENT_TOP = "#0B0E1A"
BG_GRADIENT_BOT = "#1B1248"
ACCENT_1 = "#5B5EF4"
ACCENT_2 = "#06B6D4"
ACCENT_3 = "#EC4899"
TEXT_PRIMARY = "#FFFFFF"
TEXT_MUTED = "#A5A8B8"


class Splash:
    """Borderless animated splash window."""

    def __init__(
        self,
        master: tk.Misc | None = None,
        *,
        on_close: Callable[[], None] | None = None,
    ) -> None:
        self._on_close = on_close
        self._closed = False
        self._bar_phase = 0.0
        self._title_alpha = 0.0
        self._tagline_alpha = 0.0

        self.top = tk.Toplevel(master)
        self.top.withdraw()
        self.top.overrideredirect(True)
        with contextlib.suppress(tk.TclError):
            self.top.attributes("-topmost", True)
        with contextlib.suppress(tk.TclError):
            self.top.attributes("-alpha", 0.0)

        self._center()

        self.canvas = tk.Canvas(
            self.top,
            width=SPLASH_W,
            height=SPLASH_H,
            bd=0,
            highlightthickness=0,
            bg=BG_GRADIENT_TOP,
        )
        self.canvas.pack(fill="both", expand=True)

        self._draw_background()
        self._draw_logo()
        self._draw_text()
        self._draw_bar()
        self._draw_footer()

        self.top.deiconify()
        self._start_time_ms = self._now_ms()
        self._fade_in()
        self._animate_bar()

    # ------------------------------------------------------------------ Geometry

    def _center(self) -> None:
        self.top.update_idletasks()
        sw = self.top.winfo_screenwidth()
        sh = self.top.winfo_screenheight()
        x = (sw - SPLASH_W) // 2
        y = (sh - SPLASH_H) // 2
        self.top.geometry(f"{SPLASH_W}x{SPLASH_H}+{x}+{y}")

    # ------------------------------------------------------------------ Drawing

    def _draw_background(self) -> None:
        steps = 80
        for i in range(steps):
            t = i / (steps - 1)
            color = _blend(BG_GRADIENT_TOP, BG_GRADIENT_BOT, t)
            y0 = int(SPLASH_H * i / steps)
            y1 = int(SPLASH_H * (i + 1) / steps)
            self.canvas.create_rectangle(0, y0, SPLASH_W, y1, fill=color, outline=color)

        for cx, cy, r, color in (
            (90, 60, 130, ACCENT_1),
            (470, 80, 110, ACCENT_2),
            (430, 290, 140, ACCENT_3),
        ):
            for k in range(8, 0, -1):
                shade = _blend(color, BG_GRADIENT_BOT, 1 - k / 12)
                self.canvas.create_oval(
                    cx - r * k / 8,
                    cy - r * k / 8,
                    cx + r * k / 8,
                    cy + r * k / 8,
                    fill=shade,
                    outline=shade,
                )

    def _draw_logo(self) -> None:
        cx, cy = SPLASH_W // 2, 110
        size = 64
        ring_r = size // 2 + 8
        self.canvas.create_oval(
            cx - ring_r,
            cy - ring_r,
            cx + ring_r,
            cy + ring_r,
            outline=ACCENT_2,
            width=2,
        )
        self.canvas.create_polygon(
            cx - size // 2,
            cy + size // 2,
            cx,
            cy - size // 2,
            cx + size // 2,
            cy + size // 2,
            fill=ACCENT_1,
            outline="",
        )
        self.canvas.create_polygon(
            cx - size // 3,
            cy + size // 2,
            cx + size // 6,
            cy - size // 6,
            cx + size // 2,
            cy + size // 2,
            fill=ACCENT_3,
            outline="",
        )
        self.canvas.create_oval(
            cx + size // 5 - 5,
            cy - size // 3 - 5,
            cx + size // 5 + 5,
            cy - size // 3 + 5,
            fill=TEXT_PRIMARY,
            outline="",
        )

    def _draw_text(self) -> None:
        self._title_id = self.canvas.create_text(
            SPLASH_W // 2,
            205,
            text="Image Upscaler Pro",
            fill=TEXT_PRIMARY,
            font=("Segoe UI", 22, "bold"),
        )
        self._by_id = self.canvas.create_text(
            SPLASH_W // 2,
            236,
            text="By BASIS",
            fill=ACCENT_2,
            font=("Segoe UI", 13, "italic"),
        )
        self._tag_id = self.canvas.create_text(
            SPLASH_W // 2,
            260,
            text="AI & klasik · batch siap pakai",
            fill=TEXT_MUTED,
            font=("Segoe UI", 10),
        )

    def _draw_bar(self) -> None:
        bar_w = 360
        bar_h = 6
        bx = (SPLASH_W - bar_w) // 2
        by = 295
        self._bar_track = self.canvas.create_rectangle(
            bx,
            by,
            bx + bar_w,
            by + bar_h,
            fill="#2A2F3F",
            outline="",
        )
        self._bar_fill = self.canvas.create_rectangle(
            bx,
            by,
            bx + 40,
            by + bar_h,
            fill=ACCENT_1,
            outline="",
        )
        self._bar_geom = (bx, by, bar_w, bar_h)

    def _draw_footer(self) -> None:
        self.canvas.create_text(
            SPLASH_W // 2,
            322,
            text=f"v{APP_VERSION}  ·  memuat…",
            fill=TEXT_MUTED,
            font=("Segoe UI", 9),
        )

    # ------------------------------------------------------------------ Animation

    def _now_ms(self) -> int:
        return int(self.top.tk.call("clock", "milliseconds"))

    def _fade_in(self) -> None:
        if self._closed:
            return
        elapsed = self._now_ms() - self._start_time_ms
        alpha = min(1.0, elapsed / FADE_IN_MS)
        with contextlib.suppress(tk.TclError):
            self.top.attributes("-alpha", alpha)
        if alpha < 1.0:
            self.top.after(16, self._fade_in)

    def _animate_bar(self) -> None:
        if self._closed:
            return
        self._bar_phase = (self._bar_phase + 0.04) % 1.0
        bx, by, bar_w, bar_h = self._bar_geom
        seg_w = 90
        travel = bar_w + seg_w
        pos = self._bar_phase * travel - seg_w
        x0 = max(bx, bx + pos)
        x1 = min(bx + bar_w, bx + pos + seg_w)
        if x1 > x0:
            self.canvas.coords(self._bar_fill, x0, by, x1, by + bar_h)
        pulse = 0.5 + 0.5 * math.sin(self._bar_phase * 2 * math.pi)
        color = _blend(ACCENT_1, ACCENT_2, pulse)
        self.canvas.itemconfigure(self._bar_fill, fill=color)
        self.top.after(BAR_STEP_MS, self._animate_bar)

    def _fade_out(self, on_done: Callable[[], None]) -> None:
        start = self._now_ms()

        def step() -> None:
            if self._closed:
                return
            t = (self._now_ms() - start) / FADE_OUT_MS
            alpha = max(0.0, 1.0 - t)
            with contextlib.suppress(tk.TclError):
                self.top.attributes("-alpha", alpha)
            if alpha > 0.0:
                self.top.after(16, step)
            else:
                on_done()

        step()

    # ------------------------------------------------------------------ Public API

    def close(self) -> None:
        """Fade the splash out then destroy it; respects the minimum duration."""
        if self._closed:
            return
        elapsed = self._now_ms() - self._start_time_ms
        delay = max(0, MIN_DURATION_MS - elapsed)

        def begin_fade() -> None:
            self._fade_out(self._destroy)

        self.top.after(delay, begin_fade)

    def _destroy(self) -> None:
        if self._closed:
            return
        self._closed = True
        with contextlib.suppress(tk.TclError):
            self.top.destroy()
        if self._on_close is not None:
            self._on_close()


# ---------------------------------------------------------------------- Helpers


def _blend(hex_a: str, hex_b: str, t: float) -> str:
    t = max(0.0, min(1.0, t))
    a = _hex_to_rgb(hex_a)
    b = _hex_to_rgb(hex_b)
    r = round(a[0] + (b[0] - a[0]) * t)
    g = round(a[1] + (b[1] - a[1]) * t)
    bl = round(a[2] + (b[2] - a[2]) * t)
    return f"#{r:02X}{g:02X}{bl:02X}"


def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
