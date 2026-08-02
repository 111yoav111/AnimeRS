import base64
import re

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QPushButton, QProgressBar, QSizePolicy, QDialog, QScrollArea,
    QApplication
)
from PyQt6.QtCore import Qt, pyqtSignal, QRectF, QSize, QTimer, QUrl
from PyQt6.QtGui import QPixmap, QPainter, QFont, QFontMetrics, QPainterPath
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget

from ui import theme
from ui.background_paint import draw_cover_background
from ui.search_worker import QuotaWorker


# banner hero height - let the text be above the image.
_BANNER_H = 210
_BANNER_H_MIN = 150

_STAT_INNER_WIDTH = 100  # used for the very start, before the stats row set up


def _clean_anilist_text(text: str | None) -> str:
    """
    AniList descriptions can still carry stray HTML/markdown even with
    asHtml: false requested - strip it down to plain, readable text.
    """
    if not text:
        return ""
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("__", "").replace("~!", "").replace("!~", "")
    return text.strip()


class _ImageBanner(QWidget):
    """
    Displays a pixmap scaled to cover the widget.

    The image automatically resizes to fill the widgets current dimensions.

    corner_radius defaults to 0, preserving the original square-corner behavior.
    Upload img/gif/vid for displaying the rounded corners.
    """

    def __init__(self, parent=None, corner_radius: int = 0, preferred_height: int = 0):
        super().__init__(parent)
        self._pixmap: QPixmap | None = None
        self._corner_radius = corner_radius
        self._preferred_height = preferred_height

    def sizeHint(self) -> QSize:
        # preferred (not fixed) height lets the layout hand back space when
        # the window is short, instead of overlapping the widgets below.
        hint = super().sizeHint()
        if self._preferred_height:
            return QSize(hint.width(), self._preferred_height)
        return hint

    def set_pixmap(self, pixmap: QPixmap | None) -> None:
        self._pixmap = pixmap
        self.update()

    def paintEvent(self, event) -> None:
        if self._pixmap is not None and not self._pixmap.isNull():
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            if self._corner_radius > 0:
                path = QPainterPath()
                path.addRoundedRect(
                    QRectF(self.rect()), self._corner_radius, self._corner_radius
                )
                painter.setClipPath(path)
            draw_cover_background(painter, self.rect(), self._pixmap)
            painter.end()
        super().paintEvent(event)


