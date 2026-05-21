"""Reusable UI widgets: frameless title bar, card, section header, etc."""
from __future__ import annotations

from PySide6.QtCore import Qt, QPoint, Signal
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class TitleBar(QFrame):
    """Frameless window title bar with drag + min/max/close controls."""

    minimize_clicked = Signal()
    maximize_clicked = Signal()
    close_clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("TitleBar")
        self.setFixedHeight(44)

        self._drag_pos: QPoint | None = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(8)

        title = QLabel("Spectrum AI", self)
        title.setObjectName("AppTitle")
        layout.addWidget(title)

        badge = QLabel("v0.1 \u00b7 PRIVATE", self)
        badge.setObjectName("AppBadge")
        layout.addWidget(badge)

        layout.addStretch(1)

        self.btn_min = QPushButton("\u2014", self)
        self.btn_min.setObjectName("WindowControl")
        self.btn_min.setFixedSize(40, 28)
        self.btn_min.clicked.connect(self.minimize_clicked)

        self.btn_max = QPushButton("\u25a1", self)
        self.btn_max.setObjectName("WindowControl")
        self.btn_max.setFixedSize(40, 28)
        self.btn_max.clicked.connect(self.maximize_clicked)

        self.btn_close = QPushButton("\u2715", self)
        self.btn_close.setObjectName("WindowControlClose")
        self.btn_close.setProperty("class", "WindowControl")
        self.btn_close.setObjectName("WindowControl")
        self.btn_close.setFixedSize(40, 28)
        self.btn_close.clicked.connect(self.close_clicked)

        layout.addWidget(self.btn_min)
        layout.addWidget(self.btn_max)
        layout.addWidget(self.btn_close)

    # ----- drag-to-move -------------------------------------------------
    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_pos is not None and event.buttons() & Qt.LeftButton:
            window = self.window()
            if window is not None and not window.isMaximized():
                delta = event.globalPosition().toPoint() - self._drag_pos
                window.move(window.pos() + delta)
                self._drag_pos = event.globalPosition().toPoint()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._drag_pos = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        self.maximize_clicked.emit()
        super().mouseDoubleClickEvent(event)


class Card(QFrame):
    """Rounded card panel."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)


class SectionLabel(QLabel):
    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(text.upper(), parent)
        self.setProperty("class", "section")
        self.setStyleSheet("color: #9a9ac0; font-size: 11px; letter-spacing: 1px;")


class Heading(QLabel):
    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setObjectName("Heading")


def vbox(*widgets: QWidget, margin: int = 8, spacing: int = 8) -> QVBoxLayout:
    layout = QVBoxLayout()
    layout.setContentsMargins(margin, margin, margin, margin)
    layout.setSpacing(spacing)
    for widget in widgets:
        layout.addWidget(widget)
    return layout


def hbox(*widgets: QWidget, margin: int = 0, spacing: int = 8) -> QHBoxLayout:
    layout = QHBoxLayout()
    layout.setContentsMargins(margin, margin, margin, margin)
    layout.setSpacing(spacing)
    for widget in widgets:
        layout.addWidget(widget)
    return layout
