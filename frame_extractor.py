from __future__ import annotations

import io
import logging
from pathlib import Path

import imageio.v3 as iio
from PIL import Image

logger = logging.getLogger(__name__)

_JPEG_QUALITY = 85 

_STILL_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".tif",
}


def _encode(img : Image.Image) -> bytes:
    """
    Convert PIL image to JPEG bytes.
    """
    buffer = io.BytesIO()
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGB")

    img.save(buffer, format="JPEG", quality=_JPEG_QUALITY, optimize=True)

    return buffer.getvalue()


def _count_frames_for_duration(duration_sec : float) -> int:
    """
    Decide how many frames to extract based on video duration.

    The longer the video -> more frames, capped at 40 frames to avoid diminishing returns.
    """
    if duration_sec < 30:
        return 5
    elif duration_sec < 120:  # 30 sec – 2 min
        return 10
    elif duration_sec < 600:  # 2 – 10 min
        return 20
    elif duration_sec < 1800: # 10 – 30 min
        return 30
    else:  # 30 min+
        return 40


def _is_image(path : Path) -> list[bytes]:
    """
    Read an image and return it as a 1-element list.
    """
    img = Image.open(path)
    img.load()
    logger.info("Image - 1 frame (%s)", path.name)

    return [_encode(img)]


def _from_video(path : Path) -> list[bytes]:
    """
    Handle videos - extract evenly-spread frames from a GIF or video.

    First and last captured frames mark the timestamp range.
    """
    metadata = iio.improps(str(path))
    total_frames = metadata.n_images if metadata.n_images and metadata.n_images > 0 else None

    # Try get the FPS for duration calc
    try:
        md = iio.immeta(str(path))
        fps = md.get("fps") or md.get("average_rate") or 25
    except Exception:
        fps = 24

    if total_frames:
        duration_sec = total_frames / fps
    else:  # cant read metadata - fall back
        duration_sec = 0
        total_frames = 0
    
    frames_to_give = _count_frames_for_duration(duration_sec)

    # Calc skip - dynamic, based on vid duration
    if total_frames and total_frames > frames_to_give:
        skip = max(1, total_frames // frames_to_give)
    else: 
        skip = 1

    logger.info(
        "Video duration: (%.1fs) | total_frames: (%d) | extracting (%d) frames | skip: (%d) | (%s)",
        duration_sec, total_frames, frames_to_give, skip, path.name
    )

    frames : list[bytes] = [] 

    for i, raw in enumerate(iio.imiter(str(path))):
        if i % skip == 0:
            try:
                frames.append(_encode(Image.fromarray(raw)))
                logger.debug("Added frame %d", i)
            except Exception as exc:
                # couldnt capture frame - skip it
                logger.debug("Skipped frame %d: %s", i, exc)
 
            if len(frames) >= frames_to_give:
                break

    return frames


def extract_frames(path : str | Path) -> list[bytes]:
    """
    Extract JPEG-encoded frames from any image, GIF, or video.
 
    Returns
    -------
    list[bytes]
        Always at least 1 item.
        - Still image  : 1 frame
        - GIF / video  : 5–40 frames evenly spread across full duration
                         frames[0]  = start of timestamp range
                         frames[-1] = end of timestamp range
 
    Raises FileNotFoundError if the path does not exist.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")

    if path.suffix.lower() in _STILL_EXTENSIONS:
        return _is_image(path)
    
    frames = _from_video(path)

    if not frames:
        # Might be a single-frame GIF or metadata read failed, treat it as img
        logger.warning("No frames captured, retrying as image (%s)", path.name)
        return _is_image(path)
    
    return frames
