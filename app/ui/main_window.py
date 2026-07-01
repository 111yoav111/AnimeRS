from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QStackedWidget,
    QHBoxLayout, QVBoxLayout, QLabel, QMessageBox
)
from PyQt6.QtCore import Qt

from ui.theme import (
    BG_APP, DOT_RED, DOT_YELLOW, DOT_GREEN,
    WINDOW_WIDTH, WINDOW_HEIGHT,
    titlebar_style, app_style, credit_style,
)
from ui.upload_screen import UploadScreen
from ui.result_screen import ResultScreen
from ui.search_worker import SearchWorker


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AnimeRS")
        self.setFixedSize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setStyleSheet(app_style())

        self._current_filename = ""
        self._worker = None

        root = QWidget()
        root.setObjectName("central")
        self.setCentralWidget(root)

        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # Titlebar
        titlebar = QWidget()
        titlebar.setObjectName("titlebar")
        titlebar.setFixedHeight(44)
        titlebar.setStyleSheet(titlebar_style())

        tb_layout = QHBoxLayout(titlebar)
        tb_layout.setContentsMargins(16, 0, 16, 0)
        tb_layout.setSpacing(8)

        for color in (DOT_RED, DOT_YELLOW, DOT_GREEN):
            dot = QLabel()
            dot.setFixedSize(12, 12)
            dot.setStyleSheet(f"""
                QLabel {{
                    background: {color};
                    border-radius: 6px;
                }}
            """)
            tb_layout.addWidget(dot)

        tb_layout.addStretch()

        title_label = QLabel("AnimeRS")
        title_label.setObjectName("titlebar_label")
        tb_layout.addWidget(title_label)

        tb_layout.addStretch()

        # placeholder to balance the dots on the right side
        spacer = QWidget()
        spacer.setFixedWidth(12 * 3 + (8 * 2))  # 3 dots + 2 gaps
        tb_layout.addWidget(spacer)

        root_layout.addWidget(titlebar)

        # Screens
        self.stack = QStackedWidget()

        self._upload_screen = UploadScreen()
        self._result_screen = ResultScreen()

        self.stack.addWidget(self._upload_screen)  # index 0
        self.stack.addWidget(self._result_screen)  # index 1

        root_layout.addWidget(self.stack, stretch=1)

        # Dev by
        credit_bar = QWidget()
        credit_bar.setStyleSheet(f"background: {BG_APP};")
        credit_layout = QHBoxLayout(credit_bar)
        credit_layout.setContentsMargins(16, 6, 16, 10)

        credit_label = QLabel("Developed by 111yoav111")
        credit_label.setStyleSheet(credit_style())
        credit_layout.addWidget(credit_label, alignment=Qt.AlignmentFlag.AlignLeft)

        root_layout.addWidget(credit_bar)

        # Signals
        self._upload_screen.search_requested.connect(self._on_search_requested)
        self._result_screen.go_back.connect(self._on_go_back)

    # Slots

    def _on_search_requested(self, path: str, max_frames) -> None:
        """
        User clicked Search - call the worker with the file and frame count.
        max_frames is None (auto) or an int (user picked).
        """
        self._current_filename = path.split("/")[-1].split("\\")[-1] if path else ""

        # Show analyzing state while we wait for the backend
        self._upload_screen.start_progress(1)

        self._worker = SearchWorker(file_path=path, max_frames=max_frames)
        self._worker.finished.connect(self._on_search_finished)
        self._worker.error.connect(self._on_search_error)
        self._worker.start()

    def _on_search_finished(self, verdict: dict) -> None:
        """
        Worker finished - populate result screen and switch to it.
        """
        frames_total = verdict.get("frames_total", 1)
        self._upload_screen.start_progress(frames_total)
        for i in range(frames_total):
            self._upload_screen.update_progress(i)

        self._result_screen.show_result(verdict, self._current_filename)
        self.show_screen(1)

    def _on_search_error(self, message: str) -> None:
        """
        Worker hit an error - show a message box, reset upload screen.
        """
        self._upload_screen.reset()
        QMessageBox.critical(self, "Search failed", message)

    def _on_go_back(self) -> None:
        """
        User clicked back / try again - reset and go to upload screen.
        """
        self._upload_screen.reset()
        self.show_screen(0)

    def show_screen(self, index: int) -> None:
        """
        Switch the visible screen by stack index.
        0 = upload screen, 1 = result screen.
        """
        self.stack.setCurrentIndex(index)
        