import asyncio
import tempfile
import threading

from pathlib import Path

from fastapi import FastAPI, UploadFile, File
from fastapi.responses import JSONResponse

import consensus
import frame_extractor
import paste
import config
from services import quota

app = FastAPI(title="AnimeRS")

#  search counter - resets when the server restarts.
_search_count = 0
_search_lock = threading.Lock()


def _add_search_counter(result: dict) -> dict:
    """
    Increment the search counter and send a quota reminder every QUOTA_WARN_EVERY searches.
    """
    global _search_count
    with _search_lock:
        _search_count += 1
        count = _search_count
    if count % config.QUOTA_WARN_EVERY == 0:
        result["quota_reminder"] = (
            f"You've made {count} searches this session. "
        )
    return result


@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/quota")
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

@app.post("/search")
async def search(image: UploadFile = File(...)):
    file_bytes = await image.read()
    if not image.filename:
        return JSONResponse(status_code=400, content={"error": "File has no name, cannot determine type."})
    suffix = Path(image.filename).suffix
    if not suffix:
        return JSONResponse(status_code=400, content={"error": "Cannot determine file type from file name."})
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(file_bytes)
            tmp_path = Path(tmp.name)
        def run():
            frames, duration_sec = frame_extractor.extract_frames(tmp_path)
            return consensus.build_verdict(frames, duration_sec)
        result = await asyncio.to_thread(run)

        return _add_search_counter(result)
    
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

@app.post("/search/paste")
async def search_paste():
    """
    Grab the current clipboard image and run a search.
    """
    tmp_path = None
    try:
        tmp_path = paste.grab()
        def run():
            frames, duration_sec = frame_extractor.extract_frames(tmp_path)
            return consensus.build_verdict(frames, duration_sec)
        result = await asyncio.to_thread(run)
        return _add_search_counter(result)
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
