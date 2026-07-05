from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QPushButton, QFileDialog, QProgressBar, QSizePolicy,
    QDialog, QSpinBox, QGraphicsOpacityEffect
)
from PyQt6.QtCore import Qt, pyqtSignal, QPropertyAnimation, QEasingCurve, QTimer
from PyQt6.QtGui import QKeySequence, QShortcut, QDragEnterEvent, QDropEvent, QPainter, QFontMetrics, QPixmap

from ui import theme
from ui.background_paint import draw_cover_background, load_pixmap
from ui.result_screen import _ImageBanner
from ui.search_worker import ThumbnailWorker

# The upload screens background image - only this file.
_BG_IMAGE_PATH = Path(__file__).parent / "assets" / "bg_image.png"

# Running/cartwheel animation shown during "Analyzing frames".
# Uses pre-cut, equally sized frames (not a sprite sheet that is sliced at runtime).
# Cycles through frames with a timer, and falls back to an emoji if assets are missing.
_RUN_CYCLE_DIR = Path(__file__).parent / "assets" / "run_cycle"
_RUN_CYCLE_FRAME_COUNT = 7

# Horizontal movement speed (pixels per second)
_WALK_SPEED_PX_PER_SEC = 45

# Pose cycle timing: how often the 7-frame animation loops.
# This is independent from full screen traversal time, so the character
# performs multiple steps per crossing instead of a single cycle.
_POSE_CYCLE_MS = 950

# Allowed formats for the file dialog filter
_ALLOWED_FORMATS = "Media files (*.jpg *.jpeg *.png *.webp *.bmp *.tiff *.tif *.gif *.mp4 *.mkv *.webm *.mov *.avi)"

_STILL_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".tif",
}


