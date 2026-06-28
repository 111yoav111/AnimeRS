from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QPushButton, QFileDialog, QProgressBar, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, QMimeData
from PyQt6.QtGui import QKeySequence, QShortcut, QDragEnterEvent, QDropEvent

from ui import theme


# Allowed formats for the file dialog filter
_ALLOWED_FORMATS = "Media files (*.jpg *.jpeg *.png *.webp *.bmp *.tiff *.tif *.gif *.mp4 *.mkv *.webm *.mov *.avi)"


class UploadScreen(QWidget):
    # Emits the file path - main_window listens and kicks off the search
    file_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)

        self._frame_dots: list[QLabel] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 28, 24, 28)
        layout.setSpacing(0)

        # Header
        eyebrow = QLabel("Anime Reverse Search")
        eyebrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
        eyebrow.setStyleSheet(f"""
            QLabel {{
                color: {theme.ACCENT};
                font-size: {theme.FONT_XS}px;
                letter-spacing: 2px;
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

        upload_icon = QLabel("↑")
        upload_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        upload_icon.setStyleSheet(f"color: {theme.TEXT_DEEP}; font-size: 28px;")
        dz_layout.addWidget(upload_icon)

        drop_title = QLabel("Drop your file here")
        drop_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        drop_title.setStyleSheet(f"color: {theme.TEXT_PRIMARY}; font-size: {theme.FONT_LG}px; font-weight: 500;")
        dz_layout.addWidget(drop_title)

        drop_sub = QLabel("Screenshot, GIF, or video clip")
        drop_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        drop_sub.setStyleSheet(f"color: {theme.TEXT_FAINT}; font-size: {theme.FONT_SM}px;")
        dz_layout.addWidget(drop_sub)

        layout.addWidget(self._drop_zone)

        layout.addSpacing(16)

        # Divider
        divider = QHBoxLayout()
        divider.setSpacing(12)

        left_line = QFrame()
        left_line.setFrameShape(QFrame.Shape.HLine)
        left_line.setStyleSheet(f"color: {theme.BORDER_SUBTLE};")
        divider.addWidget(left_line)

        or_label = QLabel("or")
        or_label.setStyleSheet(f"color: {theme.TEXT_GHOST}; font-size: {theme.FONT_SM}px;")
        divider.addWidget(or_label)

        right_line = QFrame()
        right_line.setFrameShape(QFrame.Shape.HLine)
        right_line.setStyleSheet(f"color: {theme.BORDER_SUBTLE};")
        divider.addWidget(right_line)

        layout.addLayout(divider)

        layout.addSpacing(16)

        # Browe btn
        browse_btn = QPushButton("Browse files")
        browse_btn.setStyleSheet(theme.browse_btn_style())
        browse_btn.setFixedWidth(160)
        browse_btn.clicked.connect(self._browse)
        layout.addWidget(browse_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        layout.addSpacing(24)

        # Progress section (hidden until search starts) 
        self._progress_widget = QWidget()
        self._progress_widget.setVisible(False)
        prog_layout = QVBoxLayout(self._progress_widget)
        prog_layout.setContentsMargins(0, 0, 0, 0)
        prog_layout.setSpacing(8)

        # Label row
        prog_top = QHBoxLayout()
        prog_analyzing = QLabel("Analyzing frames")
        prog_analyzing.setStyleSheet(f"color: {theme.TEXT_DIM}; font-size: {theme.FONT_SM}px;")
        prog_top.addWidget(prog_analyzing)
        prog_top.addStretch()
        self._prog_count = QLabel("0 / 0")
        self._prog_count.setStyleSheet(f"color: {theme.ACCENT}; font-size: {theme.FONT_SM}px;")
        prog_top.addWidget(self._prog_count)
        prog_layout.addLayout(prog_top)

        # Progress bar
        self._progress_bar = QProgressBar()
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setFixedHeight(3)
        self._progress_bar.setStyleSheet(theme.progress_bar_style())
        prog_layout.addWidget(self._progress_bar)

        # Frame dots row
        self._dots_row = QHBoxLayout()
        self._dots_row.setSpacing(6)
        self._dots_row.setAlignment(Qt.AlignmentFlag.AlignLeft)
        prog_layout.addLayout(self._dots_row)

        layout.addWidget(self._progress_widget)
        layout.addStretch()

        #  Ctrl+V option
        paste_shortcut = QShortcut(QKeySequence("Ctrl+V"), self)
        paste_shortcut.activated.connect(self._on_paste)


    # ---------Helpers-----------

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
            path = urls[0].toLocalFile()
            self.file_selected.emit(path)


    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select a file",
            "",
            _ALLOWED_FORMATS,
        )
        if path:
            self.file_selected.emit(path)


    def _on_paste(self) -> None:
        # Tells main_window to call the /search/paste endpoint
        # Emits an empty string as a convention - main_window handles it separately
        self.file_selected.emit("")


    def start_progress(self, total_frames: int) -> None:
        """
        Show the progress section and build the frame dots for this search.
        Called by main_window when a search kicks off.
        """
        self._frame_dots.clear()

        # Clear old dots
        while self._dots_row.count():
            item = self._dots_row.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self._progress_bar.setMaximum(total_frames)
        self._progress_bar.setValue(0)
        self._prog_count.setText(f"0 / {total_frames}")

        for i in range(total_frames):
            dot = QLabel(str(i + 1))
            dot.setFixedSize(28, 28)
            dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
            dot.setStyleSheet(theme.frame_dot_style("default"))
            self._frame_dots.append(dot)
            self._dots_row.addWidget(dot)

        self._progress_widget.setVisible(True)

    def update_progress(self, frame_index: int) -> None:
        """
        Mark frame at frame_index as done, advance the active dot.
        Called by main_window on each worker progress signal.
        """
        total = len(self._frame_dots)
        if frame_index < total:
            self._frame_dots[frame_index].setStyleSheet(theme.frame_dot_style("done"))
        if frame_index + 1 < total:
            self._frame_dots[frame_index + 1].setStyleSheet(theme.frame_dot_style("active"))

        done = frame_index + 1
        self._progress_bar.setValue(done)
        self._prog_count.setText(f"{done} / {total}")

    def reset(self) -> None:
        """
        Reset screen back to initial state — called when user goes back.
        """
        self._progress_widget.setVisible(False)
        self._progress_bar.setValue(0)
        self._frame_dots.clear()
        self._drop_zone.setStyleSheet(theme.drop_zone_style(hover=False))
        