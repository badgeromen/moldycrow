"""Dark Forces Agent-Menu styled widgets: bitmap-font labels, bevelled steel buttons, red header bands, the PDA frame."""
from __future__ import annotations

from PyQt6.QtCore import Qt, QSize, QRect, QRectF, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QFont, QPen, QBrush, QLinearGradient, QImage, QFontMetrics
from PyQt6.QtWidgets import QWidget, QPushButton, QFrame, QVBoxLayout, QSizePolicy, QLabel

from .assets import Art

# Agent Menu palette
STEEL = QColor("#5c5c5c")
STEEL_LIGHT = QColor("#8f8f8f")
STEEL_DARK = QColor("#2e2e2e")
STEEL_FACE = QColor("#4a4a4a")
RED_BAND = QColor("#6e0606")
RED_TEXT = QColor("#ff3434")
GREEN = QColor("#3cff3c")
GREEN_DIM = QColor("#1d8f1d")
GREEN_BG = QColor("#02160a")
BLACK = QColor("#000000")
AMBER = QColor("#ffd23b")


def draw_bevel(p: QPainter, r: QRect, raised: bool = True, face: QColor = STEEL_FACE, width: int = 2):
    p.fillRect(r, face)
    hi = STEEL_LIGHT if raised else STEEL_DARK
    lo = STEEL_DARK if raised else STEEL_LIGHT
    for i in range(width):
        p.setPen(hi)
        p.drawLine(r.left() + i, r.top() + i, r.right() - i, r.top() + i)
        p.drawLine(r.left() + i, r.top() + i, r.left() + i, r.bottom() - i)
        p.setPen(lo)
        p.drawLine(r.left() + i, r.bottom() - i, r.right() - i, r.bottom() - i)
        p.drawLine(r.right() - i, r.top() + i, r.right() - i, r.bottom() - i)


class BitmapLabel(QWidget):
    """Text in the game's 8px menu font, scaled with crisp pixels. Falls back to a bold system font."""

    def __init__(self, text: str = "", scale: int = 2, color=GREEN, align=Qt.AlignmentFlag.AlignLeft, parent=None):
        super().__init__(parent)
        self._text = text
        self._scale = scale
        self._color = QColor(color)
        self._align = align
        self.art = Art.get()
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

    def setText(self, t: str):
        self._text = t
        self.updateGeometry()
        self.update()

    def text(self) -> str:
        return self._text

    def setColor(self, c):
        self._color = QColor(c)
        self.update()

    def setScale(self, s: int):
        self._scale = s
        self.updateGeometry()
        self.update()

    def sizeHint(self) -> QSize:
        if self.art.font.ok:
            return QSize(self.art.font.width(self._text) * self._scale + 4, self.art.font.height * self._scale + 4)
        fm = QFontMetrics(self._fallback_font())
        return QSize(fm.horizontalAdvance(self._text) + 4, fm.height() + 4)

    def minimumSizeHint(self) -> QSize:
        return QSize(10, self.sizeHint().height())

    def _fallback_font(self) -> QFont:
        f = QFont()
        f.setPointSize(6 + 4 * self._scale)
        f.setBold(True)
        f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1)
        return f

    def paintEvent(self, e):
        p = QPainter(self)
        r = self.rect()
        if self.art.font.ok:
            img = self.art.font.render(self._text, self._scale, self._color)
            if img.width() > r.width() - 2 and len(self._text) > 4:
                # Elide to fit
                t = self._text
                while t and self.art.font.width(t + "..") * self._scale > r.width() - 2:
                    t = t[:-1]
                img = self.art.font.render(t + "..", self._scale, self._color)
            x = 2
            if self._align & Qt.AlignmentFlag.AlignHCenter:
                x = (r.width() - img.width()) // 2
            elif self._align & Qt.AlignmentFlag.AlignRight:
                x = r.width() - img.width() - 2
            y = (r.height() - img.height()) // 2
            p.drawImage(x, y, img)
        else:
            p.setFont(self._fallback_font())
            p.setPen(self._color)
            p.drawText(r, int(self._align | Qt.AlignmentFlag.AlignVCenter), self._text)
        p.end()


class RedHeader(QWidget):
    """The Agent Menu's red title band with red bitmap text."""

    def __init__(self, text: str, scale: int = 2, parent=None):
        super().__init__(parent)
        self.label = BitmapLabel(text, scale, RED_TEXT, Qt.AlignmentFlag.AlignHCenter, self)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 3, 6, 3)
        lay.addWidget(self.label)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def setText(self, t: str):
        self.label.setText(t)

    def paintEvent(self, e):
        p = QPainter(self)
        r = self.rect()
        p.fillRect(r, RED_BAND)
        p.setPen(QColor("#a51010"))
        p.drawLine(r.left(), r.top(), r.right(), r.top())
        p.setPen(QColor("#3a0000"))
        p.drawLine(r.left(), r.bottom(), r.right(), r.bottom())
        p.end()


