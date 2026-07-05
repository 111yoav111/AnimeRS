from typing import Optional

import logging

import httpx
import base64

from PyQt6.QtCore import QThread, pyqtSignal

logger = logging.getLogger(__name__)

# Base URL - FastAPI running locally
_API_BASE = "http://localhost:8000"
_TIMEOUT  = 120.0  # seconds — video searches can be slow due to frame sleeping

_ANILIST_GRAPHQL_URL = "https://graphql.anilist.co"


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
                resp = client.get(f"{_API_BASE}/quota")
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

            # Fetch cover + year + episode thumbnail + AniList banner.
            # so everything is ready when the result screen shows
            animelist_id = verdict.get("animelist_id")
            if animelist_id and animelist_id != "Unknown":
                cover_b64, year, episode_thumb_b64, banner_b64, description, episode_title = self._fetch_images(
                    animelist_id, verdict.get("episode")
                )
                if cover_b64:
                    verdict["cover_image_b64"] = cover_b64
                if year:
                    verdict["year"] = year
                if episode_thumb_b64:
                    verdict["episode_thumb_b64"] = episode_thumb_b64
                if banner_b64:
                    verdict["banner_image_b64"] = banner_b64
                if description:
                    verdict["description"] = description
                if episode_title:
                    verdict["episode_title"] = episode_title

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

    def _fetch_images(
        self, animelist_id, episode: Optional[int] = None
    ) -> tuple[Optional[str], Optional[int], Optional[str], Optional[str], Optional[str], Optional[str]]:
        """
        Fetch the anime cover image, release year, episode thumbnail, and
        AniList banner image.

        Returns (cover_b64, year, episode_thumb_b64, banner_b64). Any value may
        be None if unavailable or an error happened.

        The episode thumbnail is taken from AniList's `streamingEpisodes` list,
        which usually matches the requested episode but is not guaranteed.
        """
        cover_b64: Optional[str] = None
        year: Optional[int] = None
        episode_thumb_b64: Optional[str] = None
        banner_b64: Optional[str] = None
        description: Optional[str] = None
        episode_title: Optional[str] = None

        query = """
        query ($id: Int) {
            Media(id: $id, type: ANIME) {
                coverImage {
                    large
                }
                bannerImage
                seasonYear
                description(asHtml: false)
                streamingEpisodes {
                    title
                    thumbnail
                }
            }
        }
        """
        try:
            with httpx.Client(timeout=8.0) as client:
                resp = client.post(
                    _ANILIST_GRAPHQL_URL,
                    json={"query": query, "variables": {"id": int(animelist_id)}},
                )
                resp.raise_for_status()
                data = resp.json()
            media = data.get("data", {}).get("Media", {}) or {}
        except Exception as exc:
            logger.warning("AniList metadata lookup failed for id=%s: %s", animelist_id, exc)
            return None, None, None, None, None, None

        cover_url = (media.get("coverImage") or {}).get("large")
        banner_url = media.get("bannerImage")
        year = media.get("seasonYear")
        description = media.get("description") or None

        episode_thumb_url = None
        streaming_episodes = media.get("streamingEpisodes") or []
        if episode and 1 <= episode <= len(streaming_episodes):
            episode_data = streaming_episodes[episode - 1]
            episode_thumb_url = episode_data.get("thumbnail")
            episode_title = episode_data.get("title") or None

        if cover_url:
            try:
                with httpx.Client(timeout=8.0) as client:
                    img_resp = client.get(cover_url)
                    img_resp.raise_for_status()
                    cover_b64 = base64.b64encode(img_resp.content).decode("ascii")
            except Exception as exc:
                logger.warning("Cover image download failed: %s", exc)

        if episode_thumb_url:
            try:
                with httpx.Client(timeout=8.0) as client:
                    img_resp = client.get(episode_thumb_url)
                    img_resp.raise_for_status()
                    episode_thumb_b64 = base64.b64encode(img_resp.content).decode("ascii")
            except Exception as exc:
                logger.warning("Episode thumbnail download failed: %s", exc)

        if banner_url:
            try:
                with httpx.Client(timeout=8.0) as client:
                    img_resp = client.get(banner_url)
                    img_resp.raise_for_status()
                    banner_b64 = base64.b64encode(img_resp.content).decode("ascii")
            except Exception as exc:
                logger.warning("Banner image download failed: %s", exc)

        return cover_b64, year, episode_thumb_b64, banner_b64, description, episode_title

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
        