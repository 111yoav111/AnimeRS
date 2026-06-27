import sys
import os

# import bs
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer

from ui.main_window import MainWindow
from ui.upload_screen import UploadScreen
import ui.theme as theme


class TestMainWindow(MainWindow):
    """
    MainWindow subclass that intercepts file_selected and
    simulates a search with fake frame-by-frame progress.
    """
    def __init__(self):
        super().__init__()

        self.upload_screen = UploadScreen()
        self.stack.addWidget(self.upload_screen)

        self.upload_screen.file_selected.connect(self._fake_search)

        self._fake_frame_index = 0
        self._fake_total = 0
        self._timer = QTimer()
        self._timer.timeout.connect(self._fake_tick)

    def _fake_search(self, path: str) -> None:
        if path == "":
            print("[TEST] Ctrl+V paste triggered")
        else:
            print(f"[TEST] File selected: {path}")

        # Simulate a 5-frame video search
        self._fake_total = 5
        self._fake_frame_index = 0
        self.upload_screen.start_progress(self._fake_total)

        # Mark first dot active immediately
        if self._fake_total > 0:
            self.upload_screen._frame_dots[0].setStyleSheet(
                theme.frame_dot_style("active")
            )

        self._timer.start(800)

    def _fake_tick(self) -> None:
        self.upload_screen.update_progress(self._fake_frame_index)
        self._fake_frame_index += 1

        if self._fake_frame_index >= self._fake_total:
            self._timer.stop()
            print("[TEST] Search complete — result screen would show here")


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    window = TestMainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()