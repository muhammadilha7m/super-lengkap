"""Modern dark + glass stylesheet for PySide6."""
from __future__ import annotations


PRIMARY = "#7c4dff"
ACCENT = "#00e5ff"
ACCENT_PINK = "#ff4081"
BG = "#0a0a14"
BG_PANEL = "#11111d"
BG_PANEL_ALT = "#15152a"
BG_CARD = "#1a1a2e"
TEXT = "#e8e8ff"
TEXT_DIM = "#9a9ac0"
BORDER = "#252540"


STYLE_SHEET = f"""
* {{
    color: {TEXT};
    font-family: "Inter", "Segoe UI", "Helvetica Neue", sans-serif;
    font-size: 13px;
}}

QMainWindow, QWidget#MainContainer {{
    background-color: {BG};
}}

QFrame#TitleBar {{
    background-color: {BG_PANEL};
    border-bottom: 1px solid {BORDER};
}}

QLabel#AppTitle {{
    color: {TEXT};
    font-weight: 600;
    font-size: 14px;
    padding-left: 12px;
}}

QLabel#AppBadge {{
    color: {ACCENT};
    font-weight: 500;
    font-size: 11px;
    padding: 2px 8px;
    background-color: rgba(0, 229, 255, 0.10);
    border: 1px solid rgba(0, 229, 255, 0.30);
    border-radius: 8px;
}}

QPushButton {{
    background-color: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 8px 14px;
    color: {TEXT};
}}
QPushButton:hover {{ background-color: #22223c; border-color: {PRIMARY}; }}
QPushButton:pressed {{ background-color: #2a2a48; }}
QPushButton:disabled {{ color: {TEXT_DIM}; border-color: {BORDER}; }}

QPushButton#PrimaryButton {{
    background-color: {PRIMARY};
    border: 1px solid {PRIMARY};
    color: white;
    font-weight: 600;
}}
QPushButton#PrimaryButton:hover {{
    background-color: #9b71ff;
    border-color: #9b71ff;
}}

QPushButton#AccentButton {{
    background-color: transparent;
    border: 1px solid {ACCENT};
    color: {ACCENT};
}}
QPushButton#AccentButton:hover {{
    background-color: rgba(0, 229, 255, 0.12);
}}

QPushButton#DangerButton {{
    background-color: transparent;
    border: 1px solid {ACCENT_PINK};
    color: {ACCENT_PINK};
}}
QPushButton#WindowControl {{
    background-color: transparent;
    border: none;
    border-radius: 6px;
    padding: 4px 10px;
    color: {TEXT_DIM};
    font-size: 16px;
}}
QPushButton#WindowControl:hover {{
    background-color: rgba(255, 255, 255, 0.06);
    color: {TEXT};
}}
QPushButton#WindowControlClose:hover {{
    background-color: rgba(255, 64, 129, 0.18);
    color: {ACCENT_PINK};
}}

QFrame#Sidebar {{
    background-color: {BG_PANEL};
    border-right: 1px solid {BORDER};
}}
QFrame#RightPanel {{
    background-color: {BG_PANEL};
    border-left: 1px solid {BORDER};
}}
QFrame#PreviewFrame {{
    background-color: #050510;
    border: 1px solid {BORDER};
    border-radius: 12px;
}}
QFrame#Card {{
    background-color: {BG_PANEL_ALT};
    border: 1px solid {BORDER};
    border-radius: 10px;
}}

QLabel.section {{
    color: {TEXT_DIM};
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-top: 6px;
}}

QLabel#Heading {{
    font-size: 15px;
    font-weight: 600;
    color: {TEXT};
}}

QComboBox, QLineEdit, QSpinBox, QDoubleSpinBox, QPlainTextEdit, QTextEdit {{
    background-color: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 6px 8px;
    color: {TEXT};
    selection-background-color: {PRIMARY};
}}
QComboBox:focus, QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus,
QPlainTextEdit:focus, QTextEdit:focus {{
    border-color: {ACCENT};
}}
QComboBox::drop-down {{ border: none; }}
QComboBox QAbstractItemView {{
    background-color: {BG_CARD};
    selection-background-color: {PRIMARY};
    border: 1px solid {BORDER};
    color: {TEXT};
}}

QSlider::groove:horizontal {{
    height: 4px;
    background: {BORDER};
    border-radius: 2px;
}}
QSlider::sub-page:horizontal {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {ACCENT}, stop:1 {PRIMARY});
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background: white;
    width: 14px;
    height: 14px;
    border-radius: 7px;
    margin: -6px 0;
}}

QProgressBar {{
    background-color: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 8px;
    text-align: center;
    color: {TEXT};
    height: 18px;
}}
QProgressBar::chunk {{
    border-radius: 7px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {ACCENT}, stop:1 {PRIMARY});
}}

QListWidget {{
    background-color: transparent;
    border: none;
    color: {TEXT};
    outline: 0;
}}
QListWidget::item {{
    padding: 8px 10px;
    border-radius: 6px;
    margin: 2px 4px;
}}
QListWidget::item:selected {{
    background-color: rgba(124, 77, 255, 0.20);
    color: {TEXT};
}}
QListWidget::item:hover {{
    background-color: rgba(255, 255, 255, 0.04);
}}

QScrollBar:vertical {{
    background: transparent;
    width: 8px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {BORDER};
    border-radius: 4px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{ background: {PRIMARY}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    background: none; height: 0;
}}

QTabWidget::pane {{ border: none; }}
QTabBar::tab {{
    background-color: transparent;
    padding: 8px 14px;
    color: {TEXT_DIM};
    border: none;
}}
QTabBar::tab:selected {{
    color: {TEXT};
    border-bottom: 2px solid {ACCENT};
}}

QStatusBar {{
    background-color: {BG_PANEL};
    border-top: 1px solid {BORDER};
    color: {TEXT_DIM};
}}

QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{
    width: 16px; height: 16px;
    border: 1px solid {BORDER};
    border-radius: 4px;
    background-color: {BG_CARD};
}}
QCheckBox::indicator:checked {{
    background-color: {ACCENT};
    border-color: {ACCENT};
}}

QToolTip {{
    background-color: {BG_PANEL};
    color: {TEXT};
    border: 1px solid {BORDER};
    padding: 4px 8px;
    border-radius: 6px;
}}
"""
