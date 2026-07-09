from pathlib import Path
from typing import Optional
import logging
import httpx
from PyQt6.QtCore import QThread, pyqtSignal

import config

logger = logging.getLogger(__name__)

# Base URL - FastAPI running locally. Read at call time, since main.py may
# have moved the API to a different port if 8000 was already taken.
def _api_base() -> str:
    return f"http://127.0.0.1:{config.API_PORT}"

_TIMEOUT  = 120.0  # seconds — video searches can be slow due to frame sleeping

# Every request carries the shared local token - the backend rejects
# anything without it (blocks drive-by browser requests - for secutit).
_HEADERS = {"X-AnimeRS-Token": config.API_TOKEN}


class ThumbnailWorker(QThread):
    """
    Background thread that extracts the first frame of a video as JPEG
    bytes for the upload preview.

    Runs off the main thread to avoid blocking the UI while reading the video.
    Raw bytes are returned instead of a QPixmap, since QPixmaps must be created on the main GUI thread.

    Signals
    -------
    finished(bytes)
        JPEG-encoded first frame.
    error(str)
        error message that huamn can read.
    """
    finished = pyqtSignal(bytes)
    error = pyqtSignal(str)

    def __init__(self, path: str, parent=None):
        super().__init__(parent)
        self._path = path

    def run(self) -> None:
        try:
            import imageio.v3 as iio
            from PIL import Image
            import io

            frame = iio.imread(self._path, index=0)
            img = Image.fromarray(frame)
            if img.mode in ("RGBA", "LA", "P"):
                img = img.convert("RGB")
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=70)
            self.finished.emit(buf.getvalue())
        except Exception as exc:
            self.error.emit(str(exc))


class ProbeWorker(QThread):
    """
    Background thread that probes a video's duration for the progress UI.

    Runs off the main thread since reading metadata (and its frame-counting
    fallback) can be slow on large files and would freeze the window.

    Signals
    -------
    finished(float)
        Duration in seconds (0.0 if it couldn't be determined).
    """
    finished = pyqtSignal(float)

    def __init__(self, path: str, parent=None):
        super().__init__(parent)
        self._path = path

    def run(self) -> None:
        try:
            import frame_extractor
            self.finished.emit(float(frame_extractor.probe_duration(self._path)))
        except Exception:
            self.finished.emit(0.0)


class QuotaWorker(QThread):
    """
    Background thread that checks the user's trace.moe quota.

    Only runs when requested, so it doesnt affect normal searches.

    Signals
    -------
    finished(dict)
        {quota, quota_used, remaining, low_quota}
    error(str)
        Human-readable error message on failure.
    """
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def run(self) -> None:
        try:
            with httpx.Client(timeout=8.0) as client:
                resp = client.get(f"{_api_base()}/quota", headers=_HEADERS)
                resp.raise_for_status()
                self.finished.emit(resp.json())
        except httpx.ConnectError:
            self.error.emit("Could not connect to the backend.")
        except httpx.TimeoutException:
            self.error.emit("Request timed out.")
        except httpx.HTTPStatusError as exc:
            self.error.emit(f"Server returned an error: {exc.response.status_code}")
        except Exception as exc:
            self.error.emit(f"Error: {exc}")


class HistoryWorker(QThread):
    """
    Background thread that fetches saved search history.

    Signals
    -------
    finished(list)
        Saved history entries, most recent first.
    error(str)
        Error message on failure.
    """
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def run(self) -> None:
        try:
            with httpx.Client(timeout=8.0) as client:
                resp = client.get(f"{_api_base()}/history", headers=_HEADERS)
                resp.raise_for_status()
                self.finished.emit(resp.json())
        except httpx.ConnectError:
            self.error.emit("Could not connect to the backend.")
        except httpx.TimeoutException:
            self.error.emit("Request timed out.")
        except httpx.HTTPStatusError as exc:
            self.error.emit(f"Server returned an error: {exc.response.status_code}")
        except Exception as exc:
            self.error.emit(f"Error: {exc}")


class SearchWorker(QThread):
    """
    Background thread for a single search request, talks with the FastAPI backend.

    Output
    -------
    finished(dict) - verdict dict from the API on success
    error(str) - human-readable error message on failure
    """
    finished = pyqtSignal(dict)
    error    = pyqtSignal(str)

    def __init__(self, file_path: str, max_frames: Optional[int] = None, parent=None):
        """
        Parameters
        ----------
        file_path : str
            path to the file to search.
            Pass an empty string "" to trigger the /search/paste endpoint.
        max_frames : int | None
            User-selected frame count. None = auto (dynamic logic in backend).
        """
        super().__init__(parent)
        self._file_path = file_path
        self._max_frames = max_frames

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

            # Cover + year + episode thumbnail + AniList banner + description
            # are already attached by the backend (services/anilist.py).
            self.finished.emit(verdict)

        except httpx.ConnectError:
            self.error.emit(
                "Could not connect to the backend.\n"
                "Start the app with: python main.py\n"
                "(it launches the local API automatically)"
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

        filename = Path(path).name

        data = {}
        if self._max_frames is not None:
            data["max_frames"] = str(self._max_frames)

        with httpx.Client(timeout=_TIMEOUT) as client:
            resp = client.post(
                f"{_api_base()}/search",
                files={"image": (filename, file_bytes)},
                data=data,
                headers=_HEADERS,
            )
            resp.raise_for_status()
            return resp.json()

    def _search_paste(self) -> dict:
        with httpx.Client(timeout=_TIMEOUT) as client:
            resp = client.post(f"{_api_base()}/search/paste", headers=_HEADERS)
            resp.raise_for_status()
            return resp.json()
        