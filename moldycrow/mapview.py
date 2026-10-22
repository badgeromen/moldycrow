"""Top-down rendering of a Dark Forces level: sectors shaded by height, walls, doors, secrets, spawn."""
from __future__ import annotations

from PyQt6.QtCore import Qt, QPointF, QRectF
from PyQt6.QtGui import (QColor, QImage, QPainter, QPainterPath, QPen, QBrush, QPolygonF,
                         QLinearGradient, QFont, QTransform)
from PyQt6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsItem

from .df import Level, ObjectInfo, Sector

# Palette: the in-game PDA automap — green vectors on black
BG = QColor("#000000")
WALL = QColor("#3cff3c")
STEP = QColor("#22b322")
PORTAL = QColor("#0f5a0f")
DOOR = QColor("#ffd23b")
SECRET_FILL = QColor(255, 52, 52, 40)
SECRET_EDGE = QColor("#ff3434")
SKY_TINT = QColor(20, 60, 20, 40)
PIT_TINT = QColor(0, 0, 0, 0)
FLOOR_FILL = QColor(10, 40, 14, 110)
PLAYER = QColor("#a8ffa8")
ENEMY = QColor(255, 60, 60, 190)


def sector_path(sec: Sector) -> QPainterPath:
    """Build a closed path from the sector's wall loops (odd-even fill handles holes)."""
    path = QPainterPath()
    path.setFillRule(Qt.FillRule.OddEvenFill)
    n = len(sec.verts)
    if n < 3 or not sec.walls:
        return path
    prev_right = None
    started = False
    for w in sec.walls:
        if w.left >= n or w.right >= n or w.left < 0 or w.right < 0:
            continue
        lx, lz = sec.verts[w.left]
        if prev_right != w.left or not started:
            if started:
                path.closeSubpath()
            path.moveTo(lx, -lz)
            started = True
        rx, rz = sec.verts[w.right]
        path.lineTo(rx, -rz)
        prev_right = w.right
    if started:
        path.closeSubpath()
    return path


def height_color(t: float, ambient: int) -> QColor:
    """t in [0,1]: 0 = lowest floor, 1 = highest. A faint green floor wash so rooms read as areas on the PDA."""
    t = max(0.0, min(1.0, t))
    a = max(0.4, min(1.0, 0.5 + ambient / 62.0))
    g = int((22 + 70 * t) * a)
    return QColor(int(g * 0.25), g, int(g * 0.35), 120)


class MapPainter:
    """Draws a Level into any QPainter in *map units* (caller sets the transform)."""

    def __init__(self, level: Level, objs: ObjectInfo | None = None):
        self.level = level
        self.objs = objs
        floors = [s.floor for s in level.sectors if s.verts]
        self.fmin = min(floors) if floors else 0.0
        self.fmax = max(floors) if floors else 1.0
        self.paths = [(s, sector_path(s)) for s in level.sectors]
        self.rect = QRectF()
        for _, p in self.paths:
            self.rect = self.rect.united(p.boundingRect())

    def _t(self, sec: Sector) -> float:
        span = self.fmax - self.fmin
        if span < 1e-6:
            return 0.5
        # Dark Forces Y grows downward, so higher ground has a more negative floor.
        return 1.0 - (sec.floor - self.fmin) / span

    def draw(self, p: QPainter, scale: float, show_enemies: bool = True):
        """scale = device pixels per map unit; used to keep line widths sensible."""
        px = 1.0 / max(scale, 1e-6)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        # Fills
        p.setPen(Qt.PenStyle.NoPen)
        for sec, path in self.paths:
            if path.isEmpty():
                continue
            p.setBrush(QBrush(height_color(self._t(sec), sec.ambient)))
            p.drawPath(path)
            if sec.is_sky:
                p.setBrush(QBrush(SKY_TINT)); p.drawPath(path)
            if sec.is_pit:
                p.setBrush(QBrush(PIT_TINT)); p.drawPath(path)
            if sec.is_secret:
                p.setBrush(QBrush(SECRET_FILL)); p.drawPath(path)
            if sec.is_door:
                p.setBrush(QBrush(QColor(242, 163, 58, 110))); p.drawPath(path)
        # Walls
        portal_pen = QPen(PORTAL, 0.6 * px)
        wall_pen = QPen(WALL, 1.4 * px)
        wall_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        door_pen = QPen(DOOR, 2.0 * px)
        secret_pen = QPen(SECRET_EDGE, 1.2 * px, Qt.PenStyle.DashLine)
        p.setBrush(Qt.BrushStyle.NoBrush)
        sec_by_idx = {s.index: s for s in self.level.sectors}
        for sec, _ in self.paths:
            n = len(sec.verts)
            for w in sec.walls:
                if w.left >= n or w.right >= n or w.left < 0 or w.right < 0:
                    continue
                a = sec.verts[w.left]; b = sec.verts[w.right]
                if w.adjoin < 0:
                    p.setPen(secret_pen if sec.is_secret else wall_pen)
                else:
                    other = sec_by_idx.get(w.adjoin)
                    if other is not None and (other.is_door or sec.is_door):
                        p.setPen(door_pen)
                    elif other is not None and abs(other.floor - sec.floor) > 0.5:
                        p.setPen(QPen(STEP, 0.9 * px))
                    else:
                        p.setPen(portal_pen)
                p.drawLine(QPointF(a[0], -a[1]), QPointF(b[0], -b[1]))
        # Objects
        if self.objs:
            if show_enemies:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QBrush(ENEMY))
                r = 2.2 * px
                for (x, z) in self.objs.enemy_positions:
                    p.drawEllipse(QPointF(x, -z), r, r)
            if self.objs.player:
                x, z, yaw = self.objs.player
                import math
                r = 6.0 * px
                p.setPen(QPen(PLAYER, 1.5 * px))
                p.setBrush(QBrush(QColor(60, 255, 60, 70)))
                p.drawEllipse(QPointF(x, -z), r, r)
                ang = math.radians(yaw)
                # DF yaw: 0 = +Z, increases clockwise when viewed from above.
                dx, dz = math.sin(ang), math.cos(ang)
                p.setPen(QPen(PLAYER, 2.2 * px))
                p.drawLine(QPointF(x, -z), QPointF(x + dx * r * 2.2, -(z + dz * r * 2.2)))


