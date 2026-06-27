import httpx

from PyQt6.QtCore import QThread, pyqtSignal

# Base URL - FastAPI running locally
_API_BASE = "http://localhost:8000"
_TIMEOUT  = 120.0  # seconds — video searches can be slow due to frame sleeping


class SearchWorker(QThread):
    """
    Background thread for a single search requestm, talks with the FastAPI backend.

    Output
    -------
    finished(dict) - verdict dict from the API on success
    error(str) - human-readable error message on failure
    """
    finished = pyqtSignal(dict)
    error    = pyqtSignal(str)

    def __init__(self, file_path: str, parent=None):
        """
        Parameters
        ----------
        file_path : str
            path to the file to search.
            Pass an empty string "" to trigger the /search/paste endpoint.
        """
        super().__init__(parent)
        self._file_path = file_path

    def run(self) -> None:
        """
        Called automatically by QThread.start().
        Runs in the background thread - never call directly.
        """
        try:
            if self._file_path == "":
                verdict = self._search_paste()
            else:
                verdict = self._search_file(self._file_path)

            self.finished.emit(verdict)

        except httpx.ConnectError:
            self.error.emit(
                "Could not connect to the backend.\n"
                "Make sure the server is running: WILL BE CHANGED LATER\n"
                "uvicorn main:app --reload"
            )
        except httpx.TimeoutException:
            self.error.emit("Request timed out. file too big or backend crashed")
        except httpx.HTTPStatusError as exc:
            self.error.emit(f"Server returned an error: {exc.response.status_code}")
        except Exception as exc:
            self.error.emit(f"Error: {exc}")

    def _search_file(self, path: str) -> dict:
        with open(path, "rb") as f:
            file_bytes = f.read()

        filename = path.split("/")[-1].split("\\")[-1]

        with httpx.Client(timeout=_TIMEOUT) as client:
            resp = client.post(
                f"{_API_BASE}/search",
                files={"image": (filename, file_bytes)},
            )
            resp.raise_for_status()
            return resp.json()

    def _search_paste(self) -> dict:
        with httpx.Client(timeout=_TIMEOUT) as client:
            resp = client.post(f"{_API_BASE}/search/paste")
            resp.raise_for_status()
            return resp.json()
        