from __future__ import annotations

import io
import logging
from pathlib import Path

import imageio.v3 as iio
from PIL import Image

logger = logging.getLogger(__name__)

_JPEG_QUALITY = 60

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


def probe_duration(path: str | Path) -> float:
    """
    Return a video's duration in seconds by reading its metadata without
    decoding any frames.

    Used by the UI to estimate the number of frames before extraction,
    allowing it to display progress even when no frame count was chosen.

    This logic is intentionally separate from the extraction code to avoid
    affecting the actual extraction path. 
    
    Returns 0.0 if the duration cannot be determined.
    """
    path = Path(path)
    try:
        md = iio.immeta(str(path))
        fps = md.get("fps") or md.get("average_rate") or 25
        duration_sec = md.get("duration") or 0
        total_frames = int(duration_sec * fps) if duration_sec else None
    except Exception:
        fps = 25
        duration_sec = 0
        total_frames = None

    # fallback - count frames manually if still no duration
    if not duration_sec or not total_frames:
        try:
            total_frames = iio.improps(str(path)).n_images or 0
            duration_sec = total_frames / fps if total_frames and fps else 0
        except Exception:
            duration_sec = 0

    # final guard against inf/NaN
    if not duration_sec or duration_sec != duration_sec or duration_sec == float('inf'):
        duration_sec = 0

    return duration_sec


def _count_frames_for_duration(duration_sec : float) -> int:
    """
    Decide how many frames to extract based on video duration.

    The longer the video -> more frames, capped at 16 frames to avoid diminishing returns.
    """
    if duration_sec < 30:
        return 3
    elif duration_sec < 120:  # 30 sec – 2 min
        return 5
    elif duration_sec < 600:  # 2 – 10 min
        return 8
    elif duration_sec < 1800: # 10 – 30 min
        return 12
    else:  # 30 min+
        return 16


def _is_image(path : Path) -> list[bytes]:
    """
    Read an image and return it as a 1-element list.
    """
    img = Image.open(path)
    img.load()
    logger.info("Image - 1 frame (%s)", path.name)

    return [_encode(img)]


def _from_video(path: Path, max_frames: int | None = None) -> tuple[list[bytes], float]:
    """
    Handle videos - extract evenly-spread frames from a GIF or video.
    First and last captured frames mark the timestamp range.

    max_frames: user-selected frame count. None = use dynamic logic.
    """
    try:
        md = iio.immeta(str(path))
        fps = md.get("fps") or md.get("average_rate") or 25
        duration_sec = md.get("duration") or 0
        total_frames = int(duration_sec * fps) if duration_sec else None
    except Exception:
        fps = 25
        duration_sec = 0
        total_frames = None

    # fallback - count frames manually if still no duration
    if not duration_sec or not total_frames:
        try:
            total_frames = iio.improps(str(path)).n_images or 0
            duration_sec = total_frames / fps if total_frames and fps else 0
        except Exception:
            total_frames = 0
            duration_sec = 0

    # final guard against inf/NaN
    if not duration_sec or duration_sec != duration_sec or duration_sec == float('inf'):
        duration_sec = 0
        total_frames = 0

    # user override takes priority, otherwise dynamic logic
    if max_frames is not None:
        frames_to_give = max_frames
    else:
        frames_to_give = _count_frames_for_duration(duration_sec)

    # Always guarantee room for both a true first frame AND a true near-last
    # frame - if only 1 frame was going to be extracted (a short clip's
    # default, or the user manually picking 1), bump to 2 so the near-end
    # swap below doesn't end up overwriting the only frame we have.
    if total_frames and total_frames > 1:
        frames_to_give = max(frames_to_give, 2)

    # Calc skip - dynamic, based on vid duration
    if total_frames and total_frames > frames_to_give:
        skip = max(1, total_frames // frames_to_give)
    else:
        skip = 1
    logger.info(
        "Video duration: (%.1fs) | total_frames: (%d) | extracting (%d) frames | skip: (%d) | (%s)",
        duration_sec, total_frames, frames_to_give, skip, path.name
    )
    frames: list[bytes] = []
    captured_indices: list[int] = []
    for i, raw in enumerate(iio.imiter(str(path))):
        if i % skip == 0:
            try:
                frames.append(_encode(Image.fromarray(raw)))
                captured_indices.append(i)
                logger.debug("Added frame %d", i)
            except Exception as exc:
                logger.debug("Skipped frame %d: %s", i, exc)

            if len(frames) >= frames_to_give:
                break

    # The even-spacing loop above stops once it's collected enough frames,
    # so the last one captured isn't necessarily anywhere near the actual
    # end of the clip (e.g. 5 frames wanted, skip=60 -> last capture is
    # frame 240 even if the video runs to frame 299). Grab a frame close to
    # the true end and use it in place of that last sample instead, so the
    # matched timestamp range can be grounded in a real trace.moe result at
    # both ends, not an assumed duration.
    if frames and total_frames and total_frames > 1:
        last_index = captured_indices[-1] if captured_indices else 0
        near_end_index = max(0, total_frames - 2)  # -2: the very last frame is sometimes truncated/undecodable
        if near_end_index - last_index > max(1, skip // 2):
            try:
                end_raw = iio.imread(str(path), index=near_end_index)
                frames[-1] = _encode(Image.fromarray(end_raw))
                logger.debug("Replaced last frame with near-end frame %d (was %d)", near_end_index, last_index)
            except Exception as exc:
                logger.debug("Could not grab near-end frame %d, keeping original: %s", near_end_index, exc)

    return frames, duration_sec


def extract_frames(path: str | Path, max_frames: int | None = None) -> tuple[list[bytes], float]:
    """
    Extract JPEG-encoded frames from any image, GIF, or video.

    Parameters
    ----------
    max_frames : int | None
        User-selected frame count (1-16). None = auto (dynamic based on duration).
        Ignored for images - always 1 frame.

    Returns
    -------
    tuple[list[bytes], float]
        - list[bytes] : frames, always at least 1 item
        - float       : duration in seconds (0.0 for still images)
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")
    if path.suffix.lower() in _STILL_EXTENSIONS:
        return _is_image(path), 0.0  # image, no duration

    frames, duration_sec = _from_video(path, max_frames=max_frames)
    if not frames:
        logger.warning("No frames captured, retrying as image (%s)", path.name)
        return _is_image(path), 0.0

    return frames, duration_sec
