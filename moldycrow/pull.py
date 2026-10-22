"""The Random Pull: the Agent Menu's MISSIONS display spins through mission names over a starfield, then locks in."""
from __future__ import annotations

import math
import random
import time

from PyQt6.QtCore import Qt, QVariantAnimation, QEasingCurve, QTimer, pyqtSignal, QThread, QRectF, QRect, QPointF, QPropertyAnimation
from PyQt6.QtGui import QPainter, QColor, QFont, QPen, QBrush, QImage, QPixmap, QLinearGradient, QRadialGradient, QPolygonF
from PyQt6.QtWidgets import (QWidget, QFrame, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QStackedWidget,
                             QGraphicsOpacityEffect, QSizePolicy)

from .library import ModInfo, load_level
from .mapview import render_level_image
from .widgets import ChipRow
from .assets import Art
from .dfwidgets import (BitmapLabel, DFButton, RedHeader, SteelPanel, GreenWell, PdaFrame, draw_bevel,
                        GREEN, GREEN_DIM, GREEN_BG, RED_TEXT, RED_BAND, STEEL_FACE, AMBER, BLACK)
from .theme import MUTED, TEXT

ITEM_H = 56
FLAVOR = [
    "The Empire won't infiltrate itself.",
    "Jan's waiting in the Moldy Crow. Move.",
    "Grab the Bryar. Check your shields. Go.",
    "Mission briefing incoming from Mon Mothma.",
    "Somewhere, a Dark Trooper is warming up.",
    "Keys, codes, and a suspicious number of vents.",
    "Trust the map. The map has never lied. (It has.)",
    "Kyle Katarn does not need a difficulty setting.",
    "The Rebellion thanks you for your service.",
    "Objective: everything. Secondary objective: secrets.",
    "This one has a story. Probably about a base.",
    "May the Force be with you. You'll want it.",
]


class ThumbWorker(QThread):
    ready = pyqtSignal(object, QImage)

    def __init__(self, mod: ModInfo, w: int, h: int, parent=None):
        super().__init__(parent)
        self.mod, self.w, self.h = mod, w, h

    def run(self):
        img = QImage(self.w, self.h, QImage.Format.Format_ARGB32_Premultiplied)
        img.fill(BLACK)
        try:
            lv = self.mod.levels[0] if self.mod.levels else None
            if lv is not None:
                level, objs = load_level(self.mod, lv)
                if level is not None:
                    img = render_level_image(level, objs, self.w, self.h, margin=14)
        except Exception:  # noqa: BLE001
            pass
        self.ready.emit(self.mod, img)


