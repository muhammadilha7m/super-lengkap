"""Left sidebar — engine, scale, output, theme controls."""

from __future__ import annotations

from collections.abc import Callable

import customtkinter as ctk

from ..config import AppConfig
from ..constants import (
    APP_NAME,
    APP_VERSION,
    CONFLICT_MODES,
    ENGINE_CHOICES,
    ENGINE_REALESRGAN,
    OUTPUT_FORMATS,
    REALESRGAN_MODEL_SCALES,
    REALESRGAN_MODELS,
    SCALE_PRESETS,
)
from . import theme
from .widgets import Hint, SectionTitle


class Sidebar(ctk.CTkScrollableFrame):
    """Vertical settings panel on the left side of the window.

    Uses a scrollable frame so the panel stays usable on shorter screens
    or when the OS taskbar would otherwise clip the bottom controls.
    """

    def __init__(
        self,
        master,
        *,
        config: AppConfig,
        palette: theme.Palette,
        on_change: Callable[[], None],
        on_browse_output: Callable[[], None],
        on_browse_realesrgan: Callable[[], None],
        on_appearance_change: Callable[[str], None],
        on_accent_change: Callable[[str], None],
    ) -> None:
        super().__init__(
            master,
            fg_color=palette.bg_alt,
            corner_radius=0,
            width=320,
            scrollbar_fg_color=palette.bg_alt,
            scrollbar_button_color=palette.border,
            scrollbar_button_hover_color=palette.primary_hover,
        )
        self._config = config
        self._palette = palette
        self._on_change = on_change

        self.grid_columnconfigure(0, weight=1)

        row = 0
        self._header(palette).grid(row=row, column=0, sticky="ew", padx=20, pady=(22, 16))
        row += 1

        SectionTitle(self, text="Engine", palette=palette).grid(
            row=row, column=0, sticky="ew", padx=20, pady=(0, 6)
        )
        row += 1
        self.engine_var = ctk.StringVar(value=config.engine)
        self.engine_menu = ctk.CTkOptionMenu(
            self,
            values=list(ENGINE_CHOICES),
            variable=self.engine_var,
            command=lambda _v: self._emit(),
            fg_color=palette.card,
            button_color=palette.primary,
            button_hover_color=palette.primary_hover,
            text_color=palette.text,
            dropdown_fg_color=palette.card,
            dropdown_text_color=palette.text,
            corner_radius=10,
            height=36,
            font=theme.FONT_LABEL,
        )
        self.engine_menu.grid(row=row, column=0, sticky="ew", padx=20, pady=(0, 8))
        row += 1
        self._engine_hint = Hint(
            self,
            text="Lanczos: cepat, dijalankan oleh Pillow. Real-ESRGAN: lebih tajam, butuh binary.",
            palette=palette,
        )
        self._engine_hint.grid(row=row, column=0, sticky="ew", padx=20, pady=(0, 14))
        row += 1

        SectionTitle(self, text="Real-ESRGAN Model", palette=palette).grid(
            row=row, column=0, sticky="ew", padx=20, pady=(0, 6)
        )
        row += 1
        self.model_var = ctk.StringVar(value=config.realesrgan_model)
        self.model_menu = ctk.CTkOptionMenu(
            self,
            values=list(REALESRGAN_MODELS),
            variable=self.model_var,
            command=self._on_model_change,
            fg_color=palette.card,
            button_color=palette.secondary,
            button_hover_color=palette.primary_hover,
            text_color=palette.text,
            dropdown_fg_color=palette.card,
            dropdown_text_color=palette.text,
            corner_radius=10,
            height=36,
            font=theme.FONT_LABEL,
        )
        self.model_menu.grid(row=row, column=0, sticky="ew", padx=20, pady=(0, 4))
        row += 1

        self._model_hint = Hint(
            self,
            text=self._model_hint_text(config.realesrgan_model),
            palette=palette,
        )
        self._model_hint.grid(row=row, column=0, sticky="ew", padx=20, pady=(0, 10))
        row += 1

        self.realesrgan_path_var = ctk.StringVar(value=config.realesrgan_binary)
        self.realesrgan_path_btn = ctk.CTkButton(
            self,
            text="Pilih binary realesrgan-ncnn-vulkan…",
            command=on_browse_realesrgan,
            fg_color=palette.card,
            hover_color=palette.border,
            text_color=palette.text,
            corner_radius=10,
            height=34,
            font=theme.FONT_SMALL,
        )
        self.realesrgan_path_btn.grid(row=row, column=0, sticky="ew", padx=20, pady=(0, 14))
        row += 1

        SectionTitle(self, text="Skala", palette=palette).grid(
            row=row, column=0, sticky="ew", padx=20, pady=(0, 6)
        )
        row += 1
        self.scale_var = ctk.IntVar(value=config.scale)
        scale_row = ctk.CTkFrame(self, fg_color="transparent")
        scale_row.grid(row=row, column=0, sticky="ew", padx=20, pady=(0, 14))
        for i in range(len(SCALE_PRESETS)):
            scale_row.grid_columnconfigure(i, weight=1)
        self._scale_buttons: list[ctk.CTkRadioButton] = []
        for i, val in enumerate(SCALE_PRESETS):
            btn = ctk.CTkRadioButton(
                scale_row,
                text=f"{val}x",
                variable=self.scale_var,
                value=val,
                command=self._emit,
                fg_color=palette.primary,
                hover_color=palette.primary_hover,
                text_color=palette.text,
                font=theme.FONT_LABEL_BOLD,
            )
            btn.grid(row=0, column=i, sticky="w", padx=(0, 8))
            self._scale_buttons.append(btn)
        row += 1
        # Apply initial enable/disable based on engine + model.
        self._apply_scale_constraints()

        SectionTitle(self, text="Format Output", palette=palette).grid(
            row=row, column=0, sticky="ew", padx=20, pady=(0, 6)
        )
        row += 1
        self.format_var = ctk.StringVar(value=config.output_format)
        self.format_menu = ctk.CTkOptionMenu(
            self,
            values=list(OUTPUT_FORMATS),
            variable=self.format_var,
            command=lambda _v: self._emit(),
            fg_color=palette.card,
            button_color=palette.primary,
            button_hover_color=palette.primary_hover,
            text_color=palette.text,
            dropdown_fg_color=palette.card,
            dropdown_text_color=palette.text,
            corner_radius=10,
            height=36,
            font=theme.FONT_LABEL,
        )
        self.format_menu.grid(row=row, column=0, sticky="ew", padx=20, pady=(0, 8))
        row += 1

        self.jpeg_quality_var = ctk.IntVar(value=config.jpeg_quality)
        self.jpeg_quality_label = ctk.CTkLabel(
            self,
            text=f"Kualitas JPEG/WEBP: {config.jpeg_quality}",
            font=theme.FONT_SMALL,
            text_color=palette.text_muted,
            anchor="w",
        )
        self.jpeg_quality_label.grid(row=row, column=0, sticky="ew", padx=20, pady=(0, 2))
        row += 1
        self.jpeg_quality_slider = ctk.CTkSlider(
            self,
            from_=50,
            to=100,
            number_of_steps=50,
            variable=self.jpeg_quality_var,
            command=self._on_quality_slider,
            progress_color=palette.primary,
            button_color=palette.primary,
            button_hover_color=palette.primary_hover,
        )
        self.jpeg_quality_slider.grid(row=row, column=0, sticky="ew", padx=20, pady=(0, 14))
        row += 1

        SectionTitle(self, text="Folder Output", palette=palette).grid(
            row=row, column=0, sticky="ew", padx=20, pady=(0, 6)
        )
        row += 1
        self.output_dir_var = ctk.StringVar(value=config.output_dir)
        self.output_dir_btn = ctk.CTkButton(
            self,
            text=self._output_dir_label(),
            command=on_browse_output,
            fg_color=palette.card,
            hover_color=palette.border,
            text_color=palette.text,
            corner_radius=10,
            height=34,
            font=theme.FONT_SMALL,
        )
        self.output_dir_btn.grid(row=row, column=0, sticky="ew", padx=20, pady=(0, 14))
        row += 1

        SectionTitle(self, text="Jika File Sudah Ada", palette=palette).grid(
            row=row, column=0, sticky="ew", padx=20, pady=(0, 6)
        )
        row += 1
        self.conflict_var = ctk.StringVar(value=config.conflict_mode)
        self.conflict_menu = ctk.CTkOptionMenu(
            self,
            values=list(CONFLICT_MODES),
            variable=self.conflict_var,
            command=lambda _v: self._emit(),
            fg_color=palette.card,
            button_color=palette.primary,
            button_hover_color=palette.primary_hover,
            text_color=palette.text,
            dropdown_fg_color=palette.card,
            dropdown_text_color=palette.text,
            corner_radius=10,
            height=36,
            font=theme.FONT_LABEL,
        )
        self.conflict_menu.grid(row=row, column=0, sticky="ew", padx=20, pady=(0, 14))
        row += 1

        self.exif_var = ctk.BooleanVar(value=config.preserve_exif)
        self.exif_chk = ctk.CTkCheckBox(
            self,
            text="Pertahankan EXIF (untuk JPEG)",
            variable=self.exif_var,
            command=self._emit,
            fg_color=palette.primary,
            hover_color=palette.primary_hover,
            text_color=palette.text,
            font=theme.FONT_SMALL,
        )
        self.exif_chk.grid(row=row, column=0, sticky="ew", padx=20, pady=(0, 6))
        row += 1

        self.recursive_var = ctk.BooleanVar(value=config.recursive_folder_scan)
        self.recursive_chk = ctk.CTkCheckBox(
            self,
            text="Scan folder rekursif saat drop folder",
            variable=self.recursive_var,
            command=self._emit,
            fg_color=palette.primary,
            hover_color=palette.primary_hover,
            text_color=palette.text,
            font=theme.FONT_SMALL,
        )
        self.recursive_chk.grid(row=row, column=0, sticky="ew", padx=20, pady=(0, 6))
        row += 1

        self.sound_var = ctk.BooleanVar(value=config.play_sound_on_done)
        self.sound_chk = ctk.CTkCheckBox(
            self,
            text="Bunyikan saat batch selesai",
            variable=self.sound_var,
            command=self._emit,
            fg_color=palette.primary,
            hover_color=palette.primary_hover,
            text_color=palette.text,
            font=theme.FONT_SMALL,
        )
        self.sound_chk.grid(row=row, column=0, sticky="ew", padx=20, pady=(0, 6))
        row += 1

        self.notif_var = ctk.BooleanVar(value=config.show_desktop_notification)
        self.notif_chk = ctk.CTkCheckBox(
            self,
            text="Tampilkan notifikasi desktop",
            variable=self.notif_var,
            command=self._emit,
            fg_color=palette.primary,
            hover_color=palette.primary_hover,
            text_color=palette.text,
            font=theme.FONT_SMALL,
        )
        self.notif_chk.grid(row=row, column=0, sticky="ew", padx=20, pady=(0, 18))
        row += 1

        SectionTitle(self, text="Tampilan", palette=palette).grid(
            row=row, column=0, sticky="ew", padx=20, pady=(0, 6)
        )
        row += 1

        appearance_row = ctk.CTkFrame(self, fg_color="transparent")
        appearance_row.grid(row=row, column=0, sticky="ew", padx=20, pady=(0, 8))
        appearance_row.grid_columnconfigure(0, weight=1)
        self.appearance_var = ctk.StringVar(value=config.appearance_mode)
        self.appearance_menu = ctk.CTkSegmentedButton(
            appearance_row,
            values=["dark", "light", "white", "system"],
            variable=self.appearance_var,
            command=on_appearance_change,
            fg_color=palette.card,
            selected_color=palette.primary,
            selected_hover_color=palette.primary_hover,
            unselected_color=palette.card,
            unselected_hover_color=palette.border,
            text_color=palette.text,
            font=theme.FONT_SMALL,
            height=32,
            corner_radius=10,
        )
        self.appearance_menu.grid(row=0, column=0, sticky="ew")
        row += 1

        accent_row = ctk.CTkFrame(self, fg_color="transparent")
        accent_row.grid(row=row, column=0, sticky="ew", padx=20, pady=(0, 16))
        accent_row.grid_columnconfigure(0, weight=1)
        self.accent_var = ctk.StringVar(value=config.accent_color)
        self.accent_menu = ctk.CTkSegmentedButton(
            accent_row,
            values=["blue", "purple", "green"],
            variable=self.accent_var,
            command=on_accent_change,
            fg_color=palette.card,
            selected_color=palette.primary,
            selected_hover_color=palette.primary_hover,
            unselected_color=palette.card,
            unselected_hover_color=palette.border,
            text_color=palette.text,
            font=theme.FONT_SMALL,
            height=32,
            corner_radius=10,
        )
        self.accent_menu.grid(row=0, column=0, sticky="ew")
        row += 1

        ctk.CTkLabel(
            self,
            text=f"v{APP_VERSION}  •  © 2025",
            font=theme.FONT_TINY,
            text_color=palette.text_muted,
        ).grid(row=row, column=0, sticky="s", padx=20, pady=(16, 18))
        self.grid_rowconfigure(row, weight=1)

    def _header(self, palette: theme.Palette) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.grid_columnconfigure(1, weight=1)
        logo = ctk.CTkLabel(
            frame,
            text="◆",
            font=(theme.FONT_FAMILY, 32, "bold"),
            text_color=palette.primary,
            width=44,
        )
        logo.grid(row=0, column=0, rowspan=2, sticky="w")
        ctk.CTkLabel(
            frame,
            text=APP_NAME,
            font=theme.FONT_TITLE,
            text_color=palette.text,
            anchor="w",
        ).grid(row=0, column=1, sticky="w", padx=(8, 0))
        ctk.CTkLabel(
            frame,
            text="Upscale gambar AI & klasik · batch siap",
            font=theme.FONT_SMALL,
            text_color=palette.text_muted,
            anchor="w",
        ).grid(row=1, column=1, sticky="w", padx=(8, 0))
        return frame

    def _output_dir_label(self) -> str:
        value = self.output_dir_var.get() or ""
        if not value:
            return "📁  Sama dengan file sumber"
        short = value
        if len(short) > 36:
            short = "…" + short[-35:]
        return f"📁  {short}"

    def update_output_dir(self, new_dir: str) -> None:
        self.output_dir_var.set(new_dir)
        self.output_dir_btn.configure(text=self._output_dir_label())

    def update_realesrgan_path(self, new_path: str) -> None:
        self.realesrgan_path_var.set(new_path)
        if new_path:
            short = new_path
            if len(short) > 36:
                short = "…" + short[-35:]
            self.realesrgan_path_btn.configure(text=f"⚙  {short}")
        else:
            self.realesrgan_path_btn.configure(text="Pilih binary realesrgan-ncnn-vulkan…")

    def _on_quality_slider(self, value: float) -> None:
        self.jpeg_quality_label.configure(text=f"Kualitas JPEG/WEBP: {int(value)}")
        self._emit()

    def _on_model_change(self, _value: str) -> None:
        self._model_hint.configure(text=self._model_hint_text(self.model_var.get()))
        self._apply_scale_constraints()
        self._emit()

    @staticmethod
    def _model_hint_text(model: str) -> str:
        allowed = REALESRGAN_MODEL_SCALES.get(model)
        if not allowed:
            return ""
        allowed_str = "/".join(f"{s}x" for s in allowed)
        if len(allowed) == 1:
            return f"Model '{model}' hanya mendukung {allowed_str}."
        return f"Model '{model}' mendukung {allowed_str}."

    def _apply_scale_constraints(self) -> None:
        """Disable scale radio buttons that the current engine/model can't do."""
        if not hasattr(self, "_scale_buttons"):
            return
        engine = self.engine_var.get() if hasattr(self, "engine_var") else ""
        allowed: tuple[int, ...] | None = None
        if engine == ENGINE_REALESRGAN:
            allowed = REALESRGAN_MODEL_SCALES.get(self.model_var.get())
        for btn, val in zip(self._scale_buttons, SCALE_PRESETS, strict=True):
            if allowed is None or val in allowed:
                btn.configure(state="normal")
            else:
                btn.configure(state="disabled")
        # If current selection is no longer allowed, switch to the first valid one.
        if allowed is not None and self.scale_var.get() not in allowed:
            self.scale_var.set(allowed[0])

    def _emit(self) -> None:
        self._apply_scale_constraints()
        self._on_change()

    def collect_into(self, config: AppConfig) -> None:
        config.engine = self.engine_var.get()
        config.realesrgan_model = self.model_var.get()
        config.scale = int(self.scale_var.get())
        config.output_format = self.format_var.get()
        config.jpeg_quality = int(self.jpeg_quality_var.get())
        config.webp_quality = int(self.jpeg_quality_var.get())
        config.output_dir = self.output_dir_var.get()
        config.conflict_mode = self.conflict_var.get()
        config.preserve_exif = bool(self.exif_var.get())
        config.recursive_folder_scan = bool(self.recursive_var.get())
        config.play_sound_on_done = bool(self.sound_var.get())
        config.show_desktop_notification = bool(self.notif_var.get())
        config.appearance_mode = self.appearance_var.get()
        config.accent_color = self.accent_var.get()
        config.realesrgan_binary = self.realesrgan_path_var.get()

    def set_engine_warning(self, message: str) -> None:
        if message:
            self._engine_hint.configure(text=f"⚠  {message}", text_color=self._palette.warning)
        else:
            self._engine_hint.configure(
                text="Lanczos: cepat, dijalankan oleh Pillow. Real-ESRGAN: lebih tajam, butuh binary.",
                text_color=self._palette.text_muted,
            )

    def show_realesrgan_controls(self, show: bool) -> None:
        self.model_menu.configure(state="normal" if show else "disabled")
        self.realesrgan_path_btn.configure(state="normal" if show else "disabled")
        self.set_engine_warning(
            "" if self.engine_var.get() != ENGINE_REALESRGAN else self._engine_hint.cget("text")
        )
