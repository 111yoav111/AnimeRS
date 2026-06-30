import base64

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QPushButton, QProgressBar, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, QRect
from PyQt6.QtGui import QPixmap, QPainter, QLinearGradient, QColor

from ui import theme


class ResultScreen(QWidget):
    # Emits when user clicks back or try again
    go_back = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self._bg_pixmap = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(0)

        # Back btn
        back_btn = QPushButton("← Search again")
        back_btn.setStyleSheet(theme.back_btn_style())
        back_btn.setFixedHeight(28)
        back_btn.clicked.connect(self.go_back.emit)
        layout.addWidget(back_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        layout.addSpacing(20)

        # Result card - like 50%-transparent so the banner shows through
        self._card = QFrame()
        self._card.setObjectName("result_card")
        self._card.setStyleSheet(theme.result_card_style(transparent=True))
        card_layout = QVBoxLayout(self._card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        result_top = QFrame()
        result_top.setObjectName("result_hero")
        result_top.setStyleSheet(f"""
            QFrame#result_hero {{
                background: rgba(20, 20, 24, 130);
                border-bottom: 1px solid {theme.BORDER_SUBTLE};
            }}
        """)
        hero_layout = QHBoxLayout(result_top)
        hero_layout.setContentsMargins(18, 18, 18, 18)
        hero_layout.setSpacing(16)
        hero_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Cover — shows the anime cover image when available, falls back to a TV emoji
        self._cover = QFrame()
        self._cover.setFixedSize(theme.COVER_W, theme.COVER_H)
        self._cover.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                    stop:0 {theme.BG_ELEVATED}, stop:1 {theme.BG_SURFACE});
                border: 1px solid {theme.BORDER_DEFAULT};
                border-radius: 8px;
            }}
        """)
        cover_layout = QVBoxLayout(self._cover)
        cover_layout.setContentsMargins(0, 0, 0, 0)
        self._cover_label = QLabel("📺")
        self._cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._cover_label.setStyleSheet(f"color: {theme.TEXT_DEEP}; font-size: 22px; border: none;")
        cover_layout.addWidget(self._cover_label)
        hero_layout.addWidget(self._cover, alignment=Qt.AlignmentFlag.AlignTop)

        # Meta column
        meta = QWidget()
        meta_layout = QVBoxLayout(meta)
        meta_layout.setContentsMargins(0, 0, 0, 0)
        meta_layout.setSpacing(0)
        meta_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Confidence badge
        self._confidence_badge = QLabel()
        self._confidence_badge.setFixedHeight(22)
        meta_layout.addWidget(self._confidence_badge, alignment=Qt.AlignmentFlag.AlignLeft)

        meta_layout.addSpacing(8)

        # Anime title
        self._title_label = QLabel()
        self._title_label.setStyleSheet(f"""
            QLabel {{
                color: {theme.TEXT_PRIMARY};
                font-size: {theme.FONT_XL}px;
                font-weight: 500;
            }}
        """)
        self._title_label.setMaximumWidth(240)
        self._title_label.setWordWrap(False)
        self._title_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        meta_layout.addWidget(self._title_label)

        meta_layout.addSpacing(2)

        # Native title
        self._native_label = QLabel()
        self._native_label.setStyleSheet(f"color: {theme.TEXT_GHOST}; font-size: {theme.FONT_SM}px;")
        meta_layout.addWidget(self._native_label)

        meta_layout.addSpacing(12)

        # Badges row
        self._badges_row = QHBoxLayout()
        self._badges_row.setSpacing(6)
        self._badges_row.setAlignment(Qt.AlignmentFlag.AlignLeft)
        meta_layout.addLayout(self._badges_row)

        hero_layout.addWidget(meta)
        card_layout.addWidget(result_top)

        # Stats section
        stats_widget = QWidget()
        stats_widget.setStyleSheet("background: rgba(17, 17, 21, 130);")
        stats_layout = QHBoxLayout(stats_widget)
        stats_layout.setContentsMargins(18, 14, 18, 14)
        stats_layout.setSpacing(10)

        self._stat_similarity  = self._make_stat("Similarity",    "-", "avg across frames")
        self._stat_frames      = self._make_stat("Frames agreed", "-", "consensus vote")
        self._stat_input       = self._make_stat("Input type",    "-", "")

        for stat in (self._stat_similarity, self._stat_frames, self._stat_input):
            stats_layout.addWidget(stat)

        card_layout.addWidget(stats_widget)

        # Similarity bar
        sim_widget = QWidget()
        sim_widget.setStyleSheet("background: rgba(17, 17, 21, 130);")
        sim_layout = QVBoxLayout(sim_widget)
        sim_layout.setContentsMargins(18, 0, 18, 18)
        sim_layout.setSpacing(6)

        sim_label = QLabel("Match confidence")
        sim_label.setStyleSheet(f"""
            QLabel {{
                color: {theme.TEXT_GHOST};
                font-size: {theme.FONT_XS}px;
                text-transform: uppercase;
                letter-spacing: 1px;
            }}
        """)
        sim_layout.addWidget(sim_label)

        self._sim_bar = QProgressBar()
        self._sim_bar.setTextVisible(False)
        self._sim_bar.setFixedHeight(4)
        self._sim_bar.setMaximum(100)
        self._sim_bar.setValue(0)
        self._sim_bar.setStyleSheet(theme.progress_bar_style())
        sim_layout.addWidget(self._sim_bar)

        self._sim_pct = QLabel("0%")
        self._sim_pct.setStyleSheet(f"color: {theme.ACCENT}; font-size: {theme.FONT_SM}px;")
        sim_layout.addWidget(self._sim_pct)

        card_layout.addWidget(sim_widget)

        layout.addWidget(self._card)

        layout.addSpacing(14)

        # No match label (hidden by default)
        self._no_match = QLabel("No match found.\ntrace.moe couldn't identify this file.")
        self._no_match.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._no_match.setStyleSheet(f"""
            QLabel {{
                color: {theme.TEXT_FAINT};
                font-size: {theme.FONT_BASE}px;
                line-height: 1.6;
            }}
        """)
        self._no_match.setVisible(False)
        layout.addWidget(self._no_match)

        layout.addSpacing(6)

        # Quota reminder (hidden until triggered every N searches)
        self._quota_reminder = QLabel("")
        self._quota_reminder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._quota_reminder.setStyleSheet(f"color: {theme.CONFIDENCE_LOW_TEXT}; font-size: {theme.FONT_XS}px;")
        self._quota_reminder.setVisible(False)
        layout.addWidget(self._quota_reminder)

        layout.addSpacing(4)

        # Low quota warning (hidden until remaining searches drop low)
        self._quota_low_warning = QLabel("")
        self._quota_low_warning.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._quota_low_warning.setStyleSheet(f"color: {theme.CONFIDENCE_LOW_TEXT}; font-size: {theme.FONT_XS}px; font-weight: 600;")
        self._quota_low_warning.setVisible(False)
        layout.addWidget(self._quota_low_warning)

        layout.addSpacing(6)

        # Try again btn
        try_again = QPushButton("↺  Try another file")
        try_again.setStyleSheet(theme.try_again_btn_style())
        try_again.clicked.connect(self.go_back.emit)
        layout.addWidget(try_again)

        layout.addStretch()

    # Layout events

    def paintEvent(self, event) -> None:
        """
        Paint the banner as the background, scaled to *cover* the whole screen. 

        Scaling happens here, against self.rect(), so the banner always fill the screen.
        """
        if self._bg_pixmap is not None and not self._bg_pixmap.isNull():
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

            target = self.rect()
            src = self._bg_pixmap
            src_w, src_h = src.width(), src.height()

            if src_w > 0 and src_h > 0 and target.width() > 0 and target.height() > 0:
                target_ratio = target.width() / target.height()
                src_ratio = src_w / src_h

                # widget's aspect ratio -> classic cover crop.
                if src_ratio > target_ratio:
                    # Source too wide: crop left/right.
                    crop_w = int(round(src_h * target_ratio))
                    crop_x = (src_w - crop_w) // 2
                    src_rect = QRect(crop_x, 0, crop_w, src_h)
                else:
                    # Source too tall: crop top/bottom.
                    crop_h = int(round(src_w / target_ratio))
                    crop_y = (src_h - crop_h) // 2
                    src_rect = QRect(0, crop_y, src_w, crop_h)

                # Scale that crop to exactly fill the widget. Passing the target
                # rect (not a fixed pixel size) guarantees a full fill every time.
                painter.drawPixmap(target, src, src_rect)

                # Dark gradient overlay for text contrast.
                gradient = QLinearGradient(0, 0, 0, target.height())
                gradient.setColorAt(0.0, QColor(13, 13, 15, 210))
                gradient.setColorAt(0.35, QColor(13, 13, 15, 120))
                gradient.setColorAt(0.65, QColor(13, 13, 15, 140))
                gradient.setColorAt(1.0, QColor(13, 13, 15, 220))
                painter.fillRect(target, gradient)

            painter.end()
        super().paintEvent(event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        # paintEvent reads the live size, so just trigger a repaint.
        self.update()

    # API

    def show_result(self, verdict: dict, filename: str = "") -> None:
        """
        Populate the screen with data from the API verdict.
        Called by main_window after the worker finishes.
        """
        if not verdict.get("found"):
            self._card.setVisible(False)
            self._no_match.setVisible(True)
            self._quota_reminder.setVisible(False)
            self._quota_low_warning.setVisible(False)
            self._set_background(None)
            return

        self._card.setVisible(True)
        self._no_match.setVisible(False)

        # Confidence badge
        confident = verdict.get("confident", False)
        badge_text = "● High confidence" if confident else "● Low confidence"
        self._confidence_badge.setText(badge_text)
        self._confidence_badge.setStyleSheet(theme.confidence_badge_style(high=confident))

        # Titles
        title = (
            verdict.get("anime") or
            verdict.get("Romaji") or
            verdict.get("Native Title") or
            "Unknown"
        )
        self._title_label.setText(title)
        self._title_label.setToolTip(title)

        native = verdict.get("Native Title", "")
        self._native_label.setText(native if native and native != "Unknown" else "")

        # Cover image is used in TWO places:
        #   1. the thumbnail inside the card
        #   2. scaled up to fill the screen as the background
        # The banner from the API is ignored.
        cover_b64 = verdict.get("cover_image_b64")
        self._set_cover(cover_b64)
        self._set_background(cover_b64)

        # Clear old badges
        while self._badges_row.count():
            item = self._badges_row.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Episode badge
        episode = verdict.get("episode")
        if episode is not None:
            ep_badge = QLabel(f"Episode {episode}")
            ep_badge.setStyleSheet(theme.badge_ep_style())
            self._badges_row.addWidget(ep_badge)

        # Timestamp badge (still image)
        timestamp = verdict.get("timestamp")
        if timestamp:
            ts_badge = QLabel(f"⏱ {timestamp}")
            ts_badge.setStyleSheet(theme.badge_ts_style())
            self._badges_row.addWidget(ts_badge)

        # Range badge (video/GIF)
        ts_range = verdict.get("timestamp_range")
        if ts_range:
            range_badge = QLabel(f"⏱ {ts_range}")
            range_badge.setStyleSheet(theme.badge_range_style())
            self._badges_row.addWidget(range_badge)

        # Stats
        similarity = verdict.get("similarity", 0)
        frames_agreed = verdict.get("frames_agreed", 0)
        frames_total = verdict.get("frames_total", 0)
        is_video = verdict.get("timestamp_range") is not None

        self._update_stat(self._stat_similarity, f"{similarity}%", "avg across frames")
        self._update_stat(self._stat_frames, f"{frames_agreed} / {frames_total}", "consensus vote")

        input_type = "Video clip" if is_video else "Image"
        input_sub = f"{filename.split('.')[-1].lower()} · {frames_total} frames" if filename else ""
        self._update_stat(self._stat_input, input_type, input_sub)

        # Similarity bar
        self._sim_bar.setValue(similarity)
        self._sim_pct.setText(f"{similarity}%")

        # Quota reminder - shown every N searches when backend send it
        quota_reminder = verdict.get("quota_reminder")
        if quota_reminder:
            self._quota_reminder.setText(f"🔔 {quota_reminder.strip()}")
            self._quota_reminder.setVisible(True)
        else:
            self._quota_reminder.setVisible(False)

        # Low quota warning - shown when remaining searches drop low
        low_warning = verdict.get("quota_low_warning")
        if low_warning:
            self._quota_low_warning.setText(f"⚠ {low_warning}")
            self._quota_low_warning.setVisible(True)
        else:
            self._quota_low_warning.setVisible(False)

    # -----helpers-----------

    def _set_cover(self, cover_image_b64: str | None) -> None:
        """
        Decode and display the cover image fetched by the worker, or
        fall back to the TV emoji placeholder if none is available.
        """
        if not cover_image_b64:
            self._cover_label.setText("📺")
            self._cover_label.setPixmap(QPixmap())
            return

        try:
            image_bytes = base64.b64decode(cover_image_b64)
            pixmap = QPixmap()
            pixmap.loadFromData(image_bytes)
            if pixmap.isNull():
                raise ValueError("Empty pixmap")

            scaled = pixmap.scaled(
                theme.COVER_W, theme.COVER_H,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._cover_label.setText("")
            self._cover_label.setPixmap(scaled)
            self._cover.setStyleSheet(f"""
                QFrame {{
                    background: transparent;
                    border: 1px solid {theme.BORDER_DEFAULT};
                    border-radius: 8px;
                }}
            """)
        except Exception:
            self._cover_label.setText("📺")
            self._cover_label.setPixmap(QPixmap())

    def _set_background(self, cover_image_b64: str | None) -> None:
        """
        Decode the cover image and store it for paintEvent to draw for background.

        This is the same image (cover) shown as the card thumbnail, just larger.

        Falls back to a plain dark background if no cover is available.
        """
        if not cover_image_b64:
            self._bg_pixmap = None
            self.update()
            return

        try:
            image_bytes = base64.b64decode(cover_image_b64)
            pixmap = QPixmap()
            pixmap.loadFromData(image_bytes)
            if pixmap.isNull():
                raise ValueError("Empty pixmap")

            self._bg_pixmap = pixmap
            self.update()
        except Exception:
            self._bg_pixmap = None
            self.update()

    def _make_stat(self, label: str, value: str, sub: str) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(theme.stat_box_style())
        fl = QVBoxLayout(frame)
        fl.setContentsMargins(12, 10, 12, 10)
        fl.setSpacing(2)

        lbl = QLabel(label.upper())
        lbl.setObjectName("stat_label")
        lbl.setStyleSheet(f"""
            QLabel {{
                color: {theme.TEXT_GHOST};
                font-size: {theme.FONT_XS}px;
                letter-spacing: 1px;
            }}
        """)
        fl.addWidget(lbl)

        val = QLabel(value)
        val.setObjectName("stat_value")
        val.setStyleSheet(f"color: {theme.TEXT_SECONDARY}; font-size: {theme.FONT_LG}px; font-weight: 500;")
        fl.addWidget(val)

        s = QLabel(sub)
        s.setObjectName("stat_sub")
        s.setStyleSheet(f"color: {theme.TEXT_DEEP}; font-size: {theme.FONT_XS}px;")
        fl.addWidget(s)

        return frame

    def _update_stat(self, frame: QFrame, value: str, sub: str) -> None:
        frame.findChild(QLabel, "stat_value").setText(value)
        frame.findChild(QLabel, "stat_sub").setText(sub)
