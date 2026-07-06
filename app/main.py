import asyncio
import secrets
import tempfile
import threading
from typing import Optional

from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Form, Depends, Header, HTTPException
from fastapi.responses import JSONResponse

import consensus
import frame_extractor
import paste
import config
from services import anilist, quota

app = FastAPI(title="AnimeRS")


def _require_token(x_animers_token: str = Header(default="")) -> None:
    """
    Reject any request that doesn't carry the shared local token.

    A custom header can't be sent by a plain cross-origin browser request
    without a CORS preflight (which will fail here), so this blocks drive-by
    web pages from triggering searches / clipboard grabs. compare_digest
    keeps the comparison constant-time.
    """
    if not secrets.compare_digest(x_animers_token, config.API_TOKEN):
        raise HTTPException(status_code=401, detail="Missing or invalid X-AnimeRS-Token header.")

#  search counter - resets when the server restarts.
_search_count = 0
_search_lock = threading.Lock()


def _add_search_counter(result: dict) -> dict:
    """
    Increment the search counter and send a quota reminder every QUOTA_WARN_EVERY searches.

    Counts *frames*, not requests - each frame costs one trace.moe search, so
    one video request can burn up to 16 quota. 
    The reminder fires on threshold crossings since the count can jump by more than 1 per request.

    Also attaches a low-quota warning (from trace.moe /me) when the daily quota runs low.
    Best case cenrio - a quota check failure never fails a search.

    Blocking (network call) - run via asyncio.to_thread from the endpoints.
    """
    global _search_count
    frames_used = result.get("frames_total") or 1
    with _search_lock:
        before = _search_count
        _search_count += frames_used
        count = _search_count
    if count // config.QUOTA_WARN_EVERY > before // config.QUOTA_WARN_EVERY:
        result["quota_reminder"] = (
            f"You have used {count} trace.moe searches this session."
        )
    try:
        q = quota.get_quota()
        if q.get("low_quota"):
            result["quota_low_warning"] = (
                f"Only {q['remaining']} trace.moe searches left today."
            )
    except Exception:
        pass  # quota check is informational only
    return result


@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/quota", dependencies=[Depends(_require_token)])
async def get_quota():
    """
    Return current trace.moe quota status (from /me).
    """
    try:
        return await asyncio.to_thread(quota.get_quota)
    except RuntimeError as exc:
        return JSONResponse(status_code=502, content={"error": str(exc)})
    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": f"Unexpected error: {exc}"})

@app.post("/search", dependencies=[Depends(_require_token)])
async def search(
    image: UploadFile = File(...),
    max_frames: Optional[int] = Form(None),  # None = auto, 1-16 = user override
):
    file_bytes = await image.read()
    if not image.filename:
        return JSONResponse(status_code=400, content={"error": "File has no name, cannot determine type."})
    suffix = Path(image.filename).suffix
    if not suffix:
        return JSONResponse(status_code=400, content={"error": "Cannot determine file type from file name."})
    # Only formats the UI offers - anything else never reaches ffmpeg/imageio.
    if suffix.lower() not in config.ALLOWED_EXTENSIONS:
        return JSONResponse(status_code=400, content={"error": f"Unsupported file type: {suffix}"})
    # Cap upload size - the whole file is held in memory.
    if len(file_bytes) > config.MAX_UPLOAD_MB * 1024 * 1024:
        return JSONResponse(status_code=413, content={"error": f"File too large (max {config.MAX_UPLOAD_MB} MB)."})

    # clamp to valid range if user provided a value
    if max_frames is not None:
        max_frames = max(1, min(max_frames, config.MAX_FRAMES_LIMIT))

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(file_bytes)
            tmp_path = Path(tmp.name)
        def run():
            frames, duration_sec = frame_extractor.extract_frames(tmp_path, max_frames=max_frames)
            verdict = consensus.build_verdict(frames, duration_sec)
            return anilist.enrich(verdict)
        result = await asyncio.to_thread(run)

        return await asyncio.to_thread(_add_search_counter, result)
    
    except RuntimeError as exc:
        return JSONResponse(status_code=502, content={"error": str(exc)})
    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": f"Unexpected error: {exc}"})
    finally:
        if tmp_path:
            try:
                tmp_path.unlink()
            except Exception:
                pass

@app.post("/search/paste", dependencies=[Depends(_require_token)])
async def search_paste():
    """
    Grab the current clipboard image and run a search.

    Reads the *server machine's*(user) clipboard - token-protected so a drive-by
    web page or another host can't trigger a silent clipboard upload.
    """
    tmp_path = None
    try:
        tmp_path = paste.grab()
        def run():
            frames, duration_sec = frame_extractor.extract_frames(tmp_path)
            verdict = consensus.build_verdict(frames, duration_sec)
            return anilist.enrich(verdict)
        result = await asyncio.to_thread(run)
        return await asyncio.to_thread(_add_search_counter, result)
    except NotImplementedError as e:
        return JSONResponse(status_code=400, content={"error": str(e)})
    except RuntimeError as e:
        return JSONResponse(status_code=502, content={"error": str(e)})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"Error: {e}"})
    finally:
        if tmp_path:
            try:
                tmp_path.unlink()
            except Exception:
                pass


# Open the UI from here 
# Run python main.py to launch app (starts the local API automatically).
# Run uvicorn main:app to start the API server only - set ANIMERS_TOKEN in the
# environment for both processes in that case.
if __name__ == "__main__":
    import os
    import socket
    import sys
    from pathlib import Path

    import uvicorn
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtGui import QIcon
    from ui.main_window import MainWindow

    # Packaged (PyInstaller --windowed) builds have no console, so
    # sys.stdout/stderr are None - anything that touches them crashes
    # (uvicorn's log formatter calls sys.stdout.isatty()). Give them a
    # safe sink so logging/printing is a no-op instead of a crash.
    if getattr(sys, "frozen", False):
        if sys.stdout is None:
            sys.stdout = open(os.devnull, "w")
        if sys.stderr is None:
            sys.stderr = open(os.devnull, "w")

    # If the preferred port is taken (an old server still running, a second
    # app instance, or another program), fall back to a free one. The UI reads
    # config.API_PORT at request time, so both sides stay in sync.
    def _free_port(preferred: int) -> int:
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", preferred))
                return preferred
            except OSError:
                s.bind(("127.0.0.1", 0))  # 0 = let the OS pick any free port
                return s.getsockname()[1]

    config.API_PORT = _free_port(config.API_PORT)

    # Local API in a background thread - bound to 127.0.0.1 only, never the network.
    # UI and API share config.API_TOKEN since it's the same process.
    # (uvicorn skips signal-handler setup when not on the main thread.)
    # log_config=None: skip uvicorn's console logging setup - there is no
    # console in the packaged app, and its formatter breaks without one.
    _server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=config.API_PORT, log_config=None))
    threading.Thread(target=_server.run, daemon=True).start()

    qt_app = QApplication(sys.argv)
    qt_app.setStyle("Fusion")

    # App/taskbar icon - logo at ui/assets/app_icon.png. 
    # Skips if no icon found.
    icon_path = Path(__file__).parent / "ui" / "assets" / "app_icon.png"
    if icon_path.exists():
        icon = QIcon(str(icon_path))
        qt_app.setWindowIcon(icon)

    window = MainWindow()
    if icon_path.exists():
        window.setWindowIcon(icon)
    window.show()

    sys.exit(qt_app.exec())
