from typing import Optional

import httpx
import base64

from PyQt6.QtCore import QThread, pyqtSignal

# Base URL - FastAPI running locally
_API_BASE = "http://localhost:8000"
_TIMEOUT  = 120.0  # seconds — video searches can be slow due to frame sleeping

_ANILIST_GRAPHQL_URL = "https://graphql.anilist.co"


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

            # Fetch the cover image while we still have the animelist_id,
            # so it's ready by the time the result screen shows.
            animelist_id = verdict.get("animelist_id")
            if animelist_id and animelist_id != "Unknown":
                cover_b64 = self._fetch_cover(animelist_id)
                if cover_b64:
                    verdict["cover_image_b64"] = cover_b64

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

    def _fetch_cover(self, animelist_id) -> Optional[str]:
        """
        Fetch the anime cover image from AniList's GraphQL API.

        Returns the image as a base64 string (for easy JSON-free transport
        between thread and UI), or None if anything fails.
        """
        try:
            query = """
            query ($id: Int) {
                Media(id: $id, type: ANIME) {
                    coverImage {
                        large
                    }
                }
            }
            """
            with httpx.Client(timeout=8.0) as client:
                resp = client.post(
                    _ANILIST_GRAPHQL_URL,
                    json={"query": query, "variables": {"id": int(animelist_id)}},
                )
                resp.raise_for_status()
                data = resp.json()

            cover_url = (
                data.get("data", {})
                .get("Media", {})
                .get("coverImage", {})
                .get("large")
            )
            if not cover_url:
                return None

            with httpx.Client(timeout=8.0) as client:
                img_resp = client.get(cover_url)
                img_resp.raise_for_status()
                return base64.b64encode(img_resp.content).decode("ascii")

        except Exception:
            # Cover is a nice-to-have, never let it break the search
            return None

    def _search_file(self, path: str) -> dict:
        with open(path, "rb") as f:
            file_bytes = f.read()

        filename = path.split("/")[-1].split("\\")[-1]

        data = {}
        if self._max_frames is not None:
            data["max_frames"] = str(self._max_frames)

        with httpx.Client(timeout=_TIMEOUT) as client:
            resp = client.post(
                f"{_API_BASE}/search",
                files={"image": (filename, file_bytes)},
                data=data,
            )
            resp.raise_for_status()
            return resp.json()

    def _search_paste(self) -> dict:
        with httpx.Client(timeout=_TIMEOUT) as client:
            resp = client.post(f"{_API_BASE}/search/paste")
            resp.raise_for_status()
            return resp.json()
        