class DFButton(QPushButton):
    """Bevelled steel button with bitmap-font caption; 'primary' gets the red BEGIN MISSION highlight."""

    def __init__(self, text: str = "", primary: bool = False, scale: int = 2, parent=None):
        super().__init__(text, parent)
        self.primary = primary
        self.scale = scale
        self.art = Art.get()
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumHeight(30)

    def sizeHint(self) -> QSize:
        t = self.text().replace("&", "")
        if self.art.font.ok:
            w = self.art.font.width(t) * self.scale + 26
            h = self.art.font.height * self.scale + 16
        else:
            fm = QFontMetrics(self.font())
            w, h = fm.horizontalAdvance(t) + 26, fm.height() + 14
        return QSize(max(w, 70), max(h, 30))

    def paintEvent(self, e):
        p = QPainter(self)
        r = self.rect()
        down = self.isDown() or self.isChecked()
        draw_bevel(p, r, raised=not down)
        if self.primary:
            p.setPen(QPen(QColor("#c81616"), 2))
            p.drawRect(r.adjusted(3, 3, -4, -4))
        col = GREEN if self.isEnabled() else QColor("#6a6a6a")
        if self.underMouse() and self.isEnabled():
            col = QColor("#a8ffa8")
        if self.primary and self.isEnabled():
            col = RED_TEXT if not self.underMouse() else QColor("#ff8a8a")
        t = self.text().replace("&", "")
        off = 1 if down else 0
        if self.art.font.ok:
            img = self.art.font.render(t, self.scale, col)
            p.drawImage((r.width() - img.width()) // 2 + off, (r.height() - img.height()) // 2 + off, img)
        else:
            f = QFont(); f.setBold(True); p.setFont(f); p.setPen(col)
            p.drawText(r.translated(off, off), Qt.AlignmentFlag.AlignCenter, t)
        if self.hasFocus():
            p.setPen(QPen(QColor(60, 255, 60, 120), 1, Qt.PenStyle.DotLine))
            p.drawRect(r.adjusted(5, 5, -6, -6))
        p.end()

    def enterEvent(self, e):
        self.update(); super().enterEvent(e)

    def leaveEvent(self, e):
        self.update(); super().leaveEvent(e)


class SteelPanel(QFrame):
    """Raised steel bevel panel; children laid out inside by the caller."""

    def __init__(self, parent=None, sunken: bool = False, face: QColor = STEEL_FACE):
        super().__init__(parent)
        self.sunken = sunken
        self.face = face
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)

    def paintEvent(self, e):
        p = QPainter(self)
        draw_bevel(p, self.rect(), raised=not self.sunken, face=self.face)
        p.end()


class GreenWell(QFrame):
    """Sunken black-green display area, like the AGENTS / MISSIONS lists."""

    def paintEvent(self, e):
        p = QPainter(self)
        r = self.rect()
        draw_bevel(p, r, raised=False, face=GREEN_BG)
        p.end()


class PdaFrame(QWidget):
    """Draws the in-game PDA bezel (scaled, crisp) and keeps a child widget inside its screen cutout."""

    def __init__(self, inner: QWidget, parent=None):
        super().__init__(parent)
        self.art = Art.get()
        self.inner = inner
        inner.setParent(self)
        self.setMinimumSize(360, 240)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def _geometry(self):
        fr = self.art.pda_frame
        if fr is None:
            return None
        s = min(self.width() / fr.width(), self.height() / fr.height())
        w, h = int(fr.width() * s), int(fr.height() * s)
        x, y = (self.width() - w) // 2, (self.height() - h) // 2
        return s, QRect(x, y, w, h)

    def resizeEvent(self, e):
        g = self._geometry()
        if g is None:
            self.inner.setGeometry(self.rect().adjusted(6, 6, -6, -6))
            return
        s, fr = g
        hole = self.art.pda_inner
        self.inner.setGeometry(QRect(fr.x() + int(hole.x() * s), fr.y() + int(hole.y() * s),
                                     int(hole.width() * s), int(hole.height() * s)))

    def paintEvent(self, e):
        p = QPainter(self)
        p.fillRect(self.rect(), BLACK)
        g = self._geometry()
        if g is None:
            draw_bevel(p, self.rect(), raised=True)
            p.end()
            return
        s, fr = g
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        p.drawImage(fr, self.art.pda_frame)
        p.end()


class Starfield(QWidget):
    """Tiled starfield from darklogo.lfd, used behind the mission-select reel."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.art = Art.get()

    def paintEvent(self, e):
        p = QPainter(self)
        p.fillRect(self.rect(), BLACK)
        st = self.art.stars
        if st is not None:
            p.setOpacity(0.55)
            for y in range(0, self.height(), st.height() * 2):
                for x in range(0, self.width(), st.width() * 2):
                    p.drawImage(QRect(x, y, st.width() * 2, st.height() * 2), st)
        p.end()