class ResultScreen(QWidget):
    # Budget for the badges row in the banner layout. The title and native title are
    _badges_budget = 394

    # Emits when user clicks back or try again
    go_back = pyqtSignal()
    # Emits when user clicks "History"
    show_history_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self._bg_pixmap = None
        self._info_title = ""
        self._info_description = ""
        self._info_episode_title = ""
        self._result_copy_text = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(0)

        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(0, 0, 0, 0)
        top_bar.setSpacing(0)

        self._copy_btn = QPushButton("Copy result")
        self._copy_btn.setStyleSheet(self._quota_link_style())
        self._copy_btn.setFixedHeight(28)
        self._copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._copy_btn.setVisible(False)  # only makes sense once a result is actually shown
        self._copy_btn.clicked.connect(self._on_copy_result)
        top_bar.addWidget(self._copy_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        top_bar.addStretch()

        self._history_btn = QPushButton("🕘  History")
        self._history_btn.setStyleSheet(theme.history_btn_style())
        self._history_btn.setFixedHeight(30)
        self._history_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._history_btn.clicked.connect(self.show_history_requested.emit)
        top_bar.addWidget(self._history_btn, alignment=Qt.AlignmentFlag.AlignRight)

        top_bar.addSpacing(12)

        self._quota_link = QPushButton("Check searches left")
        self._quota_link.setStyleSheet(self._quota_link_style())
        self._quota_link.setFixedHeight(28)
        self._quota_link.setCursor(Qt.CursorShape.PointingHandCursor)
        self._quota_link.clicked.connect(self._on_check_quota)

        # Reset the quota button label 10 seconds after a successful check.
        # Restart the timer each time so older checks can't overwrite newer results.
        self._quota_revert_timer = QTimer(self)
        self._quota_revert_timer.setSingleShot(True)
        self._quota_revert_timer.timeout.connect(self._revert_quota_button)
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
        self._banner_image = _ImageBanner(preferred_height=_BANNER_H)
        # bottom floor = whatever the overlaid text block needs +  art above it.
        # so the text can never be pushed off the image.
        self._banner_image.setMinimumHeight(_BANNER_H_MIN)
        self._banner_image.setMaximumHeight(_BANNER_H)
        banner_outer.addWidget(self._banner_image)

        # The title/native/badges block is laid out *inside* the image, pinned to
        # its bottom edge, so the text sits on the artwork. A stretch above it
        # does the pinning - no absolute positioning, so it survives resizes.
        self._banner_image_layout = QVBoxLayout(self._banner_image)
        self._banner_image_layout.setContentsMargins(0, 0, 0, 0)
        self._banner_image_layout.setSpacing(0)
        self._banner_image_layout.addStretch(1)

        # Inline preview clip - overlays the banner image, autoplays muted
        # for a few seconds, then hides itself and show banner instead.
        self._preview_url: str | None = None
        self._preview_retried = False  # one retry per result
        self._banner_video_widget = QVideoWidget(self._banner_image)
        self._banner_video_widget.setVisible(False)

        self._banner_audio_output = QAudioOutput()
        self._banner_audio_output.setMuted(True)  # autoplay cant have sound
        self._banner_video_player = QMediaPlayer()
        self._banner_video_player.setAudioOutput(self._banner_audio_output)
        self._banner_video_player.setVideoOutput(self._banner_video_widget)
        self._banner_video_player.errorOccurred.connect(self._on_banner_preview_error)
        self._banner_video_player.playbackStateChanged.connect(self._on_banner_playback_state_changed)

        self._banner_preview_timer = QTimer(self)
        self._banner_preview_timer.setSingleShot(True)
        self._banner_preview_timer.timeout.connect(self._on_banner_preview_timeout)

        # Info btn in the images top-left corner. Parent it to the banner.Ad
        # Hidden by default - only shown when we actually have something to show.
        self._info_btn = QPushButton("i", self._banner_image)
        self._info_btn.setFixedSize(24, 24)
        self._info_btn.move(12, 12)
        self._info_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._info_btn.setToolTip("About this anime")
        self._info_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(0, 0, 0, 160);
                border: 1px solid rgba(255, 255, 255, 60);
                border-radius: 12px;
                color: {theme.TEXT_PRIMARY};
                font-size: {theme.FONT_SM}px;
                font-weight: 700;
                font-style: italic;
            }}
            QPushButton:hover {{
                background: rgba(0, 0, 0, 210);
            }}
        """)
        self._info_btn.setVisible(False)
        self._info_btn.clicked.connect(self._on_show_info)

        # Expand btn in the image's top-right corner - opens the preview clip
        # Hidden until a preview is available.
        self._preview_expand_btn = QPushButton("▶", self._banner_image)
        self._preview_expand_btn.setFixedSize(24, 24)
        self._preview_expand_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._preview_expand_btn.setToolTip("Watch preview clip")
        self._preview_expand_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(0, 0, 0, 160);
                border: 1px solid rgba(255, 255, 255, 60);
                border-radius: 12px;
                color: {theme.TEXT_PRIMARY};
                font-size: {theme.FONT_XS}px;
            }}
            QPushButton:hover {{
                background: rgba(0, 0, 0, 210);
            }}
        """)
        self._preview_expand_btn.setVisible(False)
        self._preview_expand_btn.clicked.connect(self._on_open_preview_dialog)

        self._info_btn.raise_()
        self._preview_expand_btn.raise_()

        # Title + native title + season/episode/timestamp/year badges, below the image
        banner_meta = QWidget()
        banner_meta.setObjectName("banner_meta")
        # add a background to text so it will be readable always
        banner_meta.setStyleSheet("""
            QWidget#banner_meta {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(13, 13, 15, 0),
                    stop:0.35 rgba(13, 13, 15, 165),
                    stop:1 rgba(13, 13, 15, 230));
            }
        """)
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

        banner_meta_layout.addSpacing(6)

        self._banner_badges_row = QHBoxLayout()
        self._banner_badges_row.setSpacing(6)
        self._banner_badges_row.setAlignment(Qt.AlignmentFlag.AlignLeft)
        banner_meta_layout.addLayout(self._banner_badges_row)

        self._banner_image_layout.addWidget(banner_meta)
        self._banner_meta = banner_meta
        # Created after the video widget, so it already stacks above it; make
        # that explicit so the preview clip never covers the title.
        self._banner_meta.raise_()
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

        layout.addSpacing(10)

        # Quota notice shared by the session reminder and low-quota warning.
        # Its layout space is always reserved so showing it doesn't shift the UI.
        self._quota_reminder = QLabel("")
        self._quota_reminder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._quota_reminder.setStyleSheet(f"color: {theme.CONFIDENCE_LOW_TEXT}; font-size: {theme.FONT_XS}px;")
        self._quota_reminder.setFixedHeight(18)  # emoji glyphs render taller than text - pin the height
        _sp = self._quota_reminder.sizePolicy()
        _sp.setRetainSizeWhenHidden(True)
        self._quota_reminder.setSizePolicy(_sp)
        self._quota_reminder.setVisible(False)
        layout.addWidget(self._quota_reminder)

        layout.addSpacing(4)

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
        self._resize_banner_video()

    def _resize_banner_video(self) -> None:
        self._banner_video_widget.setGeometry(0, 0, self._banner_image.width(), self._banner_image.height())
        self._banner_meta.raise_()  # video is a sibling covering the whole image
        margin = 12
        x = self._banner_image.width() - self._preview_expand_btn.width() - margin
        self._preview_expand_btn.move(max(0, x), margin)

    # Quota check (only if pressed by user)
    def _on_copy_result(self) -> None:
        """
        Copy the current result's title, season/episode, and timestamp to the
        clipboard as plain text.

        After clicking, the button shows a "Copied!" message, then reverting to the defult label.
        """
        if not self._result_copy_text:
            return
        QApplication.clipboard().setText(self._result_copy_text)
        self._copy_btn.setText("Copied!")
        QTimer.singleShot(1500, lambda: self._copy_btn.setText("Copy result"))

    def _on_banner_playback_state_changed(self, state) -> None:
        """
        Show the clip and start the swap to banner countdown only once
        playback has actually reached PlayingState - not when requested.

        Showing the widget here rather than in _set_preview keeps the banner
        image on screen while a network clip buffers.
        """
        if state != QMediaPlayer.PlaybackState.PlayingState:
            return
        if not self._preview_url or not self._hero_banner.isVisible():
            return  # result changed (or went away) while the clip was loading

        self._resize_banner_video()
        self._banner_video_widget.setVisible(True)
        # The video widget is a sibling of these ones, so it would cover them.
        self._info_btn.raise_()
        self._preview_expand_btn.raise_()
        self._banner_preview_timer.start(4000)

    def _on_banner_preview_timeout(self) -> None:
        """
        The countdown is over -> swap back to the banner.
        Hidden before stopped, so the video sink isn't torn down while still visible/painting.
        """
        self._banner_video_widget.setVisible(False)
        self._banner_video_player.stop()

    def _on_banner_preview_error(self, error, error_string) -> None:
        """
        The preview stream failed to load (dead link, network hiccup, or
        trace.moe still cutting the clip) - fall back to the static banner
        instead of a broken black box, then give it one retry a moment later.
        """
        self._banner_preview_timer.stop()
        self._banner_video_widget.setVisible(False)
        self._banner_video_player.stop()

        if self._preview_url and not self._preview_retried:
            self._preview_retried = True
            QTimer.singleShot(900, lambda url=self._preview_url: self._retry_banner_preview(url))

    def _retry_banner_preview(self, url: str) -> None:
        """
        Second (and last) attempt at the inline preview, skipped if a
        different result is on screen by now.
        """
        if self._preview_url != url or not self._hero_banner.isVisible():
            return
        self._banner_video_player.setSource(QUrl())  # see _set_preview
        self._banner_video_player.setSource(QUrl(url))
        self._banner_video_player.play()

    def _on_open_preview_dialog(self) -> None:
        """
        User clicked the expand button - replay the preview clip full-size,
        unmuted, in its own dialog.
        """
        if not self._preview_url:
            return

        # full stop
        self._banner_preview_timer.stop()
        self._banner_video_widget.setVisible(False)
        self._banner_video_player.stop()

        dialog = QDialog(self)
        dialog.setWindowTitle("Preview clip")
        dialog.setFixedSize(400, 300)
        dialog.setStyleSheet(f"background: {theme.BG_APP};")

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        video_widget = QVideoWidget()
        video_widget.setMinimumHeight(220)
        layout.addWidget(video_widget, stretch=1)

        # trace.moe's preview links expire after a while, so an old
        # history/batch result can fail here even though it played fine
        # when it was first searched. Shown in place of the video instead
        # of leaving a blank, stuck-looking player.
        unavailable_label = QLabel("Preview unavailable\n(the clip link has likely expired)")
        unavailable_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        unavailable_label.setWordWrap(True)
        unavailable_label.setStyleSheet(f"color: {theme.TEXT_FAINT}; font-size: {theme.FONT_SM}px;")
        unavailable_label.setVisible(False)
        layout.addWidget(unavailable_label, stretch=1)

        player = QMediaPlayer(dialog)
        audio = QAudioOutput(dialog)
        player.setAudioOutput(audio)
        player.setVideoOutput(video_widget)

        def _on_dialog_preview_error(*_):
            player.stop()
            video_widget.setVisible(False)
            unavailable_label.setVisible(True)

        # Playing it once just stops at the end of the data that was actually received.
        # cant play it loop since the received data will crash the app.
        player.errorOccurred.connect(_on_dialog_preview_error)
        player.setSource(QUrl(self._preview_url))
        player.play()

        close_btn = QPushButton("Close")
        close_btn.setStyleSheet(theme.browse_btn_style())
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)

        dialog.exec()
        player.stop()
        # Defer the actual C++ destruction to a safe point in the event loop
        # rather than leaving it to Python refcounting timing.
        dialog.deleteLater()

    def _on_check_quota(self) -> None:
        """
        User clicked the "check searchs left" button - run a backend API ask via /quota

        Return how many searchs left from the total daily searchs.
        """
        self._quota_revert_timer.stop()  # a fresh check gets its own full 10s timer
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
        self._quota_revert_timer.start(10000)  # back to normal 10s after showing the result

    def _on_quota_check_failed(self, message: str) -> None:
        self._quota_revert_timer.stop()
        self._quota_link.setText("Check searches left")
        self._quota_link.setStyleSheet(self._quota_link_style())
        self._quota_link.setToolTip(message)
        self._quota_link.setEnabled(True)

    def _revert_quota_button(self) -> None:
        self._quota_link.setText("Check searches left")
        self._quota_link.setStyleSheet(self._quota_link_style())

    def _on_show_info(self) -> None:
        """
        User clicked the info icon on the banner - show explantion about anime.
        This is the series general premise AniList description...
        """
        dialog = QDialog(self)
        dialog.setWindowTitle("About this anime")
        dialog.setFixedSize(380, 340)
        dialog.setStyleSheet(f"background: {theme.BG_APP}; color: {theme.TEXT_PRIMARY};")

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        heading = QLabel(self._info_title or "About this anime")
        heading.setWordWrap(True)
        heading.setStyleSheet(f"font-size: {theme.FONT_LG}px; font-weight: 600; color: {theme.TEXT_PRIMARY};")
        layout.addWidget(heading)

        if self._info_episode_title:
            ep_label = QLabel(self._info_episode_title)
            ep_label.setWordWrap(True)
            ep_label.setStyleSheet(f"color: {theme.ACCENT}; font-size: {theme.FONT_SM}px; font-weight: 600;")
            layout.addWidget(ep_label)

        # Scrollable
        # dialog shouldnt just clip it.
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        body = QLabel(self._info_description or "No description available for this anime.")
        body.setWordWrap(True)
        body.setStyleSheet(f"color: {theme.TEXT_MUTED}; font-size: {theme.FONT_SM}px; background: transparent;")
        scroll.setWidget(body)
        layout.addWidget(scroll, stretch=1)

        close_btn = QPushButton("Close")
        close_btn.setStyleSheet(theme.browse_btn_style())
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)

        dialog.exec()

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
            self._info_btn.setVisible(False)
            self._copy_btn.setVisible(False)
            self._set_background(None)
            self._set_preview(None, use_banner=False)
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

        # Build the "copy result" answer.
        copy_parts = [title]
        season = verdict.get("season")
        if season:
            copy_parts.append(season)
        episode = verdict.get("episode")
        if episode is not None:
            copy_parts.append(f"Episode {episode}")
        self._result_copy_text = " - ".join(copy_parts)
        timestamp = verdict.get("timestamp") or verdict.get("timestamp_range")
        if timestamp:
            self._result_copy_text += f" ({timestamp})"
        self._copy_btn.setVisible(True)

        # info popup - include some basic info abou thte anime.
        self._info_title = title
        self._info_description = _clean_anilist_text(verdict.get("description"))
        self._info_episode_title = verdict.get("episode_title")
        self._info_btn.setVisible(bool(self._info_description or self._info_episode_title))

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

        self._set_preview(verdict.get("preview_video_url"), use_banner=use_banner)

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

        # Shared quota notice. If both messages are available, the low-quota
        # warning takes priority.
        quota_reminder = verdict.get("quota_reminder")
        low_warning = verdict.get("quota_low_warning")
        if low_warning:
            self._quota_reminder.setText(f"⚠ {low_warning.strip()}")
            self._quota_reminder.setStyleSheet(
                f"color: {theme.CONFIDENCE_LOW_TEXT}; font-size: {theme.FONT_XS}px; font-weight: 600;"
            )
            self._quota_reminder.setVisible(True)
        elif quota_reminder:
            self._quota_reminder.setText(f"🔔 {quota_reminder.strip()}")
            self._quota_reminder.setStyleSheet(
                f"color: {theme.CONFIDENCE_LOW_TEXT}; font-size: {theme.FONT_XS}px;"
            )
            self._quota_reminder.setVisible(True)
        else:
            self._quota_reminder.setVisible(False)

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
            font = QFont(label.font())
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

        def _add(badge: QLabel) -> None:
            # Keep badges at their intended size. This prevents Qt from shrinking
            # them when the window becomes crowded by other stuff.
            badge.ensurePolished()  # apply the stylesheet padding BEFORE measuring
            badge.setMinimumSize(badge.sizeHint())
            badge.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            row.addWidget(badge)

        season = verdict.get("season")
        if season:
            badge = QLabel(season)
            badge.setStyleSheet(theme.badge_season_style())
            _add(badge)

        episode = verdict.get("episode")
        if episode is not None:
            badge = QLabel(f"Episode {episode}")
            badge.setStyleSheet(theme.badge_ep_style())
            _add(badge)

        timestamp = verdict.get("timestamp")
        if timestamp:
            badge = QLabel(f"⏱ {timestamp}")
            badge.setStyleSheet(theme.badge_ts_style())
            _add(badge)

        ts_range = verdict.get("timestamp_range")
        if ts_range:
            badge = QLabel(f"⏱ {ts_range}")
            badge.setStyleSheet(theme.badge_range_style())
            _add(badge)

        # Build the year badge first so its real width can be reserved.
        year = verdict.get("year")
        year_badge = None
        if year:
            year_badge = QLabel(str(year))
            year_badge.setStyleSheet(theme.year_badge_style())
            year_badge.ensurePolished()

        # check the badges row is good, and if not, elide the widest one to fit.
        widgets = [row.itemAt(i).widget() for i in range(row.count())]
        widgets = [w for w in widgets if w is not None]
        if widgets:
            reserved = (year_badge.sizeHint().width() + 6) if year_badge else 0
            budget = self._badges_budget - reserved
            used = sum(w.sizeHint().width() for w in widgets) + 6 * (len(widgets) - 1)
            if used > budget:
                widest = max(widgets, key=lambda w: w.sizeHint().width())
                full_text = widest.text()
                allowed = widest.sizeHint().width() - (used - budget)
                if allowed > 48:
                    widest.setMinimumSize(0, 0)  # unpin before re-measuring
                    fm = QFontMetrics(widest.font())
                    # maybe 22px of the badge width is padding + border, not text.
                    widest.setText(fm.elidedText(full_text, Qt.TextElideMode.ElideRight, allowed - 22))
                    widest.setToolTip(full_text)
                    widest.setMinimumSize(widest.sizeHint())

        if year_badge is not None:
            row.addStretch()
            _add(year_badge)

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

    def _set_preview(self, video_url: str | None, use_banner: bool) -> None:
        """
        Autoplay trace.moe's preview clip inline over the banner image for a
        few seconds, muted, then swap back to the banner. 

        The expand button stays available after to replay it full-size.

        Only wired up when the banner layout is active - there's nowhere to
        show it in the plain cover layout.
        """
        self._preview_url = video_url if use_banner else None
        self._banner_preview_timer.stop()
        self._preview_expand_btn.setVisible(bool(self._preview_url))

        if not self._preview_url:
            self._banner_video_widget.setVisible(False)
            self._banner_video_player.stop()
            return

        self._resize_banner_video()  # geometry may be stale if this is the first result shown
        self._banner_audio_output.setMuted(True)
        self._preview_retried = False
        # Keep the video hidden until playback starts to avoid a black placeholder
        # while the clip is buffering.
        self._banner_video_widget.setVisible(False)

        # Reset the media source before loading the clip. Qt's FFmpeg backend can
        # fail when reusing the same URL ("Demuxing failed"), so clearing the source
        # forces a fresh load. No explicit stop() is needed since setSource() already
        # resets playback.
        self._banner_video_player.setSource(QUrl())
        self._banner_video_player.setSource(QUrl(self._preview_url))
        self._banner_video_player.play()
        # The 4s countdown starts once playback begins (see _on_banner_playback_state_changed).

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

    def _fitted_px(self, text: str, available_width: int, max_px: int, min_px: int) -> int:
        """
        Largest pixel size, at most max_px, that fits text in available_width.
        """
        for px in range(max_px, min_px - 1, -1):
            font = QFont(self.font())
            font.setPixelSize(px)
            if QFontMetrics(font).horizontalAdvance(text) <= available_width:
                return px
        return min_px

    def _update_stat(self, frame: QFrame, value: str, sub: str) -> None:
        """
        Fill a stat box, shrinking the text if it would be cut off - the boxes
        are a fixed third of the card each, and "Video clip" or
        "avg across frames" are both wider than that at the default size.
        """
        inner_width = frame.width() - 24  # the box's 12px side margins
        if inner_width < 60:
            inner_width = _STAT_INNER_WIDTH  # first result, row not laid out yet

        value_label = frame.findChild(QLabel, "stat_value")
        value_label.setText(value)
        value_px = self._fitted_px(value, inner_width, theme.FONT_LG, 12)
        value_label.setStyleSheet(
            f"color: {theme.TEXT_SECONDARY}; font-size: {value_px}px; font-weight: 500;"
        )

        sub_label = frame.findChild(QLabel, "stat_sub")
        sub_label.setText(sub)
        sub_px = self._fitted_px(sub, inner_width, theme.FONT_XS, 9)
        sub_label.setStyleSheet(f"color: {theme.TEXT_DEEP}; font-size: {sub_px}px;")
        