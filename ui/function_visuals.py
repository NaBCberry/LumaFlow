from dataclasses import dataclass

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QBrush, QColor, QIcon, QPainter, QPen, QPixmap


@dataclass(frozen=True)
class FunctionTextureSpec:
    pattern: str
    tile_size: int


FUNCTION_TEXTURE_SPECS = {
    1: FunctionTextureSpec("diagonal", 32),
    2: FunctionTextureSpec("crosshatch", 16),
    3: FunctionTextureSpec("dots", 8),
}


def get_function_texture_spec(function):
    """Return the shared texture specification, or None for solid/invalid modes."""
    try:
        mode = int(function)
    except (TypeError, ValueError):
        return None
    return FUNCTION_TEXTURE_SPECS.get(mode)


def make_function_brush(function, color, texture_scale=1.0):
    """Create a screen-space texture brush for a Function mode."""
    spec = get_function_texture_spec(function)
    if spec is None:
        return QBrush(Qt.NoBrush)

    scale = max(0.25, float(texture_scale))
    tile_size = max(4, int(round(spec.tile_size * scale)))
    pattern_color = QColor(color)
    pattern_color.setAlpha(180)

    pixmap = QPixmap(tile_size, tile_size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    try:
        painter.setRenderHint(QPainter.Antialiasing)
        pen_width = max(1.0, 1.5 * scale)
        painter.setPen(QPen(pattern_color, pen_width))

        edge = float(tile_size - 1)
        if spec.pattern == "diagonal":
            painter.drawLine(QPointF(0.0, edge), QPointF(edge, 0.0))
        elif spec.pattern == "crosshatch":
            painter.drawLine(QPointF(0.0, edge), QPointF(edge, 0.0))
            painter.drawLine(QPointF(0.0, 0.0), QPointF(edge, edge))
        elif spec.pattern == "dots":
            radius = max(1.0, tile_size * 0.16)
            center = QPointF(tile_size / 2.0, tile_size / 2.0)
            painter.setBrush(pattern_color)
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(center, radius, radius)
    finally:
        painter.end()
    return QBrush(pixmap)


def make_function_icon(function, foreground, background, size=18):
    """Create a menu swatch from the same texture generator as the timeline."""
    pixmap = QPixmap(size, size)
    pixmap.fill(QColor(background))

    background_color = QColor(background)
    foreground_color = QColor(foreground)
    if background_color.lightness() < 100 and foreground_color.lightness() < 100:
        foreground_color = QColor(220, 220, 220)

    painter = QPainter(pixmap)
    try:
        icon_scale = max(0.5, min(1.0, size / 32.0))
        brush = make_function_brush(function, foreground_color, icon_scale)
        if brush.style() != Qt.NoBrush:
            painter.fillRect(pixmap.rect(), brush)
        painter.setPen(QPen(foreground_color, 1))
        painter.drawRect(pixmap.rect().adjusted(0, 0, -1, -1))
    finally:
        painter.end()
    return QIcon(pixmap)
