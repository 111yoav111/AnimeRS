from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QPushButton, QScrollArea,
)
from PyQt6.QtCore import Qt, pyqtSignal

from ui import theme


class _HistoryRow(QFrame):
    """
    Single clickable row in the history list - anime/verdict headline on top,
    search date/time below.
    """
    clicked = pyqtSignal()

    def __init__(self, headline: str, subtitle: str, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(f"""
            QFrame {{
                background: {theme.BG_ELEVATED};
                border: 1px solid {theme.BORDER_DEFAULT};
                border-radius: {theme.RADIUS_BTN}px;
            }}
            QFrame:hover {{
                background: {theme.BG_HOVER};
            }}
        """)

        row_layout = QVBoxLayout(self)
        row_layout.setContentsMargins(14, 10, 14, 10)
        row_layout.setSpacing(2)

        headline_label = QLabel(headline)
        headline_label.setWordWrap(True)
        headline_label.setStyleSheet(f"color: {theme.TEXT_SECONDARY}; font-size: {theme.FONT_SM}px; font-weight: 500; border: none;")
        row_layout.addWidget(headline_label)

        subtitle_label = QLabel(subtitle)
        subtitle_label.setStyleSheet(f"color: {theme.TEXT_GHOST}; font-size: {theme.FONT_XS}px; border: none;")
        row_layout.addWidget(subtitle_label)

    def mousePressEvent(self, event) -> None:
        super().mousePressEvent(event)
        self.clicked.emit()


class HistoryScreen(QWidget):
    """
    Scrollable list of past searches, most recent first.
    Clicking a row re-opens that result on the result screen.
    """
    go_back = pyqtSignal()
    entry_selected = pyqtSignal(dict, str)  # verdict, filename

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(0)

        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(0, 0, 0, 0)

        back_btn = QPushButton("← Back")
        back_btn.setStyleSheet(theme.back_btn_style())
        back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        back_btn.clicked.connect(self.go_back.emit)
        top_bar.addWidget(back_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        top_bar.addStretch()

        title = QLabel("Search history")
        title.setStyleSheet(f"color: {theme.TEXT_PRIMARY}; font-size: {theme.FONT_LG}px; font-weight: 500;")
        top_bar.addWidget(title, alignment=Qt.AlignmentFlag.AlignRight)

        layout.addLayout(top_bar)
        layout.addSpacing(16)

        self._empty_label = QLabel("No searches yet.")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setStyleSheet(f"color: {theme.TEXT_FAINT}; font-size: {theme.FONT_BASE}px;")
        self._empty_label.setVisible(False)
        layout.addWidget(self._empty_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self._list_widget = QWidget()
        self._list_layout = QVBoxLayout(self._list_widget)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(8)
        self._list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        scroll.setWidget(self._list_widget)
        layout.addWidget(scroll, stretch=1)

    # API

    def set_entries(self, entries: list[dict]) -> None:
        """
        Replace the list contents with the given history entries
        (newest first, as returned by the /history endpoint).
        """
        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self._empty_label.setVisible(not entries)

        for entry in entries:
            self._list_layout.addWidget(self._make_row(entry))

    # Helpers

    def _make_row(self, entry: dict) -> _HistoryRow:
        verdict = entry.get("verdict") or {}
        filename = entry.get("filename") or ""

        if verdict.get("found"):
            parts = [verdict.get("anime") or "Unknown"]
            season = verdict.get("season")
            if season:
                parts.append(season)
            episode = verdict.get("episode")
            if episode is not None:
                parts.append(f"Ep {episode}")
            headline = " · ".join(parts)
            timestamp = verdict.get("timestamp") or verdict.get("timestamp_range")
            if timestamp:
                headline += f"  ({timestamp})"
        else:
            headline = f"No match — {filename}" if filename else "No match"

        subtitle = self._format_when(entry.get("searched_at"))

        row = _HistoryRow(headline, subtitle)
        row.clicked.connect(lambda: self.entry_selected.emit(verdict, filename))
        return row

    @staticmethod
    def _format_when(searched_at) -> str:
        if not searched_at:
            return ""
        try:
            return datetime.fromtimestamp(searched_at).strftime("%b %d, %Y · %H:%M")
        except Exception:
            return ""