class MapCover(QWidget):
    """Black PDA screen reading MAP CLASSIFIED, or the rendered map once peeked."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.img: QImage | None = None
        self.opacity = 0.0

    def set_image(self, img: QImage | None):
        self.img = img
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        r = self.rect()
        p.fillRect(r, BLACK)
        art = Art.get()
        if self.img is not None and self.opacity > 0:
            p.setOpacity(self.opacity)
            scaled = self.img.scaled(r.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            p.drawImage((r.width() - scaled.width()) // 2, (r.height() - scaled.height()) // 2, scaled)
            p.setOpacity(1.0)
        if self.img is None or self.opacity < 1.0:
            p.setOpacity(1.0 - self.opacity)
            if art.font.ok:
                t = art.font.render("MAP CLASSIFIED", 3, RED_TEXT)
                p.drawImage((r.width() - t.width()) // 2, r.height() // 2 - t.height() - 6, t)
                s1 = art.font.render("LAYOUT WITHHELD UNTIL PLAYED", 2, GREEN_DIM)
                p.drawImage((r.width() - s1.width()) // 2, r.height() // 2 + 6, s1)
                s2 = art.font.render("GO IN BLIND, LIKE KYLE WOULD", 2, GREEN_DIM)
                p.drawImage((r.width() - s2.width()) // 2, r.height() // 2 + 6 + s1.height() + 6, s2)
            else:
                p.setPen(RED_TEXT)
                p.drawText(r, Qt.AlignmentFlag.AlignCenter, "MAP CLASSIFIED")
        p.end()


class RevealCard(SteelPanel):
    play = pyqtSignal()
    again = pyqtSignal()
    skip = pyqtSignal()
    close_req = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(6, 6, 6, 6)
        outer.setSpacing(6)
        self.header = RedHeader("YOUR NEXT MISSION", 3)
        outer.addWidget(self.header)
        lay = QHBoxLayout()
        lay.setContentsMargins(10, 6, 10, 10)
        lay.setSpacing(16)
        outer.addLayout(lay)
        left = QVBoxLayout()
        left.setSpacing(6)
        self.cover = MapCover()
        self.pda = PdaFrame(self.cover)
        self.pda.setFixedSize(600, 375)
        left.addWidget(self.pda)
        self.b_peek = DFButton("PEEK AT MAP (SPOILERS)")
        self.b_peek.clicked.connect(self._peek)
        left.addWidget(self.b_peek)
        lay.addLayout(left)
        self._img: QImage | None = None
        self._peeked = False

        right = QVBoxLayout()
        right.setSpacing(6)
        self.title = BitmapLabel("", 3, GREEN)
        self.title.setMinimumWidth(420)
        right.addWidget(self.title)
        self.sub = QLabel("")
        self.sub.setObjectName("greendim")
        self.sub.setWordWrap(True)
        right.addWidget(self.sub)
        self.chips = ChipRow()
        right.addWidget(self.chips)
        well = GreenWell()
        wl = QVBoxLayout(well)
        wl.setContentsMargins(10, 8, 10, 8)
        self.desc = QLabel("")
        self.desc.setWordWrap(True)
        self.desc.setObjectName("green")
        self.desc.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        wl.addWidget(self.desc, 1)
        self.flavor = QLabel("")
        self.flavor.setStyleSheet(f"color: {AMBER.name()}; font-style: italic;")
        wl.addWidget(self.flavor)
        right.addWidget(well, 1)
        btns = QHBoxLayout()
        self.b_play = DFButton("BEGIN MISSION", primary=True)
        self.b_again = DFButton("SPIN AGAIN")
        self.b_skip = DFButton("SKIP")
        self.b_close = DFButton("CLOSE")
        for b in (self.b_play, self.b_again, self.b_skip):
            btns.addWidget(b)
        btns.addStretch(1)
        btns.addWidget(self.b_close)
        right.addLayout(btns)
        lay.addLayout(right, 1)
        self.b_play.clicked.connect(self.play)
        self.b_again.clicked.connect(self.again)
        self.b_skip.clicked.connect(self.skip)
        self.b_close.clicked.connect(self.close_req)
        self.setFixedWidth(1180)

    def set_mod(self, mod: ModInfo):
        self.title.setText(mod.title.upper())
        parts = []
        if mod.author:
            parts.append(f"by {mod.author}")
        if mod.levels:
            names = ", ".join(l.display for l in mod.levels[:4])
            if len(mod.levels) > 4:
                names += f" +{len(mod.levels) - 4} more"
            parts.append(names)
        self.sub.setText("  ·  ".join(parts))
        chips = [(mod.size_tag.upper(), "chipAccent"), (f"{len(mod.levels)} level{'s' if len(mod.levels) != 1 else ''}", "chip")]
        if mod.sectors:
            chips.append((f"{mod.sectors:,} sectors", "chip"))
        if mod.enemies:
            chips.append((f"{mod.enemies} hostiles", "chip"))
        if mod.secrets:
            chips.append((f"{mod.secrets} secrets", "chip"))
        if mod.has_cutscenes:
            chips.append(("cutscenes", "chip"))
        self.chips.set_chips(chips)
        d = mod.description.strip()
        if len(d) > 420:
            d = d[:417].rsplit(" ", 1)[0] + "…"
        self.desc.setText(d or "No briefing text in this mod's readme.")
        self.flavor.setText(random.choice(FLAVOR))
        self._img = None
        self._peeked = False
        self.cover.set_image(None)
        self.cover.opacity = 0.0
        self.b_peek.setEnabled(False)
        self.b_peek.setText("PEEK AT MAP (SPOILERS)")

    def _peek(self):
        if self._img is None:
            return
        if self._peeked:
            self._peeked = False
            self.b_peek.setText("PEEK AT MAP (SPOILERS)")
            self.cover.opacity = 0.0
            self.cover.set_image(None)
            return
        self._peeked = True
        self.b_peek.setText("HIDE MAP")
        self._fade_in(self._img)

    def set_thumb(self, img: QImage):
        self._img = img
        self.b_peek.setEnabled(True)
        if self._peeked:
            self._fade_in(img)

    def _fade_in(self, img: QImage):
        self.cover.set_image(img)
        anim = QVariantAnimation(self)
        anim.setDuration(650)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        def step(v):
            self.cover.opacity = float(v)
            self.cover.update()
        anim.valueChanged.connect(step)
        anim.start(QVariantAnimation.DeletionPolicy.DeleteWhenStopped)
        self._anim = anim


class PullOverlay(QWidget):
    """Covers the main window. start(pool) → spins → reveal. Emits play(mod)."""
    play = pyqtSignal(object)
    closed = pyqtSignal()

    def __init__(self, parent: QWidget, sfx=None):
        super().__init__(parent)
        self.sfx = sfx
        self.art = Art.get()
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.hide()
        self.phase = "idle"
        self.reel: list[str] = []
        self.offset = 0.0
        self.last_idx = -1
        self.last_tick_t = 0.0
        self.tick = 0.0
        self.winner: ModInfo | None = None
        self.pool: list[ModInfo] = []
        self.skipped: set[str] = set()
        self.thumb_img: QImage | None = None
        self.worker: ThumbWorker | None = None
        self.anim = QVariantAnimation(self)
        self.anim.valueChanged.connect(self._on_value)
        self.anim.finished.connect(self._on_finished)
        self.tick_timer = QTimer(self)
        self.tick_timer.setInterval(16)
        self.tick_timer.timeout.connect(self._decay)
        self.card = RevealCard(self)
        self.card.hide()
        self.card.play.connect(self._play)
        self.card.again.connect(self.spin)
        self.card.skip.connect(self._skip)
        self.card.close_req.connect(self.close_overlay)
        self.hint = BitmapLabel("SPACE  SPIN      ENTER  BEGIN      ESC  CLOSE", 2, GREEN_DIM, Qt.AlignmentFlag.AlignHCenter, self)

    def _cue(self, name: str):
        if self.sfx is not None:
            self.sfx.cue(name)

    # ----- lifecycle -----
    def start(self, pool: list[ModInfo]):
        self.pool = pool
        self.skipped.clear()
        self.setGeometry(self.parent().rect())
        self.show()
        self.raise_()
        self.setFocus()
        self._cue("open")
        self.spin()

    def close_overlay(self):
        self.anim.stop()
        self.tick_timer.stop()
        self.card.hide()
        self.phase = "idle"
        self.hide()
        self.closed.emit()

    def resizeEvent(self, e):
        self._place_card()

    def _place_card(self):
        r = self.rect()
        self.card.adjustSize()
        self.card.move((r.width() - self.card.width()) // 2, max(20, (r.height() - self.card.height()) // 2))
        self.hint.setGeometry(0, r.height() - 44, r.width(), 30)

    def candidates(self) -> list[ModInfo]:
        return [m for m in self.pool if m.file not in self.skipped]

    # ----- spinning -----
    def spin(self):
        cands = self.candidates()
        self.card.hide()
        if not cands:
            self.phase = "empty"
            self.update()
            return
        self.winner = random.choice(cands)
        titles = [m.title.upper() for m in cands]
        n = min(44, max(18, len(titles)))
        self.reel = [random.choice(titles) for _ in range(n)]
        self.reel.append(self.winner.title.upper())
        self.reel += [random.choice(titles) for _ in range(4)]
        self.win_idx = n
        self.offset = 0.0
        self.last_idx = -1
        self.tick = 0.0
        self.phase = "spin"
        self.thumb_img = None
        self.worker = ThumbWorker(self.winner, 560, 300, self)
        self.worker.ready.connect(self._thumb_ready)
        self.worker.start()
        self.anim.stop()
        self.anim.setStartValue(0.0)
        self.anim.setEndValue(float(self.win_idx * ITEM_H))
        self.anim.setDuration(3600 + random.randint(0, 500))
        self.anim.setEasingCurve(QEasingCurve.Type.OutQuint)
        self.anim.start()
        self.tick_timer.start()
        self.update()

    def _on_value(self, v):
        self.offset = float(v)
        idx = int(self.offset / ITEM_H + 0.5)
        if idx != self.last_idx:
            self.last_idx = idx
            self.tick = 1.0
            now = time.monotonic()
            if now - self.last_tick_t > 0.06:
                self.last_tick_t = now
                self._cue("tick")
        self.update()

    def _decay(self):
        self.tick = max(0.0, self.tick - 0.08)
        if self.phase == "spin":
            self.update()

    def _on_finished(self):
        self.tick_timer.stop()
        self.phase = "landed"
        self.tick = 1.0
        self._cue("land")
        self.update()
        QTimer.singleShot(520, self._reveal)

    def _thumb_ready(self, mod, img):
        if self.winner is not None and mod.file == self.winner.file:
            self.thumb_img = img
            if self.phase == "reveal":
                self.card.set_thumb(img)

    def _reveal(self):
        if self.winner is None:
            return
        self.phase = "reveal"
        self.card.set_mod(self.winner)
        self.card.show()
        self._place_card()
        if self.thumb_img is not None:
            self.card.set_thumb(self.thumb_img)
        self.card.b_play.setFocus()
        self._cue("reveal")
        self.update()

    def _play(self):
        if self.winner is not None:
            w = self.winner
            self.close_overlay()
            self.play.emit(w)

    def _skip(self):
        if self.winner is not None:
            self.skipped.add(self.winner.file)
        self._cue("click")
        self.spin()

    # ----- input -----
    def keyPressEvent(self, e):
        k = e.key()
        if k == Qt.Key.Key_Escape:
            self.close_overlay()
        elif k == Qt.Key.Key_Space and self.phase in ("reveal", "empty"):
            self.spin()
        elif k in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and self.phase == "reveal":
            self._play()
        else:
            super().keyPressEvent(e)

    def mousePressEvent(self, e):
        e.accept()

    # ----- painting -----
    def paintEvent(self, e):
        p = QPainter(self)
        r = self.rect()
        p.fillRect(r, BLACK)
        st = self.art.stars
        if st is not None:
            p.setOpacity(0.5)
            p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
            for y in range(0, r.height(), st.height() * 3):
                for x in range(0, r.width(), st.width() * 3):
                    p.drawImage(QRect(x, y, st.width() * 3, st.height() * 3), st)
            p.setOpacity(1.0)
        if self.phase in ("spin", "landed"):
            self._paint_reel(p, r)
        elif self.phase == "empty":
            if self.art.font.ok:
                t = self.art.font.render("NOTHING LEFT IN THE POOL", 3, RED_TEXT)
                p.drawImage((r.width() - t.width()) // 2, r.height() // 2 - 40, t)
                t2 = self.art.font.render("UNCHECK 'UNPLAYED ONLY' OR CLEAR SOME SKIPS", 2, GREEN_DIM)
                p.drawImage((r.width() - t2.width()) // 2, r.height() // 2 + 10, t2)
            else:
                p.setPen(RED_TEXT)
                p.drawText(r, Qt.AlignmentFlag.AlignCenter, "Nothing left in the pool.")
        p.end()

    def _paint_reel(self, p: QPainter, r):
        cx, cy = r.width() / 2, r.height() / 2 - 10
        band_w = min(960, r.width() - 80)
        panel = QRect(int(cx - band_w / 2 - 14), int(cy - ITEM_H * 4.2 - 44), int(band_w + 28), int(ITEM_H * 8.4 + 44))
        draw_bevel(p, panel, raised=True)
        # red header band
        hdr = QRect(panel.left() + 6, panel.top() + 6, panel.width() - 12, 30)
        p.fillRect(hdr, RED_BAND)
        if self.art.font.ok:
            t = self.art.font.render("MISSION SELECT" if self.phase == "spin" else "MISSION LOCKED IN", 3, RED_TEXT)
            p.drawImage(hdr.center().x() - t.width() // 2, hdr.center().y() - t.height() // 2, t)
        # green well
        well = QRect(panel.left() + 6, hdr.bottom() + 6, panel.width() - 12, panel.bottom() - hdr.bottom() - 12)
        draw_bevel(p, well, raised=False, face=GREEN_BG)
        inner = well.adjusted(3, 3, -3, -3)
        p.setClipRect(inner)
        idx_f = self.offset / ITEM_H
        center = int(math.floor(idx_f))
        for i in range(center - 5, center + 7):
            if i < 0 or i >= len(self.reel):
                continue
            dy = (i - idx_f) * ITEM_H
            y = cy + dy
            dist = abs(dy) / ITEM_H
            if dist > 4.6:
                continue
            fade = max(0.0, 1.0 - dist / 4.4)
            if dist < 0.5:
                col = QColor("#c8ffc8"); scale = 3
            else:
                col = QColor(GREEN_DIM) if dist > 1.5 else QColor(GREEN); scale = 2
            col.setAlphaF(fade)
            txt = self.reel[i]
            if self.art.font.ok:
                maxw = inner.width() - 40
                while txt and self.art.font.width(txt) * scale > maxw:
                    txt = txt[:-1]
                img = self.art.font.render(txt, scale, col)
                p.drawImage(int(cx - img.width() / 2), int(y - img.height() / 2), img)
            else:
                f = QFont(); f.setPointSize(14 if dist >= 0.5 else 22); f.setBold(True)
                p.setFont(f); p.setPen(col)
                p.drawText(QRectF(inner.left(), y - ITEM_H / 2, inner.width(), ITEM_H), Qt.AlignmentFlag.AlignCenter, txt)
        p.setClipping(False)
        # red selection box like BEGIN MISSION's highlight
        glow = int(90 + 120 * self.tick)
        pen = QPen(QColor(255, 52, 52, min(255, glow)), 2 + 2 * self.tick)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        band = QRectF(inner.left() + 10, cy - ITEM_H / 2 + 4, inner.width() - 20, ITEM_H - 8)
        p.drawRect(band)
        # side markers
        p.setBrush(QBrush(QColor(RED_TEXT)))
        p.setPen(Qt.PenStyle.NoPen)
        tri = 8
        for sx, d in ((band.left() - 4, -1), (band.right() + 4, 1)):
            poly = QPolygonF([QPointF(sx, cy - tri), QPointF(sx, cy + tri), QPointF(sx - d * tri * 1.4, cy)])
            p.drawPolygon(poly)
        # pool size under the panel
        if self.art.font.ok:
            t = self.art.font.render(f"{len(self.candidates())} MISSIONS IN THE POOL", 2, GREEN_DIM)
            p.drawImage(int(cx - t.width() / 2), panel.bottom() + 10, t)
