import base64

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QPushButton, QProgressBar, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap, QPainter, QFont, QFontMetrics

from ui import theme
from ui.background_paint import draw_cover_background
from ui.search_worker import QuotaWorker


class _ImageBanner(QWidget):
    """
    Displays a pixmap scaled to cover the widget.

    The image automatically resizes to fill the widgets current dimensions.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pixmap: QPixmap | None = None

    def set_pixmap(self, pixmap: QPixmap | None) -> None:
        self._pixmap = pixmap
        self.update()

    def paintEvent(self, event) -> None:
        if self._pixmap is not None and not self._pixmap.isNull():
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
            draw_cover_background(painter, self.rect(), self._pixmap)
            painter.end()
        super().paintEvent(event)


class ResultScreen(QWidget):
    # Emits when user clicks back or try again
    go_back = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self._bg_pixmap = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(0)

        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(0, 0, 0, 0)
        top_bar.setSpacing(0)

        top_bar.addStretch()

        self._quota_link = QPushButton("Check searches left")
        self._quota_link.setStyleSheet(self._quota_link_style())
        self._quota_link.setFixedHeight(28)
        self._quota_link.setCursor(Qt.CursorShape.PointingHandCursor)
        self._quota_link.clicked.connect(self._on_check_quota)
        top_bar.addWidget(self._quota_link, alignment=Qt.AlignmentFlag.AlignRight)

        layout.addLayout(top_bar)

        layout.addSpacing(20)

        # Result card - like 50%-transparent so the cover image shows through
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
        self._hero_normal = result_top
        hero_layout = QHBoxLayout(result_top)
        hero_layout.setContentsMargins(18, 18, 18, 18)
        hero_layout.setSpacing(16)
        hero_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Cover img,fall back to emoji is cant find
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

        # Banner hero layout, shown when an episode still is available.
        self._hero_banner = QFrame()
        self._hero_banner.setObjectName("result_hero_banner")
        self._hero_banner.setStyleSheet(f"""
            QFrame#result_hero_banner {{
                background: transparent;
                border-bottom: 1px solid {theme.BORDER_SUBTLE};
            }}
        """)
        self._hero_banner.setVisible(False)
        banner_outer = QVBoxLayout(self._hero_banner)
        banner_outer.setContentsMargins(0, 0, 0, 0)
        banner_outer.setSpacing(0)

        # Image strip, full card width, fixed height
        self._banner_image = _ImageBanner()
        self._banner_image.setFixedHeight(150)
        banner_outer.addWidget(self._banner_image)

        # Title + native title + season/episode/timestamp/year badges, below the image
        banner_meta = QWidget()
        banner_meta_layout = QVBoxLayout(banner_meta)
        banner_meta_layout.setContentsMargins(18, 14, 18, 18)
        banner_meta_layout.setSpacing(0)

        self._banner_title_label = QLabel()
        self._banner_title_label.setStyleSheet(f"""
            QLabel {{
                color: {theme.TEXT_PRIMARY};
                font-size: {theme.FONT_XL}px;
                font-weight: 500;
            }}
        """)
        self._banner_title_label.setWordWrap(False)
        banner_meta_layout.addWidget(self._banner_title_label)

        banner_meta_layout.addSpacing(2)

        self._banner_native_label = QLabel()
        self._banner_native_label.setStyleSheet(f"color: {theme.TEXT_GHOST}; font-size: {theme.FONT_SM}px;")
        banner_meta_layout.addWidget(self._banner_native_label)

        banner_meta_layout.addSpacing(12)

        self._banner_badges_row = QHBoxLayout()
        self._banner_badges_row.setSpacing(6)
        self._banner_badges_row.setAlignment(Qt.AlignmentFlag.AlignLeft)
        banner_meta_layout.addLayout(self._banner_badges_row)

        banner_outer.addWidget(banner_meta)
        card_layout.addWidget(self._hero_banner)

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
        Paint the cover image as the background, scaled to *cover* the whole screen.

        Scaling happens here, against self.rect(), so the image always fills the screen.
        """
        if self._bg_pixmap is not None and not self._bg_pixmap.isNull():
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
            draw_cover_background(painter, self.rect(), self._bg_pixmap)
            painter.end()
        super().paintEvent(event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        # paintEvent reads the live size, so just trigger a repaint.
        self.update()

    # Quota check (only if pressed by user)
    def _on_check_quota(self) -> None:
        """
        User clicked the "check searchs left" button - run a backend API ask via /quota

        Return how many searchs left from the total daily searchs.
        """
        self._quota_link.setText("Checking...")
        self._quota_link.setEnabled(False)

        self._quota_worker = QuotaWorker()
        self._quota_worker.finished.connect(self._on_quota_checked)
        self._quota_worker.error.connect(self._on_quota_check_failed)
        self._quota_worker.start()

    def _on_quota_checked(self, data: dict) -> None:
        remaining = data.get("remaining")
        quota = data.get("quota")
        if remaining is not None and quota is not None:
            self._quota_link.setText(f"{remaining}/{quota} searches left")
        else:
            self._quota_link.setText("Check searches left")

        if data.get("low_quota"):
            self._quota_link.setStyleSheet(f"""
                QPushButton {{
                    background: none;
                    border: none;
                    color: {theme.CONFIDENCE_LOW_TEXT};
                    font-size: {theme.FONT_MD}px;
                    font-weight: 600;
                }}
            """)
        else:
            self._quota_link.setStyleSheet(self._quota_link_style())

        self._quota_link.setEnabled(True)

    def _on_quota_check_failed(self, message: str) -> None:
        self._quota_link.setText("Check searches left")
        self._quota_link.setStyleSheet(self._quota_link_style())
        self._quota_link.setToolTip(message)
        self._quota_link.setEnabled(True)

    def _quota_link_style(self) -> str:
        return f"""
            QPushButton {{
                background: none;
                border: none;
                color: {theme.TEXT_MUTED};
                font-size: {theme.FONT_MD}px;
            }}
            QPushButton:hover {{
                color: {theme.TEXT_PRIMARY};
            }}
        """

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

        title = (
            verdict.get("anime") or
            verdict.get("Romaji") or
            verdict.get("Native Title") or
            "Unknown"
        )
        native = verdict.get("Native Title", "")
        native_display = native if native and native != "Unknown" else ""

        cover_b64 = verdict.get("cover_image_b64")
        episode_thumb_b64 = verdict.get("episode_thumb_b64")
        banner_image_b64 = verdict.get("banner_image_b64")

        # Prefer the episode banner, then the AniList banner, otherwise use the cover layout.
        banner_source = episode_thumb_b64 or banner_image_b64
        use_banner = bool(banner_source)

        self._hero_normal.setVisible(not use_banner)
        self._hero_banner.setVisible(use_banner)

        # Set titles for both layouts, shrinking the font if needed.
        self._set_fitted_title(self._title_label, title, available_width=240, max_px=theme.FONT_XL)
        self._title_label.setToolTip(title)
        self._native_label.setText(native_display)

        self._set_fitted_title(self._banner_title_label, title, available_width=394, max_px=theme.FONT_XL)
        self._banner_title_label.setToolTip(title)
        self._banner_native_label.setText(native_display)

        # Show the appropriate image for the active layout.
        if use_banner:
            self._set_banner_image(banner_source)
        else:
            self._set_cover(cover_b64)

        # Background always uses the poster art.
        self._set_background(cover_b64)

        # Populate metadata badges for both layouts.
        self._populate_badges(self._badges_row, verdict)
        self._populate_badges(self._banner_badges_row, verdict)

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
        Display the poster image in the cover box. Show the TV placeholder if no image is available.
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

    def _set_banner_image(self, image_b64: str | None) -> None:
        """
        Load the banner image (or AniList banner as a fallback) into the banner widget.
        """
        if not image_b64:
            self._banner_image.set_pixmap(None)
            return

        try:
            image_bytes = base64.b64decode(image_b64)
            pixmap = QPixmap()
            pixmap.loadFromData(image_bytes)
            if pixmap.isNull():
                raise ValueError("Empty pixmap")
            self._banner_image.set_pixmap(pixmap)
        except Exception:
            self._banner_image.set_pixmap(None)

    def _set_fitted_title(self, label: QLabel, text: str, available_width: int, max_px: int, min_px: int = 14) -> None:
        """
        set the title text, keeping the default size unless it needs to be reduced.
        """
        label.setText(text)

        chosen_px = min_px
        for px in range(max_px, min_px - 1, -1):
            font = QFont()
            font.setPixelSize(px)
            # safty buffer
            if QFontMetrics(font).horizontalAdvance(text) <= available_width - 6:
                chosen_px = px
                break

        label.setStyleSheet(f"""
            QLabel {{
                color: {theme.TEXT_PRIMARY};
                font-size: {chosen_px}px;
                font-weight: 500;
            }}
        """)

    def _populate_badges(self, row: QHBoxLayout, verdict: dict) -> None:
        """
        Fill a season/episode/timestamp badges row from the verdict. 

        Used for both cases, with episode thumbnail or anime banner.
        """
        while row.count():
            item = row.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        season = verdict.get("season")
        if season:
            badge = QLabel(season)
            badge.setStyleSheet(theme.badge_season_style())
            row.addWidget(badge)

        episode = verdict.get("episode")
        if episode is not None:
            badge = QLabel(f"Episode {episode}")
            badge.setStyleSheet(theme.badge_ep_style())
            row.addWidget(badge)

        timestamp = verdict.get("timestamp")
        if timestamp:
            badge = QLabel(f"⏱ {timestamp}")
            badge.setStyleSheet(theme.badge_ts_style())
            row.addWidget(badge)

        ts_range = verdict.get("timestamp_range")
        if ts_range:
            badge = QLabel(f"⏱ {ts_range}")
            badge.setStyleSheet(theme.badge_range_style())
            row.addWidget(badge)

        # Year - same row as the others, but pushed to right 
        year = verdict.get("year")
        if year:
            row.addStretch()
            badge = QLabel(str(year))
            badge.setStyleSheet(theme.year_badge_style())
            row.addWidget(badge)

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
