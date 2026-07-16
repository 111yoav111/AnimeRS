from __future__ import annotations
import io
import os
import platform
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageGrab

_OS = platform.system()

# linux clipboard mime type, try these in order
_LINUX_IMAGE_TYPES = (
    "image/png", "image/webp", "image/jpeg", "image/jpg",
    "image/bmp", "image/tiff", "image/gif",
)

_LINUX_CMD_TIMEOUT = 10  # clipboard tools can hang if app fell


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
    img = ImageGrab.grabclipboard()
    if img is None:
        raise RuntimeError("Couldnt copy the image from clipboard")

    return _to_png_bytes(img)


def _run_clipboard_tool(cmd: list[str]) -> bytes:
    """
    Run a clipboard command and return its raw stdout bytes.

    Wraps timeouts/missing-tool errors in readable messages.
    """
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=_LINUX_CMD_TIMEOUT)
    except subprocess.TimeoutExpired:
        raise RuntimeError(
            f"Clipboard read timed out ({cmd[0]}). The app that owns the "
            "clipboard may be frozen - try copying the image again."
        )
    if proc.returncode != 0:
        stderr = (proc.stderr or b"").decode(errors="replace").strip()
        raise RuntimeError(f"{cmd[0]} failed: {stderr or 'no image in the clipboard?'}")
    return proc.stdout


def _grab_linux_bytes() -> tuple[bytes, str]:
    """
    Grab the clipboard image on Linux, returning (raw_bytes, mime_type).

    Wayland sessions use wl-paste (wl-clipboard package), X11 uses xclip.
    Pure stdlib on purpose - PIL conversion happens in the caller.
    """
    wayland = bool(os.environ.get("WAYLAND_DISPLAY"))
    x11 = bool(os.environ.get("DISPLAY"))

    if wayland and shutil.which("wl-paste"):
        list_cmd = ["wl-paste", "--list-types"]
        fetch_cmd = lambda mime: ["wl-paste", "--type", mime]
    elif x11 and shutil.which("xclip"):
        list_cmd = ["xclip", "-selection", "clipboard", "-t", "TARGETS", "-o"]
        fetch_cmd = lambda mime: ["xclip", "-selection", "clipboard", "-t", mime, "-o"]
    elif wayland or x11:
        tool = "wl-clipboard (for wl-paste)" if wayland else "xclip"
        raise RuntimeError(
            f"Clipboard paste needs {tool} installed"
        )
    else:
        raise RuntimeError(
            "No graphical session detected (neither WAYLAND_DISPLAY nor DISPLAY is set)"
        )

    available = _run_clipboard_tool(list_cmd).decode(errors="replace").split()
    mime = next((t for t in _LINUX_IMAGE_TYPES if t in available), None)
    if mime is None:
        raise RuntimeError(
            "No image in the clipboard. Copy an image first (not a file or text)."
        )

    data = _run_clipboard_tool(fetch_cmd(mime))
    if not data:
        raise RuntimeError("The clipboard returned an empty image.")
    return data, mime


def _grab_linux() -> bytes:
    """
    Grab on Linux and normalize to PNG bytes, matching the win/mac path.
    """
    data, _mime = _grab_linux_bytes()
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except Exception as e:
        raise RuntimeError(f"Clipboard content could not be read as an image: {e}") from e
    return _to_png_bytes(img)


def grab() -> Path:
    """
    Grab the current clipboard image (the ctrl+v one), return a path to temp PNG file.

    file must be deleted at the end by caller! (try/finally).
    """
    if _OS in ("Windows", "Darwin"):
        img_bytes = _grab_win_mac()
    else:
        img_bytes = _grab_linux()
    _verify(img_bytes)

    tmp = tempfile.NamedTemporaryFile(
        suffix=".png", prefix="AnimeRS_img_", delete=False
    )
    try:
        tmp.write(img_bytes)
    finally:
        tmp.close()  # always close tmp

    return Path(tmp.name)