def render_level_image(level: Level, objs: ObjectInfo | None, width: int, height: int,
                       margin: int = 24, bg: QColor = BG, show_enemies: bool = True) -> QImage:
    img = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(bg)
    mp = MapPainter(level, objs)
    r = mp.rect
    if r.width() < 1 or r.height() < 1:
        return img
    scale = min((width - 2 * margin) / r.width(), (height - 2 * margin) / r.height())
    p = QPainter(img)
    p.translate(width / 2, height / 2)
    p.scale(scale, scale)
    p.translate(-r.center().x(), -r.center().y())
    mp.draw(p, scale, show_enemies)
    p.end()
    return img


class LevelItem(QGraphicsItem):
    def __init__(self, mp: MapPainter):
        super().__init__()
        self.mp = mp
        self.show_enemies = True
        self.setCacheMode(QGraphicsItem.CacheMode.NoCache)

    def boundingRect(self) -> QRectF:
        return self.mp.rect.adjusted(-10, -10, 10, 10)

    def paint(self, painter, option, widget=None):
        scale = painter.worldTransform().m11() or 1.0
        self.mp.draw(painter, scale, self.show_enemies)


class MapView(QGraphicsView):
    """Zoomable, pannable vector view of one level."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setScene(QGraphicsScene(self))
        self.setBackgroundBrush(QBrush(BG))
        self.setRenderHints(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.setFrameShape(QGraphicsView.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.item: LevelItem | None = None
        self.auto_fit = True

    def set_level(self, level: Level | None, objs: ObjectInfo | None = None):
        self.scene().clear()
        self.item = None
        if level is None or not level.sectors:
            return
        self.item = LevelItem(MapPainter(level, objs))
        self.scene().addItem(self.item)
        self.scene().setSceneRect(self.item.boundingRect().adjusted(-200, -200, 200, 200))
        self.auto_fit = True
        self.fit()

    def set_show_enemies(self, on: bool):
        if self.item:
            self.item.show_enemies = on
            self.viewport().update()

    def fit(self):
        if self.item:
            self.fitInView(self.item.boundingRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def wheelEvent(self, e):
        factor = 1.18 if e.angleDelta().y() > 0 else 1 / 1.18
        self.auto_fit = False
        self.scale(factor, factor)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self.auto_fit:
            self.fit()

    def showEvent(self, e):
        super().showEvent(e)
        if self.auto_fit:
            self.fit()

    def mouseDoubleClickEvent(self, e):
        self.auto_fit = True
        self.fit()
