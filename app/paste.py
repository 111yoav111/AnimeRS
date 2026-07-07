from __future__ import annotations
import io
import platform
import tempfile
from pathlib import Path

from PIL import Image, ImageGrab

_OS = platform.system() 


# --------helpers-----------
def _to_png_bytes(img : Image.Image) -> bytes:
    """
    Convert a PIL image to raw png bytes.
    """
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")

    return buffer.getvalue()

def _verify(img_bytes : bytes) -> None:
    """
    Verify that img bytes are real and can be parsed.
    """
    try:
        img = Image.open(io.BytesIO(img_bytes))
        img.verify()
    except Exception as e:
        raise RuntimeError(
            f"Doesnt look like a valid image: {e}"
        ) from e
    

# --------graber---------
def _grab_win_mac() -> bytes:
    """
    Grab clipboard image on Windows or macOS.
    """
    img = ImageGrab.grabclipboard()  # cant be used with Linux (for now)
    if img is None:
        raise RuntimeError("Couldnt copy the image from clipboard")
    
    return _to_png_bytes(img)



def grab() -> Path:
    """
    Grab the current clipboard image (the ctrl+v one), return a path to temp PNG file.

    file must be deleted at the end by caller! (try/finally).
    """
    if _OS not in ("Windows", "Darwin"): 
        raise NotImplementedError(
            "Clipboard option is not supported on Linux yet \n" 
            "Please upload your file directly"
        )
    
    img_bytes = _grab_win_mac()
    _verify(img_bytes)

    tmp = tempfile.NamedTemporaryFile(
        suffix=".png", prefix="AnimeRS_img_", delete=False
    )
    try:
        tmp.write(img_bytes)
    finally:
        tmp.close()  # always close tmp

    return Path(tmp.name)
