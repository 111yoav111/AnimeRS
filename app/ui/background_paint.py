from __future__ import annotations
from pathlib import Path

from PyQt6.QtCore import QRect, Qt
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


def _collage_grid_dims(count: int) -> tuple[int, int]:
    """
    Pick (rows, cols) for a collage of `count` images, capped at a 3x3 grid.
    """
    if count <= 1:
        return (1, 1)
    if count == 2:
        return (1, 2)
    if count <= 4:
        return (2, 2)
    if count <= 6:
        return (2, 3)
    return (3, 3)


def _draw_cell_cover_fill(painter: QPainter, cell: QRect, pixmap: QPixmap) -> None:
    """
    Fill `cell` edge-to-edge with a center-crop of `pixmap` (cover mode).
    
    Used as the cell's backdrop so no dark letterbox bars ever show.
    """
    src_w, src_h = pixmap.width(), pixmap.height()
    if src_w <= 0 or src_h <= 0:
        return

    cell_ratio = cell.width() / cell.height()
    src_ratio = src_w / src_h
    if src_ratio > cell_ratio:
        crop_w = int(round(src_h * cell_ratio))
        src_rect = QRect((src_w - crop_w) // 2, 0, max(crop_w, 1), src_h)
    else:
        crop_h = int(round(src_w / cell_ratio))
        src_rect = QRect(0, (src_h - crop_h) // 2, src_w, max(crop_h, 1))
    painter.drawPixmap(cell, pixmap, src_rect)


def draw_collage_background(painter: QPainter, target: QRect, pixmaps: list[QPixmap]) -> None:
    """
    Draw a grid collage of `pixmaps` (most recent first) into `target`,
    filling every pixel of the area no matter how many images there are.

    Each cell is painted twice: a center-cropped, dimmed copy of the cover
    fills the whole cell as a backdrop, then the full cover is drawn
    centered on top of it. So the screen is always completely covered in
    art, while every cover also stays fully visible - no crop on the
    foreground copy, no dark letterbox bars behind it.

    No-op if pixmaps is empty; caller handles the plain-background fallback.
    """
    if not pixmaps or target.width() <= 0 or target.height() <= 0:
        return

    valid = [p for p in pixmaps if p is not None and not p.isNull()]
    if not valid:
        return

    rows, cols = _collage_grid_dims(len(valid))
    cells = valid[:rows * cols]

    # No gaps - cells butt against each other so the imagery is seamless.
    cell_w = target.width() / cols
    cell_h = target.height() / rows

    for i, pixmap in enumerate(cells):
        row, col = divmod(i, cols)
        x = int(target.x() + col * cell_w)
        y = int(target.y() + row * cell_h)
        # Right/bottom edges absorb the rounding remainder so the last
        # column/row still reaches the target edge exactly.
        w = int(target.x() + (col + 1) * cell_w) - x if col < cols - 1 else target.x() + target.width() - x
        h = int(target.y() + (row + 1) * cell_h) - y if row < rows - 1 else target.y() + target.height() - y
        cell = QRect(x, y, w, h)

        # Backdrop: the same art crop-filled to the whole cell, dimmed so
        # the full copy on top reads clearly against it.
        _draw_cell_cover_fill(painter, cell, pixmap)
        painter.fillRect(cell, QColor(13, 13, 15, 150))

        # Foreground: the complete cover, letterboxed inside the cell.
        scaled = pixmap.scaled(
            max(w, 1), max(h, 1),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        painter.drawPixmap(x + (w - scaled.width()) // 2, y + (h - scaled.height()) // 2, scaled)

    # Same dark gradient treatment as the single-cover background, so card
    # text stays readable over a busier image.
    gradient = QLinearGradient(0, 0, 0, target.height())
    gradient.setColorAt(0.0, QColor(13, 13, 15, 210))
    gradient.setColorAt(0.35, QColor(13, 13, 15, 120))
    gradient.setColorAt(0.65, QColor(13, 13, 15, 140))
    gradient.setColorAt(1.0, QColor(13, 13, 15, 220))
    painter.fillRect(target, gradient)
