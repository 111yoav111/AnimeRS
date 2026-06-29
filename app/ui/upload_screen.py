from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QPushButton, QFileDialog, QProgressBar, QSizePolicy,
    QDialog, QSpinBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QKeySequence, QShortcut, QDragEnterEvent, QDropEvent

from ui import theme


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

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 28, 24, 28)
        layout.setSpacing(0)

        # Header
        eyebrow = QLabel("Anime Reverse Search")
        eyebrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
        eyebrow.setStyleSheet(f"""
            QLabel {{
                color: {theme.ACCENT};
                font-size: {theme.FONT_LG}px;
                letter-spacing: 3px;
            }}
        """)
        layout.addWidget(eyebrow)

        layout.addSpacing(6)

        heading = QLabel("What anime is this?")
        heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        heading.setStyleSheet(f"""
            QLabel {{
                color: {theme.TEXT_PRIMARY};
                font-size: {theme.FONT_2XL}px;
                font-weight: 500;
            }}
        """)
        layout.addWidget(heading)

        layout.addSpacing(24)

        # Drop area
        self._drop_zone = QFrame()
        self._drop_zone.setObjectName("drop_zone")
        self._drop_zone.setStyleSheet(theme.drop_zone_style(hover=False))
        self._drop_zone.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._drop_zone.setMinimumHeight(200)

        dz_layout = QVBoxLayout(self._drop_zone)
        dz_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dz_layout.setSpacing(12)
        dz_layout.setContentsMargins(16, 32, 16, 32)

        self._upload_icon = QLabel("↑")
        self._upload_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._upload_icon.setStyleSheet(f"color: {theme.TEXT_DEEP}; font-size: 28px;")
        dz_layout.addWidget(self._upload_icon)

        self._drop_title = QLabel("Drop your file here")
        self._drop_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._drop_title.setStyleSheet(f"color: {theme.TEXT_PRIMARY}; font-size: {theme.FONT_LG}px; font-weight: 500;")
        dz_layout.addWidget(self._drop_title)

        self._drop_sub = QLabel("Screenshot, GIF, or video clip")
        self._drop_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._drop_sub.setStyleSheet(f"color: {theme.TEXT_FAINT}; font-size: {theme.FONT_SM}px;")
        dz_layout.addWidget(self._drop_sub)

        layout.addWidget(self._drop_zone)

        layout.addSpacing(16)

        # Divider
        divider = QHBoxLayout()
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

        layout.addLayout(divider)

        layout.addSpacing(16)

        # Browse btn
        browse_btn = QPushButton("Browse files")
        browse_btn.setStyleSheet(theme.browse_btn_style())
        browse_btn.setFixedWidth(160)
        browse_btn.clicked.connect(self._browse)
        layout.addWidget(browse_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        layout.addSpacing(16)

        # Video options row (hidden until a video is selected)
        self._video_options = QWidget()
        self._video_options.setVisible(False)
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

        layout.addWidget(self._video_options)

        layout.addSpacing(8)

        # Search button (hidden until a file is selected)
        self._search_btn = QPushButton("Search")
        self._search_btn.setStyleSheet(theme.search_btn_style())
        self._search_btn.setFixedWidth(160)
        self._search_btn.setVisible(False)
        self._search_btn.clicked.connect(self._on_search)
        layout.addWidget(self._search_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        layout.addSpacing(16)

        # Progress section (hidden until search starts)
        self._progress_widget = QWidget()
        self._progress_widget.setVisible(False)
        prog_layout = QVBoxLayout(self._progress_widget)
        prog_layout.setContentsMargins(0, 0, 0, 0)
        prog_layout.setSpacing(8)

        prog_top = QHBoxLayout()
        prog_analyzing = QLabel("Analyzing frames")
        prog_analyzing.setStyleSheet(f"color: {theme.TEXT_DIM}; font-size: {theme.FONT_SM}px;")
        prog_top.addWidget(prog_analyzing)
        prog_top.addStretch()
        self._prog_count = QLabel("")
        self._prog_count.setStyleSheet(f"color: {theme.ACCENT}; font-size: {theme.FONT_SM}px;")
        prog_top.addWidget(self._prog_count)
        prog_layout.addLayout(prog_top)

        self._progress_bar = QProgressBar()
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setFixedHeight(3)
        self._progress_bar.setStyleSheet(theme.progress_bar_style())
        prog_layout.addWidget(self._progress_bar)

        layout.addWidget(self._progress_widget)
        layout.addStretch()

        # Ctrl+V
        paste_shortcut = QShortcut(QKeySequence("Ctrl+V"), self)
        paste_shortcut.activated.connect(self._on_paste)

    # Drop zone events

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self._drop_zone.setStyleSheet(theme.drop_zone_style(hover=True))

    def dragLeaveEvent(self, event) -> None:
        self._drop_zone.setStyleSheet(theme.drop_zone_style(hover=False))

    def dropEvent(self, event: QDropEvent) -> None:
        self._drop_zone.setStyleSheet(theme.drop_zone_style(hover=False))
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
        self._video_options.setVisible(False)

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

        self._drop_title.setText(filename)
        self._drop_sub.setText("Video" if is_video else "Image")
        self._video_options.setVisible(is_video)
        self._frames_label.setText("Frames: Auto")
        self._search_btn.setVisible(True)

    def _open_frame_picker(self) -> None:
        dialog = FramePickerDialog(self)
        if dialog.exec():
            self._max_frames = dialog.value()
            self._frames_label.setText(f"Frames: {self._max_frames}")

    def _on_search(self) -> None:
        self.search_requested.emit(self._current_path, self._max_frames)

    # Progress API

    def start_progress(self, total_frames: int) -> None:
        self._progress_bar.setMaximum(max(total_frames, 1))
        self._progress_bar.setValue(0)
        self._prog_count.setText("Analyzing...")
        self._progress_widget.setVisible(True)

    def update_progress(self, frame_index: int) -> None:
        self._progress_bar.setValue(frame_index + 1)
        self._prog_count.setText("Analyzing...")

    def reset(self) -> None:
        self._progress_widget.setVisible(False)
        self._progress_bar.setValue(0)
        self._drop_zone.setStyleSheet(theme.drop_zone_style(hover=False))
        self._drop_title.setText("Drop your file here")
        self._drop_sub.setText("Screenshot, GIF, or video clip")
        self._search_btn.setVisible(False)
        self._video_options.setVisible(False)
        self._current_path = ""
        self._max_frames = None
        