"""Game art loaded from the user's own Dark Forces install: menu font, PDA frame, Agent Menu backdrop, starfield."""
from __future__ import annotations

import struct
from pathlib import Path

from PyQt6.QtCore import QRect, Qt
from PyQt6.QtGui import QImage, QPainter, QColor

from .library import stock_gob_path
from .paths import CACHE_DIR
from .lfd import Lfd

ART_CACHE = CACHE_DIR / "art"


def base_game_dir() -> Path | None:
    p = stock_gob_path()
    return p.parent if p else None


class BitmapFont:
    """The 8px LFD FONT: first char, glyph count, height, then widths and 8 row-bytes per glyph."""

    def __init__(self, raw: bytes | None):
        self.ok = False
        if not raw or len(raw) < 12:
            return
        self.first, self.count, self.height, _bpl = struct.unpack_from("<hhhh", raw, 0)
        self.widths = list(raw[12:12 + self.count])
        self.data = raw[12 + self.count:]
        self.per = max(1, len(self.data) // max(1, self.count))
        self.ok = self.count > 0 and len(self.data) >= self.count * self.per
        self._cache: dict[tuple, QImage] = {}

    def width(self, text: str) -> int:
        w = 0
        for c in text:
            i = ord(c) - self.first
            w += (self.widths[i] if 0 <= i < self.count else 3) + 1
        return max(0, w - 1)

    def render(self, text: str, scale: int = 3, color: QColor | str = "#3cff3c") -> QImage:
        color = QColor(color)
        key = (text, scale, color.rgba())
        if key in self._cache:
            return self._cache[key]
        w = max(1, self.width(text) * scale)
        img = QImage(w, self.height * scale, QImage.Format.Format_ARGB32)
        img.fill(0)
        p = QPainter(img)
        x = 0
        for c in text:
            i = ord(c) - self.first
            if 0 <= i < self.count:
                gw = self.widths[i]
                base = i * self.per
                for row in range(min(self.height, self.per)):
                    byte = self.data[base + row]
                    for col in range(gw):
                        if byte & (0x80 >> col):
                            p.fillRect(x + col * scale, row * scale, scale, scale, color)
                x += (gw + 1) * scale
            else:
                x += 4 * scale
        p.end()
        if len(self._cache) > 400:
            self._cache.clear()
        self._cache[key] = img
        return img


class Art:
    """Singleton-ish holder. Everything is optional: with no base game found, widgets fall back to plain drawing."""
    _inst: "Art | None" = None

    def __init__(self):
        self.font = BitmapFont(None)
        self.pda_frame: QImage | None = None
        self.pda_inner = QRect(14, 12, 292, 156)
        self.agent_backdrop: QImage | None = None
        self.stars: QImage | None = None
        self.cursor: QImage | None = None
        self.available = False
        base = base_game_dir()
        if base is None:
            return
        try:
            menu = Lfd.from_file(base / "lfd" / "menu.lfd")
            if menu.has("FONT", "font8"):
                self.font = BitmapFont(menu.raw("FONT", "font8"))
            pal = menu.palette("menu") if menu.has("PLTT", "menu") else menu.palette()
            frames = menu.anim_frames("pda", pal=pal, limit=1)
            if frames:
                self.pda_frame = frames[0]
                self.pda_inner = self._find_hole(self.pda_frame)
            if menu.has("DELT", "cursor"):
                self.cursor = menu.delt("cursor", pal)
        except Exception:  # noqa: BLE001
            pass
        try:
            agent = Lfd.from_file(base / "lfd" / "agentmnu.lfd")
            fr = agent.anim_frames("agentmnu", limit=1)
            if fr:
                self.agent_backdrop = fr[0]
        except Exception:  # noqa: BLE001
            pass
        try:
            logo = Lfd.from_file(base / "lfd" / "darklogo.lfd")
            if logo.has("DELT", "darklgbc"):
                self.stars = logo.delt("darklgbc", logo.palette("darklgbc") if logo.has("PLTT", "darklgbc") else None)
        except Exception:  # noqa: BLE001
            pass
        self.available = self.font.ok

    @staticmethod
    def _find_hole(img: QImage) -> QRect:
        """Bounding box of the transparent viewport in the middle of the PDA frame."""
        w, h = img.width(), img.height()
        cx, cy = w // 2, h // 2

        def hole(x, y):
            c = img.pixelColor(x, y)
            return c.alpha() == 0 or (c.red() + c.green() + c.blue()) < 30

        if not hole(cx, cy):
            return QRect(24, 13, w - 40, h - 48)
        left = cx
        while left > 0 and hole(left - 1, cy):
            left -= 1
        right = cx
        while right < w - 1 and hole(right + 1, cy):
            right += 1
        top = cy
        while top > 0 and hole(cx, top - 1):
            top -= 1
        bottom = cy
        while bottom < h - 1 and hole(cx, bottom + 1):
            bottom += 1
        return QRect(left + 1, top + 1, right - left - 1, bottom - top - 3)

    @classmethod
    def get(cls) -> "Art":
        if cls._inst is None:
            cls._inst = Art()
        return cls._inst
