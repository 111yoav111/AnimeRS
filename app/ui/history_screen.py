import base64
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QPushButton, QScrollArea, QApplication,
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QPainter, QPixmap

from ui import theme
from ui.background_paint import draw_collage_background


class _HistoryRow(QFrame):
    """
    Single clickable row in the history list - anime/verdict headline on top,
    search date/time below.

    translucent=True gives the row a see-through background (same treatment
    as the result screen's card) so a collage behind it stays visible.
    """
    clicked = pyqtSignal()

    def __init__(self, headline: str, subtitle: str, translucent: bool = False, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        if translucent:
            bg = "rgba(17, 17, 21, 130)"
            bg_hover = "rgba(34, 34, 48, 190)"
        else:
            bg = theme.BG_ELEVATED
            bg_hover = theme.BG_HOVER
        self.setStyleSheet(f"""
            QFrame {{
                background: {bg};
                border: 1px solid {theme.BORDER_DEFAULT};
                border-radius: {theme.RADIUS_BTN}px;
            }}
            QFrame:hover {{
                background: {bg_hover};
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

    def __init__(
        self, title: str = "Search history", empty_text: str = "No searches yet.",
        collage_background: bool = False, show_filenames: bool = False,
        batch_actions: bool = False, parent=None,
    ):
        super().__init__(parent)


        self._collage_background = collage_background
        self._show_filenames = show_filenames
        self._batch_actions = batch_actions
        self._bg_pixmaps: list[QPixmap] = []
        self._entries: list[dict] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(0)

        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(0, 0, 0, 0)

        if batch_actions:
            # Same look and behavior as the result screen's "Copy result",
            # but copies every row of the batch at once.
            self._copy_btn = QPushButton("Copy results")
            self._copy_btn.setStyleSheet(f"""
                QPushButton {{
                    background: none;
                    border: none;
                    color: {theme.TEXT_MUTED};
                    font-size: {theme.FONT_MD}px;
                }}
                QPushButton:hover {{
                    color: {theme.TEXT_PRIMARY};
                }}
            """)
            self._copy_btn.setFixedHeight(28)
            self._copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self._copy_btn.clicked.connect(self._on_copy_results)
            top_bar.addWidget(self._copy_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        else:
            back_btn = QPushButton("← Back")
            back_btn.setStyleSheet(theme.back_btn_style())
            back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            back_btn.clicked.connect(self.go_back.emit)
            top_bar.addWidget(back_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        top_bar.addStretch()

        title_label = QLabel(title)
        title_label.setStyleSheet(f"color: {theme.TEXT_PRIMARY}; font-size: {theme.FONT_LG}px; font-weight: 500;")
        top_bar.addWidget(title_label, alignment=Qt.AlignmentFlag.AlignRight)

        layout.addLayout(top_bar)
        layout.addSpacing(16)

        self._empty_label = QLabel(empty_text)
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setStyleSheet(f"color: {theme.TEXT_FAINT}; font-size: {theme.FONT_BASE}px;")
        self._empty_label.setVisible(False)
        layout.addWidget(self._empty_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        scroll.viewport().setStyleSheet("background: transparent;")

        self._list_widget = QWidget()
        self._list_layout = QVBoxLayout(self._list_widget)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(8)
        self._list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        scroll.setWidget(self._list_widget)
        layout.addWidget(scroll, stretch=1)

        if batch_actions:
            # Bottom action, same style and placement as the result screen's
            # "Try another file" - resets and returns to the upload screen.
            layout.addSpacing(14)
            try_more = QPushButton("↺  Try more files")
            try_more.setStyleSheet(theme.try_again_btn_style())
            try_more.clicked.connect(self.go_back.emit)
            layout.addWidget(try_more)

    # Layout events

    def paintEvent(self, event) -> None:
        """
        Batch results only: paint a collage of this batch's own cover
        images behind the list of results.
        """
        if self._collage_background and self._bg_pixmaps:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
            draw_collage_background(painter, self.rect(), self._bg_pixmaps)
            painter.end()
        super().paintEvent(event)

    # API

    def set_entries(self, entries: list[dict]) -> None:
        """
        Replace the list contents with the given history entries
        (newest first, as returned by the /history endpoint, or a batch
        run's own in-memory results).
        """
        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self._entries = list(entries)
        self._empty_label.setVisible(not entries)

        for entry in entries:
            self._list_layout.addWidget(self._make_row(entry))

        if self._collage_background:
            self._bg_pixmaps = self._extract_covers(entries)
        self.update()

    # Helpers

    @staticmethod
    def _extract_covers(entries: list[dict]) -> list[QPixmap]:
        pixmaps = []
        for entry in entries:
            cover_b64 = (entry.get("verdict") or {}).get("cover_image_b64")
            if not cover_b64:
                continue
            try:
                pixmap = QPixmap()
                pixmap.loadFromData(base64.b64decode(cover_b64))
                if not pixmap.isNull():
                    pixmaps.append(pixmap)
            except Exception:
                continue
        return pixmaps

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
            if self._show_filenames and filename:
                headline = f"{filename}  →  {headline}"
        elif verdict.get("error"):
            # if error happened -> "no match found" result.
            headline = f"Error — {filename}: {verdict['error']}" if filename else f"Error: {verdict['error']}"
        else:
            headline = f"No match — {filename}" if filename else "No match"

        subtitle = self._format_when(entry.get("searched_at"))

        row = _HistoryRow(headline, subtitle, translucent=self._collage_background)
        row.clicked.connect(lambda: self.entry_selected.emit(verdict, filename))
        return row

    def _on_copy_results(self) -> None:
        """
        Copy every batch row to the clipboard as plain text, one line per
        file, in the same format as the result screen's "Copy result".
        """
        if not self._entries:
            return
        text = "\n".join(self._entry_copy_line(entry) for entry in self._entries)
        QApplication.clipboard().setText(text)
        self._copy_btn.setText("Copied!")
        QTimer.singleShot(1500, lambda: self._copy_btn.setText("Copy results"))

    @staticmethod
    def _entry_copy_line(entry: dict) -> str:
        verdict = entry.get("verdict") or {}
        filename = entry.get("filename") or "Unknown file"

        if verdict.get("found"):
            parts = [verdict.get("anime") or "Unknown"]
            season = verdict.get("season")
            if season:
                parts.append(season)
            episode = verdict.get("episode")
            if episode is not None:
                parts.append(f"Episode {episode}")
            line = " - ".join(parts)
            timestamp = verdict.get("timestamp") or verdict.get("timestamp_range")
            if timestamp:
                line += f" ({timestamp})"
        elif verdict.get("error"):
            line = f"Error: {verdict['error']}"
        else:
            line = "No match"

        return f"{filename} -> {line}"

    @staticmethod
    def _format_when(searched_at) -> str:
        if not searched_at:
            return ""
        try:
            return datetime.fromtimestamp(searched_at).strftime("%b %d, %Y · %H:%M")
        except Exception:
            return ""
