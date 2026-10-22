"""LFD resource reader for Dark Forces menu/briefing art: PLTT palettes, DELT images, ANIM frame sets, FONT glyphs."""
from __future__ import annotations

import struct
from dataclasses import dataclass, field
from pathlib import Path

from PyQt6.QtGui import QImage, QColor


def lfd_entries(data: bytes) -> list[tuple[str, str, int, int]]:
    """Return [(type, name, offset, length)] for every resource in an LFD blob."""
    out = []
    if len(data) < 16:
        return out
    rmap_len = struct.unpack_from("<I", data, 12)[0]
    p = 16 + rmap_len
    while p + 16 <= len(data):
        t = data[p:p + 4].decode("latin1")
        name = data[p + 4:p + 12].split(b"\0")[0].decode("latin1")
        ln = struct.unpack_from("<I", data, p + 12)[0]
        out.append((t, name, p + 16, ln))
        p += 16 + ln
    return out


class Lfd:
    def __init__(self, data: bytes):
        self.data = data
        self.res: dict[tuple[str, str], tuple[int, int]] = {}
        self.order: list[tuple[str, str]] = []
        for t, n, o, l in lfd_entries(data):
            key = (t.upper(), n.lower())
            self.res[key] = (o, l)
            self.order.append(key)

    @classmethod
    def from_file(cls, path: str | Path) -> "Lfd":
        return cls(Path(path).read_bytes())

    def has(self, t: str, name: str) -> bool:
        return (t.upper(), name.lower()) in self.res

    def raw(self, t: str, name: str) -> bytes:
        o, l = self.res[(t.upper(), name.lower())]
        return self.data[o:o + l]

    def names(self, t: str) -> list[str]:
        return [n for (tt, n) in self.order if tt == t.upper()]

    def palette(self, name: str | None = None) -> list[tuple[int, int, int]]:
        if name is None:
            names = self.names("PLTT")
            if not names:
                return [(i, i, i) for i in range(256)]
            name = names[0]
        return parse_pltt(self.raw("PLTT", name))

    def delt(self, name: str, pal=None) -> QImage:
        return delt_to_image(self.raw("DELT", name), pal or self.palette())

    def anim_frames(self, name: str, pal=None, limit: int | None = None) -> list[QImage]:
        b = self.raw("ANIM", name)
        n = struct.unpack_from("<h", b, 0)[0]
        pal = pal or self.palette()
        out = []
        p = 2
        for i in range(n):
            if p + 4 > len(b):
                break
            sz = struct.unpack_from("<I", b, p)[0]
            out.append(delt_to_image(b[p + 4:p + 4 + sz], pal))
            p += 4 + sz
            if limit and len(out) >= limit:
                break
        return out


def parse_pltt(b: bytes) -> list[tuple[int, int, int]]:
    first, last = b[0], b[1]
    pal = [(0, 0, 0)] * 256
    p = 2
    for i in range(first, min(last, 255) + 1):
        if p + 3 > len(b):
            break
        pal[i] = (b[p], b[p + 1], b[p + 2])
        p += 3
    mx = max(max(c) for c in pal)
    if mx <= 63:  # 6-bit VGA palette
        pal = [(r * 4, g * 4, bb * 4) for r, g, bb in pal]
    return pal


@dataclass
class Delt:
    ox: int
    oy: int
    w: int
    h: int
    pixels: list[list[int | None]] = field(default_factory=list)


def parse_delt(b: bytes) -> Delt:
    ox, oy, sx, sy = struct.unpack_from("<hhhh", b, 0)
    w, h = sx - ox + 1, sy - oy + 1
    if w <= 0 or h <= 0 or w > 4096 or h > 4096:
        return Delt(0, 0, 1, 1, [[None]])
    img = [[None] * w for _ in range(h)]

    def put(x, y, v):
        yy, xx = y - oy, x - ox
        if 0 <= yy < h and 0 <= xx < w:
            img[yy][xx] = v

    p = 8
    n = len(b)
    while p + 2 <= n:
        st = struct.unpack_from("<h", b, p)[0]
        p += 2
        if st == 0:
            break
        if p + 4 > n:
            break
        x, y = struct.unpack_from("<hh", b, p)
        p += 4
        count, rle = st >> 1, st & 1
        px = 0
        while px < count and p < n:
            if rle:
                c = b[p]
                p += 1
                if c & 1:
                    v = b[p]
                    p += 1
                    for _ in range(c >> 1):
                        put(x + px, y, v)
                        px += 1
                else:
                    for _ in range(c >> 1):
                        if p >= n:
                            break
                        put(x + px, y, b[p])
                        p += 1
                        px += 1
            else:
                put(x + px, y, b[p])
                p += 1
                px += 1
    return Delt(ox, oy, w, h, img)


def delt_to_image(b: bytes, pal) -> QImage:
    d = parse_delt(b)
    img = QImage(d.w, d.h, QImage.Format.Format_ARGB32)
    img.fill(0)
    for y in range(d.h):
        row = d.pixels[y]
        for x in range(d.w):
            v = row[x]
            if v is not None:
                r, g, bb = pal[v]
                img.setPixel(x, y, (255 << 24) | (r << 16) | (g << 8) | bb)
    return img
