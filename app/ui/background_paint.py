from __future__ import annotations
from pathlib import Path

from PyQt6.QtCore import QRect
from PyQt6.QtGui import QColor, QLinearGradient, QPainter, QPixmap


def load_pixmap(path: Path | None) -> QPixmap | None:
    """
    Load a pixmap from a local file path.

    Returns None if the path is missing or the file isn't a valid image,
    so callers can fall back to a plain background instead of crashing.
    """
    if path is None or not path.exists():
        return None
    pixmap = QPixmap(str(path))
    if pixmap.isNull():
        return None
    return pixmap


def draw_cover_background(painter: QPainter, target: QRect, pixmap: QPixmap) -> None:
    """
    Draw `pixmap` into `target`, scaled + cropped to *cover* the whole area.
    Add a dark gradient over it so text stays readable.

    Shared by UploadScreen and ResultScreen - same behavior.
    """
    if pixmap is None or pixmap.isNull():
        return

    src_w, src_h = pixmap.width(), pixmap.height()
    if src_w <= 0 or src_h <= 0 or target.width() <= 0 or target.height() <= 0:
        return

    target_ratio = target.width() / target.height()
    src_ratio = src_w / src_h

    if src_ratio > target_ratio:
        # Source too wide: crop left/right.
        crop_w = int(round(src_h * target_ratio))
        crop_x = (src_w - crop_w) // 2
        src_rect = QRect(crop_x, 0, crop_w, src_h)
    else:
        # Source too tall: crop top/bottom.
        crop_h = int(round(src_w / target_ratio))
        crop_y = (src_h - crop_h) // 2
        src_rect = QRect(0, crop_y, src_w, crop_h)

    # Scale that crop to exactly fill the widget. Passing the target rect
    painter.drawPixmap(target, pixmap, src_rect)

    # Dark gradient overlay for text contrast - identical on both screens.
    gradient = QLinearGradient(0, 0, 0, target.height())
    gradient.setColorAt(0.0, QColor(13, 13, 15, 210))
    gradient.setColorAt(0.35, QColor(13, 13, 15, 120))
    gradient.setColorAt(0.65, QColor(13, 13, 15, 140))
    gradient.setColorAt(1.0, QColor(13, 13, 15, 220))
    painter.fillRect(target, gradient)
