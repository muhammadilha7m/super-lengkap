"""Reusable composite widgets."""

from __future__ import annotations

from collections.abc import Callable

import customtkinter as ctk

from . import theme


class StatCard(ctk.CTkFrame):
    """Compact stat card used in the queue summary row."""

    def __init__(
        self,
        master,
        *,
        label: str,
        value: str = "0",
        accent: str = "#5B5EF4",
        palette: theme.Palette,
    ) -> None:
        super().__init__(master, fg_color=palette.card, corner_radius=12)
        self._palette = palette
        self.grid_columnconfigure(0, weight=1)

        self._bar = ctk.CTkFrame(self, fg_color=accent, height=3, corner_radius=0)
        self._bar.grid(row=0, column=0, sticky="ew", padx=0, pady=(0, 8))

        self._label = ctk.CTkLabel(
            self,
            text=label.upper(),
            font=theme.FONT_TINY,
            text_color=palette.text_muted,
            anchor="w",
        )
        self._label.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 0))

        self._value = ctk.CTkLabel(
            self,
            text=value,
            font=theme.FONT_HEADING,
            text_color=palette.text,
            anchor="w",
        )
        self._value.grid(row=2, column=0, sticky="ew", padx=14, pady=(2, 12))

    def set_value(self, value: str) -> None:
        self._value.configure(text=value)


class IconButton(ctk.CTkButton):
    """A CTk button with a slightly larger emoji glyph."""

    def __init__(
        self,
        master,
        *,
        glyph: str,
        text: str,
        command: Callable[[], None],
        palette: theme.Palette,
        kind: str = "primary",
        width: int = 140,
    ) -> None:
        bg, hover, fg = self._resolve_kind(kind, palette)
        super().__init__(
            master,
            text=f"  {glyph}  {text}",
            command=command,
            width=width,
            height=38,
            corner_radius=10,
            fg_color=bg,
            hover_color=hover,
            text_color=fg,
            font=theme.FONT_LABEL_BOLD,
        )

    @staticmethod
    def _resolve_kind(kind: str, palette: theme.Palette) -> tuple[str, str, str]:
        if kind == "primary":
            return palette.primary, palette.primary_hover, "#FFFFFF"
        if kind == "secondary":
            return palette.card_alt, palette.border, palette.text
        if kind == "success":
            return palette.success, "#0F9E6E", "#FFFFFF"
        if kind == "danger":
            return palette.danger, "#C53030", "#FFFFFF"
        return palette.card_alt, palette.border, palette.text


class SectionTitle(ctk.CTkLabel):
    def __init__(self, master, *, text: str, palette: theme.Palette) -> None:
        super().__init__(
            master,
            text=text.upper(),
            font=theme.FONT_TINY,
            text_color=palette.text_muted,
            anchor="w",
        )


class Hint(ctk.CTkLabel):
    def __init__(self, master, *, text: str, palette: theme.Palette) -> None:
        super().__init__(
            master,
            text=text,
            font=theme.FONT_SMALL,
            text_color=palette.text_muted,
            anchor="w",
            justify="left",
            wraplength=280,
        )