class FramePickerDialog(QDialog):
    """
    Small popup for the user to choose how many frames to extract.
    Only shown for video/GIF files.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Frame count")
        self.setFixedSize(320, 180)
        self.setStyleSheet(f"background: {theme.BG_APP}; color: {theme.TEXT_PRIMARY};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        label = QLabel("How many frames to extract?")
        label.setStyleSheet(f"color: {theme.TEXT_MUTED}; font-size: {theme.FONT_SM}px;")
        layout.addWidget(label)

        self._spinbox = QSpinBox()
        self._spinbox.setRange(1, 16)
        self._spinbox.setValue(5)
        self._spinbox.setStyleSheet(f"""
            QSpinBox {{
                background: {theme.BG_ELEVATED};
                border: 1px solid {theme.BORDER_DEFAULT};
                border-radius: {theme.RADIUS_BTN}px;
                padding: 10px 14px;
                color: {theme.TEXT_PRIMARY};
                font-size: {theme.FONT_LG}px;
            }}
        """)
        layout.addWidget(self._spinbox)

        confirm_btn = QPushButton("Confirm")
        confirm_btn.setStyleSheet(theme.browse_btn_style())
        confirm_btn.clicked.connect(self.accept)
        layout.addWidget(confirm_btn)

    def value(self) -> int:
        return self._spinbox.value()


class UploadScreen(QWidget):
    # Emits (file_path, max_frames) — max_frames is None if user didn't set it
    search_requested = pyqtSignal(str, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)

        self._current_path: str = ""
        self._max_frames: Optional[int] = None  # None = auto

        # The local image for bg, didnt find - fall back to black bg
        self._bg_pixmap = load_pixmap(_BG_IMAGE_PATH)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 28, 24, 28)
        layout.setSpacing(0)

        # All the card stuff, drop etc...
        self._card = QFrame()
        self._card.setObjectName("upload_card")
        self._card.setStyleSheet(theme.card_style(transparent=True))

        card_layout = QVBoxLayout(self._card)
        card_layout.setContentsMargins(20, 24, 20, 24)
        card_layout.setSpacing(0)

        # Header
        eyebrow = QLabel("Anime Reverse Searcher")
        eyebrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
        eyebrow.setStyleSheet(f"""
            QLabel {{
                color: {theme.ACCENT};
                font-size: {theme.FONT_2XL}px;
                letter-spacing: 3px;
            }}
        """)
        card_layout.addWidget(eyebrow)

        card_layout.addSpacing(6)

        heading = QLabel("What anime is this?")
        heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        heading.setStyleSheet(f"""
            QLabel {{
                color: {theme.TEXT_PRIMARY};
                font-size: {theme.FONT_XL}px;
                font-weight: 500;
            }}
        """)
        card_layout.addWidget(heading)

        card_layout.addSpacing(24)

        # Drop area
        self._drop_zone = QFrame()
        self._drop_zone.setObjectName("drop_zone")
        self._drop_zone.setStyleSheet(theme.drop_zone_style(hover=False, transparent=True))
        self._drop_zone.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._drop_zone.setMinimumHeight(200)

        dz_layout = QVBoxLayout(self._drop_zone)
        dz_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dz_layout.setSpacing(12)
        dz_layout.setContentsMargins(16, 24, 16, 24)

        # Full-drop-zone preview background. Displays the selected image or
        # video's first frame behind the drop zone's content. Hidden until a preview is ready.
        self._upload_preview = _ImageBanner(self._drop_zone, corner_radius=theme.RADIUS_CARD)
        self._upload_preview.setVisible(False)
        self._upload_preview.lower()

        # Center icon shown until a preview is available or if preview generation fails.
        self._upload_icon = QLabel("↑")
        self._upload_icon.setFixedSize(64, 64)
        self._upload_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._upload_icon.setStyleSheet(f"color: {theme.TEXT_DEEP}; font-size: 28px;")
        dz_layout.addWidget(self._upload_icon, alignment=Qt.AlignmentFlag.AlignCenter)

        self._drop_title = QLabel("Drop your file here")
        self._drop_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._drop_title.setStyleSheet(f"color: {theme.TEXT_PRIMARY}; font-size: {theme.FONT_LG}px; font-weight: 500;")
        dz_layout.addWidget(self._drop_title)

        self._drop_sub = QLabel("Screenshot, GIF, or video clip")
        self._drop_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._drop_sub.setStyleSheet(f"color: {theme.TEXT_MUTED}; font-size: {theme.FONT_SM}px;")
        dz_layout.addWidget(self._drop_sub)

        # Cancel button to remove the selected file before searching. It's
        # overlaid on the drop zone and hidden until needed.
        self._cancel_btn = QPushButton("✕", self._drop_zone)
        self._cancel_btn.setFixedSize(24, 24)
        self._cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._cancel_btn.setToolTip("Remove selected file")
        self._cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background: {theme.BG_ELEVATED};
                border: 1px solid {theme.BORDER_DEFAULT};
                border-radius: 12px;
                color: {theme.TEXT_MUTED};
                font-size: {theme.FONT_SM}px;
            }}
            QPushButton:hover {{
                background: {theme.BG_HOVER};
                color: {theme.TEXT_PRIMARY};
            }}
        """)
        self._cancel_btn.setVisible(False)
        self._cancel_btn.clicked.connect(self.reset)
        self._cancel_btn.raise_()  # always on top, even above the preview background

        card_layout.addWidget(self._drop_zone)

        card_layout.addSpacing(16)

        # Divider
        self._divider_container = QWidget()
        divider = QHBoxLayout(self._divider_container)
        divider.setSpacing(12)
        divider.setContentsMargins(0, 0, 0, 0)

        left_line = QWidget()
        left_line.setFixedHeight(1)
        left_line.setStyleSheet(f"background: {theme.BORDER_SUBTLE};")
        left_line.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        divider.addWidget(left_line)

        or_label = QLabel("or")
        or_label.setStyleSheet(f"color: {theme.TEXT_GHOST}; font-size: {theme.FONT_SM}px;")
        or_label.setContentsMargins(4, 0, 4, 0)
        divider.addWidget(or_label)

        right_line = QWidget()
        right_line.setFixedHeight(1)
        right_line.setStyleSheet(f"background: {theme.BORDER_SUBTLE};")
        right_line.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        divider.addWidget(right_line)

        card_layout.addWidget(self._divider_container)

        self._divider_opacity = QGraphicsOpacityEffect(self._divider_container)
        self._divider_container.setGraphicsEffect(self._divider_opacity)
        self._divider_opacity.setOpacity(1.0)

        self._divider_fade = QPropertyAnimation(self._divider_opacity, b"opacity")
        self._divider_fade.setDuration(220)
        self._divider_fade.setEasingCurve(QEasingCurve.Type.InOutQuad)

        card_layout.addSpacing(16)

        # Wrap everything below in one container so hiding it also removes the
        # layout spacing, keeping the transition clean.
        self._input_controls = QWidget()
        input_controls_layout = QVBoxLayout(self._input_controls)
        input_controls_layout.setContentsMargins(0, 0, 0, 0)
        input_controls_layout.setSpacing(0)

        # Browse btn
        self._browse_btn = QPushButton("Browse files")
        self._browse_btn.setStyleSheet(theme.browse_btn_style())
        self._browse_btn.setFixedWidth(160)
        self._browse_btn.clicked.connect(self._browse)
        input_controls_layout.addWidget(self._browse_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        input_controls_layout.addSpacing(16)

        # Video options row (hidden until a video is selected)
        self._video_options = QWidget()
        self._video_options.setFixedHeight(24)
        self._video_options.setEnabled(False)
        video_opts_layout = QHBoxLayout(self._video_options)
        video_opts_layout.setContentsMargins(0, 0, 0, 0)
        video_opts_layout.setSpacing(8)

        self._frames_label = QLabel("Frames: Auto")
        self._frames_label.setStyleSheet(f"color: {theme.TEXT_DIM}; font-size: {theme.FONT_SM}px;")
        video_opts_layout.addWidget(self._frames_label)

        change_frames_btn = QPushButton("Change")
        change_frames_btn.setStyleSheet(f"""
            QPushButton {{
                background: none;
                border: none;
                color: {theme.ACCENT};
                font-size: {theme.FONT_SM}px;
            }}
            QPushButton:hover {{
                color: {theme.TEXT_PRIMARY};
            }}
        """)
        change_frames_btn.clicked.connect(self._open_frame_picker)
        video_opts_layout.addWidget(change_frames_btn)
        video_opts_layout.addStretch()

        input_controls_layout.addWidget(self._video_options)

        self._video_opts_opacity = QGraphicsOpacityEffect(self._video_options)
        self._video_options.setGraphicsEffect(self._video_opts_opacity)
        self._video_opts_opacity.setOpacity(0.0)

        self._video_opts_fade = QPropertyAnimation(self._video_opts_opacity, b"opacity")
        self._video_opts_fade.setDuration(220)
        self._video_opts_fade.setEasingCurve(QEasingCurve.Type.InOutQuad)

        input_controls_layout.addSpacing(8)

        # Search button (hidden until a file is selected)
        self._search_btn = QPushButton("Search")
        self._search_btn.setStyleSheet(theme.search_btn_style())
        self._search_btn.setFixedWidth(160)
        self._search_btn.setVisible(False)
        self._search_btn.clicked.connect(self._on_search)
        input_controls_layout.addWidget(self._search_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        card_layout.addWidget(self._input_controls)

        card_layout.addSpacing(16)

        # Progress section, shown while searching. The input controls are hidden
        # since they aren't usable during analysis.
        self._progress_widget = QWidget()
        self._progress_widget.setVisible(False)
        prog_layout = QVBoxLayout(self._progress_widget)
        prog_layout.setContentsMargins(0, 4, 0, 4)
        prog_layout.setSpacing(8)

        self._prog_analyzing = QLabel("Analyzing frame")
        self._prog_analyzing.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._prog_analyzing.setStyleSheet(f"color: {theme.ACCENT}; font-size: {theme.FONT_LG}px; font-weight: 600;")
        prog_layout.addWidget(self._prog_analyzing)

        self._prog_count = QLabel("")
        self._prog_count.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._prog_count.setStyleSheet(f"color: {theme.ACCENT}; font-size: {theme.FONT_SM}px; font-weight: 600;")
        prog_layout.addWidget(self._prog_count)

        # Walking track for the loading animation. The character moves across
        # the full width of the track while cycling through poses to create the
        # walking effect. The animation distance is calculated when it starts,
        # since the track's size is determined by the layout.
        _ICON_HEIGHT = 48

        self._run_frames: list[QPixmap] = []
        for i in range(1, _RUN_CYCLE_FRAME_COUNT + 1):
            pixmap = load_pixmap(_RUN_CYCLE_DIR / f"frame_{i}.png")
            if pixmap is not None:
                self._run_frames.append(pixmap.scaledToHeight(
                    _ICON_HEIGHT, Qt.TransformationMode.SmoothTransformation
                ))
        self._run_icon_width = self._run_frames[0].width() if self._run_frames else 30

        self._walk_track = QWidget()
        self._walk_track.setFixedHeight(_ICON_HEIGHT)
        self._walk_track.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self._run_frame_index = 0
        self._run_icon = QLabel(self._walk_track)
        self._run_icon.setFixedSize(self._run_icon_width, _ICON_HEIGHT)
        if self._run_frames:
            self._run_icon.setPixmap(self._run_frames[0])
        else:
            self._run_icon.setText("🔎")
            self._run_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._run_icon.setStyleSheet("font-size: 22px;")
        self._run_icon.move(0, 0)

        # Movement and pose are driven by the same timer so they always stay in
        # sync. The current pose is based on the character's position along the
        # track, creating a natural walk cycle
        self._walk_elapsed_ms = 0
        self._walk_duration_ms = 1000  # recomputed in start_progress() from real track width
        self._walk_timer = QTimer(self)
        self._walk_timer.timeout.connect(self._advance_walk)
        self._walk_tick_ms = 30  # ~33fps - smooth enough to not look like a slideshow bs

        prog_layout.addWidget(self._walk_track)

        bar_row = QWidget()
        bar_row.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        bar_row_layout = QVBoxLayout(bar_row)
        bar_row_layout.setContentsMargins(0, 4, 0, 0)
        self._progress_bar = QProgressBar()
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setFixedHeight(6)
        self._progress_bar.setStyleSheet(theme.progress_bar_style())
        bar_row_layout.addWidget(self._progress_bar)
        prog_layout.addWidget(bar_row)

        card_layout.addWidget(self._progress_widget)

        layout.addWidget(self._card)
        layout.addStretch()

        # Ctrl+V
        paste_shortcut = QShortcut(QKeySequence("Ctrl+V"), self)
        paste_shortcut.activated.connect(self._on_paste)

    # Layout events

    def paintEvent(self, event) -> None:
        """
        Paint the local background image scaled to cover the whole screen.
        """
        if self._bg_pixmap is not None:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
            draw_cover_background(painter, self.rect(), self._bg_pixmap)
            painter.end()
        super().paintEvent(event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        # paintEvent reads the live size, so just trigger a repaint.
        self.update()
        # Resize the preview background and reposition the cancel button once
        # the drop zone's layout size is known.
        self._reposition_cancel_btn()
        self._resize_upload_preview()

    def _reposition_cancel_btn(self) -> None:
        margin = 10
        x = self._drop_zone.width() - self._cancel_btn.width() - margin
        self._cancel_btn.move(max(0, x), margin)

    def _resize_upload_preview(self) -> None:
        """
        Keep the preview background covering the entire drop zone. 

        It isnt part of the layout, so its geometry is updated manually.
        """
        self._upload_preview.setGeometry(0, 0, self._drop_zone.width(), self._drop_zone.height())

    def _advance_walk(self) -> None:
        """
        Single tick of the walk animation.

        A single incrementing clock drives both position and pose. The pose
        cycles faster than the full walk duration, allowing multiple visible
        steps during one crossing while keeping movement and animation fully
        in sync.
        """
        self._walk_elapsed_ms += self._walk_tick_ms

        t_pos = (self._walk_elapsed_ms % self._walk_duration_ms) / self._walk_duration_ms
        distance = max(self._walk_track.width() - self._run_icon_width, 0)
        self._run_icon.move(int(t_pos * distance), 0)

        if self._run_frames:
            t_pose = (self._walk_elapsed_ms % _POSE_CYCLE_MS) / _POSE_CYCLE_MS
            frame_index = min(int(t_pose * len(self._run_frames)), len(self._run_frames) - 1)
            if frame_index != self._run_frame_index:
                self._run_frame_index = frame_index
                self._run_icon.setPixmap(self._run_frames[frame_index])

    # Drop zone events

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self._drop_zone.setStyleSheet(theme.drop_zone_style(hover=True, transparent=True))

    def dragLeaveEvent(self, event) -> None:
        self._drop_zone.setStyleSheet(theme.drop_zone_style(hover=False, transparent=True))

    def dropEvent(self, event: QDropEvent) -> None:
        self._drop_zone.setStyleSheet(theme.drop_zone_style(hover=False, transparent=True))
        urls = event.mimeData().urls()
        if urls:
            self._on_file_picked(urls[0].toLocalFile())

    # File picking

    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select a file", "", _ALLOWED_FORMATS,
        )
        if path:
            self._on_file_picked(path)

    def _on_paste(self) -> None:
        self._current_path = ""
        self._max_frames = None
        self._search_btn.setVisible(True)
        self._set_video_options_visible(False)
        self._cancel_btn.setVisible(True)
        self._reposition_cancel_btn()
        self._fade_out_divider()

        self._drop_zone.setStyleSheet(theme.drop_zone_style(selected=True, transparent=True))
        self._upload_icon.setText("📋")
        self._upload_icon.setStyleSheet(f"color: {theme.ACCENT}; font-size: 28px;")
        self._set_drop_title("Pasted from clipboard")
        self._drop_sub.setText("Image")

    def _on_file_picked(self, path: str) -> None:
        """
        Called when a file is dropped or browsed.
        Shows the search button and video options if it's a video.
        """
        self._current_path = path
        self._max_frames = None
        filename = Path(path).name
        suffix = Path(path).suffix.lower()
        is_video = suffix not in _STILL_EXTENSIONS

        self._set_drop_title(filename)
        self._drop_sub.setText("Video" if is_video else "Image")
        self._set_video_options_visible(is_video)
        self._frames_label.setText("Frames: Auto")
        self._search_btn.setVisible(True)
        self._cancel_btn.setVisible(True)
        self._reposition_cancel_btn()
        self._fade_out_divider()

        # Show emoji first - when its possible, change to the preview.
        self._drop_zone.setStyleSheet(theme.drop_zone_style(selected=True, transparent=True))
        self._upload_preview.setVisible(False)
        self._upload_preview.set_pixmap(None)
        self._upload_icon.setVisible(True)
        self._upload_icon.setPixmap(QPixmap())
        self._upload_icon.setText("🎬" if is_video else "🖼️")
        self._upload_icon.setStyleSheet(f"color: {theme.ACCENT}; font-size: 28px;")

        if is_video:
            self._start_thumbnail_worker(path)
        else:
            self._set_upload_preview_from_file(path)

    def _set_upload_preview_from_file(self, path: str) -> None:
        """
        Load and display the image as a cover-cropped preview banner.

        Falls back to the emoji if the image cant be read.
        """
        try:
            pixmap = QPixmap(path)
            if pixmap.isNull():
                return
            self._show_upload_preview(pixmap)
        except Exception:
            pass

    def _start_thumbnail_worker(self, path: str) -> None:
        """
        Start a background thread to get the videos first frame. 
        
        The emoji fallback is already shown, and will be replaced once the frame is ready.
        """
        self._thumbnail_worker = ThumbnailWorker(path)
        self._thumbnail_worker.finished.connect(
            lambda jpeg_bytes: self._on_thumbnail_ready(path, jpeg_bytes)
        )
        self._thumbnail_worker.error.connect(lambda _msg: None)  # keep the emoji fallback, no popup needed
        self._thumbnail_worker.start()

    def _on_thumbnail_ready(self, path: str, jpeg_bytes: bytes) -> None:
        """
        Background loaded thumbnail is ready. 

        Apply only if the file hasnt changed since the request started(cancel option).
        """
        if path != self._current_path:
            return
        pixmap = QPixmap()
        if not pixmap.loadFromData(jpeg_bytes, "JPEG"):
            return
        self._show_upload_preview(pixmap)

    def _show_upload_preview(self, pixmap: QPixmap) -> None:
        """
        Switch from fallback icon to full drop zone preview background when the image is ready.
        
        It sits behind the layout so text renders on top.
        """
        self._upload_icon.setVisible(False)
        self._resize_upload_preview()  # don't wait for the next resize event
        self._upload_preview.set_pixmap(pixmap)
        self._upload_preview.setVisible(True)
        self._upload_preview.lower()
        self._cancel_btn.raise_()

    def _set_drop_title(self, text: str) -> None:
        """
        Set the drop zone title, eliding long filenames in the middle if needed
        to fit. This keeps both the start of the name and the file extension
        visible.
        """
        metrics = QFontMetrics(self._drop_title.font())
        available_width = self._drop_zone.width() - 64  # zone padding + a safety margin
        elided = metrics.elidedText(text, Qt.TextElideMode.ElideMiddle, max(available_width, 40))
        self._drop_title.setText(elided)
        self._drop_title.setToolTip(text)  # full name still available on hover

    def _set_video_options_visible(self, visible: bool) -> None:
        """
        Fade the video options row in or out without changing its visibility.
        Its space stays reserved so the layout doesn't shift.
        """
        self._video_options.setEnabled(visible)
        self._video_opts_fade.stop()
        try:
            self._video_opts_fade.finished.disconnect()
        except TypeError:
            pass
        self._video_opts_fade.setStartValue(self._video_opts_opacity.opacity())
        self._video_opts_fade.setEndValue(1.0 if visible else 0.0)
        self._video_opts_fade.start()

    def _fade_out_divider(self) -> None:
        """
        Fade the "or" divider out once a file is picked - hide it so it stops taking space in layout.

        Meant to be called repeatedly, reset it once file is done.
        """
        if not self._divider_container.isVisible():
            return
        self._divider_fade.stop()
        try:
            self._divider_fade.finished.disconnect()
        except TypeError:
            pass  # nothing was connected yet
        self._divider_fade.setStartValue(self._divider_opacity.opacity())
        self._divider_fade.setEndValue(0.0)
        self._divider_fade.finished.connect(lambda: self._divider_container.setVisible(False))
        self._divider_fade.start()

    def _fade_in_divider(self) -> None:
        """
        Bring the divider back - used on reset, when there's no file selected again.
        """
        self._divider_fade.stop()
        try:
            self._divider_fade.finished.disconnect()
        except TypeError:
            pass
        self._divider_container.setVisible(True)
        self._divider_opacity.setOpacity(0.0)
        self._divider_fade.setStartValue(0.0)
        self._divider_fade.setEndValue(1.0)
        self._divider_fade.start()

    def _open_frame_picker(self) -> None:
        dialog = FramePickerDialog(self)
        if dialog.exec():
            self._max_frames = dialog.value()
            self._frames_label.setText(f"Frames: {self._max_frames}")

    def _on_search(self) -> None:
        self.search_requested.emit(self._current_path, self._max_frames)

    # Progress API

    def start_progress(self, total_frames: Optional[int] = None) -> None:
        """
        Analysis has started, so all search/browse controls are hidden and the
        progress display takes the full space. Nothing is actionable until the
        process completes.

        total_frames may be None because the backend search is a single
        blocking call and does not stream progress.

        Three states are supported:
        - total_frames == 1: a still image, so "Frame 1 of 1" is shown.
        - total_frames is None: the frame count is unknown, so an
        indeterminate progress bar is shown.
        - total_frames > 1: the total frame count is known, so "Analyzing N
        frames" is shown.

        Since progress is not tracked per frame, labels such as "Frame 1 of N"
        are avoided when N > 1.
        """
        if total_frames == 1:
            self._prog_analyzing.setText("Analyzing frame")
            self._progress_bar.setRange(0, 0)  
            self._prog_count.setText("Frame 1 of 1")
        elif total_frames and total_frames > 1:
            self._prog_analyzing.setText("Analyzing frames")
            self._progress_bar.setRange(0, 0)  
            self._prog_count.setText(f"Analyzing {total_frames} frames")
        else:
            # Always use the plural label for videos/GIFs in Auto mode to avoid
            # carrying over the singular from a previous image search.
            self._prog_analyzing.setText("Analyzing frames")
            self._progress_bar.setRange(0, 0)  
            self._prog_count.setText("")
        self._progress_widget.setVisible(True)

        self._run_frame_index = 0
        if self._run_frames:
            self._run_icon.setPixmap(self._run_frames[0])
        self._run_icon.move(0, 0)

        # Track width is determined after layout, so compute distance at runtime
        # and scale animation duration to maintain constant pixel speed.
        distance = max(self._walk_track.width() - self._run_icon_width, 10)
        self._walk_duration_ms = max(int(distance / _WALK_SPEED_PX_PER_SEC * 1000), 1)
        self._walk_elapsed_ms = 0
        self._walk_timer.start(self._walk_tick_ms)

        self._input_controls.setVisible(False)
        self._cancel_btn.setVisible(False)

        # Qt grows widgets automatically but doesn't reliably shrink them, so
        # force a resize when sizeHint changes.
        self._input_controls.adjustSize()
        self._input_controls.updateGeometry()
        self._card.layout().invalidate()
        self._card.layout().activate()
        self.layout().invalidate()
        self.layout().activate()

    def update_progress(self, frame_index: int, total_frames: int) -> None:
        """
        Called after analysis completes, when the total frame count is known.
        Switches the progress bar from indeterminate to determinate mode.

        total_frames is passed explicitly since the progress bar remains in
        indeterminate mode during analysis, so its range doesn't reflect the
        real frame count.
        """
        if self._progress_bar.maximum() != total_frames:
            self._progress_bar.setRange(0, total_frames)
        self._progress_bar.setValue(frame_index + 1)
        self._prog_count.setText(f"Frame {min(frame_index + 1, total_frames)} of {total_frames}")

    def reset(self) -> None:
        self._progress_widget.setVisible(False)
        self._progress_bar.setValue(0)
        self._walk_timer.stop()
        self._input_controls.setVisible(True)
        self._drop_zone.setStyleSheet(theme.drop_zone_style(hover=False, transparent=True))
        self._upload_preview.setVisible(False)
        self._upload_preview.set_pixmap(None)
        self._upload_icon.setVisible(True)
        self._upload_icon.setPixmap(QPixmap())
        self._upload_icon.setText("↑")
        self._upload_icon.setStyleSheet(f"color: {theme.TEXT_DEEP}; font-size: 28px;")
        self._drop_title.setText("Drop your file here")
        self._drop_title.setToolTip("")
        self._drop_sub.setText("Screenshot, GIF, or video clip")
        self._search_btn.setVisible(False)
        self._set_video_options_visible(False)
        self._cancel_btn.setVisible(False)
        self._fade_in_divider()
        self._current_path = ""
        self._max_frames = None

        # input_controls was stuck at its previous size even after the search
        # button was hidden, so force a resize after sizeHint changes.
        self._input_controls.adjustSize()
        self._input_controls.updateGeometry()
        self._card.layout().invalidate()
        self._card.layout().activate()
        self.layout().invalidate()
        self.layout().activate()
