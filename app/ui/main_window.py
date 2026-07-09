from pathlib import Path

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QStackedWidget,
    QHBoxLayout, QVBoxLayout, QLabel, QMessageBox
)
from PyQt6.QtCore import Qt

import frame_extractor
from ui.theme import (
    BG_APP, DOT_RED, DOT_YELLOW, DOT_GREEN,
    WINDOW_WIDTH, WINDOW_HEIGHT,
    titlebar_style, app_style, credit_style,
)
from ui.upload_screen import UploadScreen, _STILL_EXTENSIONS
from ui.result_screen import ResultScreen
from ui.history_screen import HistoryScreen
from ui.search_worker import ProbeWorker, SearchWorker, HistoryWorker


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AnimeRS")
        self.setFixedSize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setStyleSheet(app_style())

        self._current_filename = ""
        self._worker = None
        self._history_return_index = 0  # screen to restore when leaving history

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

        tb_layout.addStretch()

        title_label = QLabel("AnimeRS")
        title_label.setObjectName("titlebar_label")
        tb_layout.addWidget(title_label)

        tb_layout.addStretch()

        root_layout.addWidget(titlebar)

        # Screens
        self.stack = QStackedWidget()

        self._upload_screen = UploadScreen()
        self._result_screen = ResultScreen()
        self._history_screen = HistoryScreen()

        self.stack.addWidget(self._upload_screen)  # index 0
        self.stack.addWidget(self._result_screen)  # index 1
        self.stack.addWidget(self._history_screen)  # index 2

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
        self._upload_screen.show_history_requested.connect(self._on_show_history)
        self._result_screen.go_back.connect(self._on_go_back)
        self._result_screen.show_history_requested.connect(self._on_show_history)
        self._history_screen.go_back.connect(self._on_history_back)
        self._history_screen.entry_selected.connect(self._on_history_entry_selected)

    # Slots

    def _on_search_requested(self, path: str, max_frames) -> None:
        """
        User clicked Search - call the worker with the file and frame count.
        max_frames is None (auto) or an int (user picked).
        """
        self._current_filename = Path(path).name if path else ""

        # Show the analyzing state while waiting for the backend. Still images
        # are always a single frame, so display that explicitly.
        is_still_image = Path(path).suffix.lower() in _STILL_EXTENSIONS if path else False

        display_frames = max_frames
        if is_still_image:
            display_frames = 1

        self._upload_screen.start_progress(display_frames)

        self._worker = SearchWorker(file_path=path, max_frames=max_frames)
        self._worker.finished.connect(self._on_search_finished)
        self._worker.error.connect(self._on_search_error)
        self._worker.start()

        if display_frames is None and path:
            # Auto mode for videos/GIFs. Estimate the frame count from the video's
            # duration to improve the progress display. This runs in the background
            # and falls back to the unknown-count state if the estimate fails.
            self._probe_worker = ProbeWorker(path)
            self._probe_worker.finished.connect(self._on_probe_done)
            self._probe_worker.start()

    def _on_probe_done(self, duration: float) -> None:
        """
        Duration probe finished - update the progress label with the
        estimated frame count (auto mode only).
        """
        if duration:
            estimated = frame_extractor.count_frames_for_duration(duration)
            self._upload_screen.set_estimated_total(estimated)

    def _on_search_finished(self, verdict: dict) -> None:
        """
        Worker finished - populate result screen and switch to it.
        """
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

    def _on_show_history(self) -> None:
        """
        User clicked "History" (from upload or result screen) - fetch saved
        searches and switch to the history screen. Remember where we came
        from so the back button returns to the right place.
        """
        self._history_return_index = self.stack.currentIndex()

        self._history_worker = HistoryWorker()
        self._history_worker.finished.connect(self._on_history_loaded)
        self._history_worker.error.connect(self._on_history_load_failed)
        self._history_worker.start()

    def _on_history_loaded(self, entries: list) -> None:
        self._history_screen.set_entries(entries)
        self.show_screen(2)

    def _on_history_load_failed(self, message: str) -> None:
        QMessageBox.critical(self, "Couldn't load history", message)

    def _on_history_entry_selected(self, verdict: dict, filename: str) -> None:
        """
        User clicked a past search - reopen it on the result screen.
        """
        self._result_screen.show_result(verdict, filename)
        self.show_screen(1)

    def _on_history_back(self) -> None:
        """
        User clicked back on the history screen - return to whichever screen
        (upload or result) it was opened from.
        """
        self.show_screen(self._history_return_index)

    def show_screen(self, index: int) -> None:
        """
        Switch the visible screen by stack index.
        0 = upload screen, 1 = result screen.
        """
        self.stack.setCurrentIndex(index)
        