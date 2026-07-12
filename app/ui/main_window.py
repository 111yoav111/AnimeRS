import time
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
        self._probe_worker = None
        self._history_return_index = 0  # screen to restore when leaving history
        self._batch_queue: list[str] = []  # paths still to search, current one popped off first
        self._batch_total = 0
        self._batch_results: list[dict] = []
        self._batch_frame_overrides: dict = {}
        # True while the result screen is showing a row opened from the batch
        # results screen - back then returns to the batch list, not upload.
        self._result_from_batch = False

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
        self._batch_screen = HistoryScreen(
            title="Batch results", empty_text="No results.",
            collage_background=True, show_filenames=True, batch_actions=True,
        )

        self.stack.addWidget(self._upload_screen)  # index 0
        self.stack.addWidget(self._result_screen)  # index 1
        self.stack.addWidget(self._history_screen)  # index 2
        self.stack.addWidget(self._batch_screen)  # index 3

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
        self._upload_screen.batch_search_requested.connect(self._on_batch_search_requested)
        self._upload_screen.show_history_requested.connect(self._on_show_history)
        self._result_screen.go_back.connect(self._on_go_back)
        self._result_screen.show_history_requested.connect(self._on_show_history)
        self._history_screen.go_back.connect(self._on_history_back)
        self._history_screen.entry_selected.connect(self._on_history_entry_selected)
        self._batch_screen.go_back.connect(self._on_go_back)
        self._batch_screen.entry_selected.connect(self._on_batch_entry_selected)

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

        # Wait out the previous worker's final thread teardown before
        # releasing it - see _run_next_batch_item for why.
        if self._worker is not None:
            self._worker.wait()
        self._worker = SearchWorker(file_path=path, max_frames=max_frames)
        self._worker.finished.connect(self._on_search_finished)
        self._worker.error.connect(self._on_search_error)
        self._worker.start()

        if display_frames is None and path:
            # Auto mode for videos/GIFs. Estimate the frame count from the video's
            # duration to improve the progress display. This runs in the background
            # and falls back to the unknown-count state if the estimate fails.
            if self._probe_worker is not None:
                self._probe_worker.wait()
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
        Worker finished - switch to the result screen, then add stuff to it.

        Switching first matters: the result screen's embedded preview clip
        sizes itself off the banner's real laid-out width, which the
        QStackedWidget only assigns once a page becomes current. 
        """
        self._result_from_batch = False
        self.show_screen(1)
        self._result_screen.show_result(verdict, self._current_filename)

    def _on_search_error(self, message: str) -> None:
        """
        Worker hit an error - show a message box, reset upload screen.
        """
        self._upload_screen.reset()
        QMessageBox.critical(self, "Search failed", message)

    def _on_batch_search_requested(self, paths: list, frame_overrides: dict) -> None:
        """
        User dropped/browsed multiple files - search them one at a time
        and append the result to a list shown when the whole batch is done.

        frame_overrides maps path -> frame count for videos the user
        customized via the batch frame picker; anything missing uses Auto.
        """
        self._batch_queue = list(paths)
        self._batch_total = len(paths)
        self._batch_results = []
        self._batch_frame_overrides = frame_overrides or {}
        self._run_next_batch_item()

    def _run_next_batch_item(self) -> None:
        if not self._batch_queue:
            self._batch_screen.set_entries(self._batch_results)
            self.show_screen(3)
            return

        path = self._batch_queue.pop(0)
        self._current_filename = Path(path).name
        position = self._batch_total - len(self._batch_queue)  # 1-based index of the item now running

        is_still_image = Path(path).suffix.lower() in _STILL_EXTENSIONS
        max_frames = self._batch_frame_overrides.get(path)  # None unless the user customized this one
        display_frames = 1 if is_still_image else max_frames
        self._upload_screen.start_progress(display_frames, batch_position=(position, self._batch_total))

        # Wait for the previous worker to finish shutting down before replacing it.
        # Destroying a QThread that's still exiting can crash the app.
        if self._worker is not None:
            self._worker.wait()
        self._worker = SearchWorker(file_path=path, max_frames=max_frames)
        self._worker.finished.connect(self._on_batch_item_finished)
        self._worker.error.connect(self._on_batch_item_error)
        self._worker.start()

    def _on_batch_item_finished(self, verdict: dict) -> None:
        self._batch_results.append({
            "searched_at": time.time(),
            "filename": self._current_filename,
            "verdict": verdict,
        })
        self._run_next_batch_item()

    def _on_batch_item_error(self, message: str) -> None:
        """
        If one file search failed, mark it as an error row and keep going, scan the rest of the batch.
        """
        self._batch_results.append({
            "searched_at": time.time(),
            "filename": self._current_filename,
            "verdict": {"found": False, "error": message},
        })
        self._run_next_batch_item()

    def _on_go_back(self) -> None:
        """
        User clicked back / try again.

        If the result screen is showing a row that was opened from the batch
        results screen, back returns to the batch list; anywhere else (single
        search, or the batch screen's own back button) it resets and goes to
        the upload screen as always.
        """
        if self._result_from_batch and self.stack.currentIndex() == 1:
            self._result_from_batch = False
            self.show_screen(3)
            return
        self._result_from_batch = False
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
        Switch first - see _on_search_finished for why.
        """
        self._result_from_batch = False
        self.show_screen(1)
        self._result_screen.show_result(verdict, filename)

    def _on_batch_entry_selected(self, verdict: dict, filename: str) -> None:
        """
        User clicked a row on the batch results screen - same as a history
        row, except back from the result returns to the batch list.
        """
        self._result_from_batch = True
        self.show_screen(1)
        self._result_screen.show_result(verdict, filename)

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
        