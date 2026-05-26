"""Visual theme — colors, fonts, spacing."""

from __future__ import annotations

from dataclasses import dataclass

# Accent palettes for the three offered accent options.
ACCENTS: dict[str, dict[str, str]] = {
    "blue": {
        "primary": "#5B5EF4",
        "primary_hover": "#4346D6",
        "secondary": "#06B6D4",
    },
    "purple": {
        "primary": "#8B5CF6",
        "primary_hover": "#7C3AED",
        "secondary": "#EC4899",
    },
    "green": {
        "primary": "#10B981",
        "primary_hover": "#059669",
        "secondary": "#06B6D4",
    },
}

SEMANTIC: dict[str, str] = {
    "success": "#10B981",
    "warning": "#F59E0B",
    "danger": "#EF4444",
    "info": "#3B82F6",
}


@dataclass(frozen=True)
class Palette:
    """Resolved colors for the active appearance + accent."""

    bg: str
    bg_alt: str
    card: str
    card_alt: str
    border: str
    text: str
    text_muted: str
    primary: str
    primary_hover: str
    secondary: str
    success: str
    warning: str
    danger: str
    info: str


def palette_for(appearance: str, accent: str) -> Palette:
    accent_key = accent if accent in ACCENTS else "blue"
    a = ACCENTS[accent_key]
    is_dark = appearance == "dark"
    if is_dark:
        bg = "#0F1117"
        bg_alt = "#13151D"
        card = "#1A1D27"
        card_alt = "#222633"
        border = "#2A2F3F"
        text = "#E5E7EB"
        text_muted = "#9CA3AF"
    else:
        bg = "#F1F5F9"
        bg_alt = "#E2E8F0"
        card = "#FFFFFF"
        card_alt = "#F8FAFC"
        border = "#CBD5E1"
        text = "#0F172A"
        text_muted = "#475569"
    return Palette(
        bg=bg,
        bg_alt=bg_alt,
        card=card,
        card_alt=card_alt,
        border=border,
        text=text,
        text_muted=text_muted,
        primary=a["primary"],
        primary_hover=a["primary_hover"],
        secondary=a["secondary"],
        **SEMANTIC,
    )


FONT_FAMILY = "Segoe UI"  # Windows default; CTk will substitute on other OSes.

FONT_TITLE = (FONT_FAMILY, 22, "bold")
FONT_HEADING = (FONT_FAMILY, 14, "bold")
FONT_LABEL = (FONT_FAMILY, 12)
FONT_LABEL_BOLD = (FONT_FAMILY, 12, "bold")
FONT_SMALL = (FONT_FAMILY, 11)
FONT_TINY = (FONT_FAMILY, 10)
FONT_MONO = ("Cascadia Mono", 11)
