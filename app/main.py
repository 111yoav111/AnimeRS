import asyncio
import tempfile

from pathlib import Path

from fastapi import FastAPI, UploadFile, File
from fastapi.responses import JSONResponse

import consensus
import frame_extractor
import paste

app = FastAPI(title="AnimeRS")

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/search")
async def search(image: UploadFile = File(...)):
    file_bytes = await image.read()
    if not image.filename:
        return JSONResponse(status_code=400, content={"error": "File has no name, cannot determine type."})
    suffix = Path(image.filename).suffix
    if not suffix:
        return JSONResponse(status_code=400, content={"error": "Cannot determine file type from file name."})
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(file_bytes)
            tmp_path = Path(tmp.name)
        def run():
            frames, duration_sec = frame_extractor.extract_frames(tmp_path)
            return consensus.build_verdict(frames, duration_sec)
        result = await asyncio.to_thread(run)

        return result
    
    except RuntimeError as exc:
        return JSONResponse(status_code=502, content={"error": str(exc)})
    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": f"Unexpected error: {exc}"})
    finally:
        try:
            tmp_path.unlink()
        except Exception:
            pass

@app.post("/search/paste")
async def search_paste():
    """
    Grab the current clipboard image and run a search.
    """
    try:
        tmp_path = paste.grab()
        def run():
            frames, duration_sec = frame_extractor.extract_frames(tmp_path)
            return consensus.build_verdict(frames, duration_sec)
        result = await asyncio.to_thread(run)
        return result
    except NotImplementedError as e:
        return JSONResponse(status_code=400, content={"error": str(e)})
    except RuntimeError as e:
        return JSONResponse(status_code=502, content={"error": str(e)})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"Error: {e}"})
    finally:
        try:
            tmp_path.unlink()
        except Exception:
            pass
