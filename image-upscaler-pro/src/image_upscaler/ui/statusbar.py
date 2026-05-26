"""Bottom status bar."""

from __future__ import annotations

import customtkinter as ctk

from . import theme


class StatusBar(ctk.CTkFrame):
    def __init__(self, master, *, palette: theme.Palette) -> None:
        super().__init__(master, fg_color=palette.bg_alt, corner_radius=0, height=32)
        self._palette = palette
        self.grid_columnconfigure(1, weight=1)
        self.grid_propagate(False)

        self.engine_label = ctk.CTkLabel(
            self,
            text="Engine: -",
            font=theme.FONT_TINY,
            text_color=palette.text_muted,
        )
        self.engine_label.grid(row=0, column=0, sticky="w", padx=16)

        self.message_label = ctk.CTkLabel(
            self,
            text="Siap.",
            font=theme.FONT_TINY,
            text_color=palette.text_muted,
        )
        self.message_label.grid(row=0, column=1, sticky="ew")

        self.right_label = ctk.CTkLabel(
            self,
            text="",
            font=theme.FONT_TINY,
            text_color=palette.text_muted,
        )
        self.right_label.grid(row=0, column=2, sticky="e", padx=16)

    def set_engine(self, name: str, ok: bool) -> None:
        glyph = "●" if ok else "○"
        color = self._palette.success if ok else self._palette.warning
        self.engine_label.configure(text=f"{glyph}  {name}", text_color=color)

    def set_message(self, message: str, kind: str = "info") -> None:
        color_map = {
            "info": self._palette.text_muted,
            "success": self._palette.success,
            "warning": self._palette.warning,
            "danger": self._palette.danger,
        }
        self.message_label.configure(text=message, text_color=color_map.get(kind, self._palette.text_muted))

    def set_right(self, text: str) -> None:
        self.right_label.configure(text=text)
