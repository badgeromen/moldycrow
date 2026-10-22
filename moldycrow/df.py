"""Parsers for Dark Forces data: GOB archives, LEV geometry, O object files, readmes."""
from __future__ import annotations

import re
import struct
import zipfile
from dataclasses import dataclass, field

GOB_MAGIC = b"GOB\n"

# Sector FLAGS (first value)
FLAG_SKY = 0x1
FLAG_DOOR = 0x2
FLAG_PIT = 0x80
FLAG_SECRET = 0x80000

ENEMY_LOGICS = {
    "TROOP", "STORM1", "COMMANDO", "I_OFFICER", "I_OFFICER1", "I_OFFICER2", "I_OFFICER3",
    "I_OFFICER4", "I_OFFICER5", "I_OFFICER6", "I_OFFICER7", "I_OFFICER8", "I_OFFICER9",
    "I_OFFICERR", "I_OFFICERY", "I_OFFICERB", "BOSSK", "G_GUARD", "REE_YEES", "REE_YEES2",
    "SEWER1", "INT_DROID", "PROBE_DROID", "REMOTE", "TURRET", "MOUSEBOT", "WELDER",
    "D_TROOP1", "D_TROOP2", "D_TROOP3", "BOBA_FETT", "KELL", "PHASE1", "PHASE2", "PHASE3",
}
BOSS_LOGICS = {"BOBA_FETT", "KELL", "PHASE1", "PHASE2", "PHASE3", "D_TROOP3", "BOSSK"}


class Gob:
    """Minimal reader for the LucasArts GOB container format."""

    def __init__(self, data: bytes):
        if data[:4] != GOB_MAGIC:
            raise ValueError("not a GOB archive")
        cat = struct.unpack_from("<I", data, 4)[0]
        count = struct.unpack_from("<I", data, cat)[0]
        p = cat + 4
        self.entries: dict[str, tuple[int, int]] = {}
        for _ in range(count):
            off, ln = struct.unpack_from("<II", data, p)
            name = data[p + 8:p + 21].split(b"\0")[0].decode("latin1").upper()
            self.entries[name] = (off, ln)
            p += 21
        self.data = data

    def __contains__(self, name: str) -> bool:
        return name.upper() in self.entries

    def read(self, name: str) -> bytes:
        off, ln = self.entries[name.upper()]
        return self.data[off:off + ln]

    def names(self, ext: str | None = None) -> list[str]:
        if ext is None:
            return sorted(self.entries)
        ext = "." + ext.upper().lstrip(".")
        return sorted(n for n in self.entries if n.endswith(ext))


@dataclass
class Wall:
    left: int
    right: int
    adjoin: int
    mirror: int
    flags: int


@dataclass
class Sector:
    index: int
    name: str = ""
    ambient: int = 0
    floor: float = 0.0
    ceiling: float = 0.0
    second: float = 0.0
    flags: int = 0
    layer: int = 0
    verts: list[tuple[float, float]] = field(default_factory=list)
    walls: list[Wall] = field(default_factory=list)

    @property
    def is_sky(self) -> bool:
        return bool(self.flags & FLAG_SKY)

    @property
    def is_door(self) -> bool:
        return bool(self.flags & FLAG_DOOR)

    @property
    def is_secret(self) -> bool:
        return bool(self.flags & FLAG_SECRET)

    @property
    def is_pit(self) -> bool:
        return bool(self.flags & FLAG_PIT)


@dataclass
class Level:
    name: str = ""
    palette: str = ""
    music: str = ""
    author: str = ""
    sectors: list[Sector] = field(default_factory=list)

    def bounds(self) -> tuple[float, float, float, float]:
        xs = [x for s in self.sectors for x, _ in s.verts]
        zs = [z for s in self.sectors for _, z in s.verts]
        if not xs:
            return (0, 0, 1, 1)
        return (min(xs), min(zs), max(xs), max(zs))

    @property
    def secrets(self) -> int:
        return sum(1 for s in self.sectors if s.is_secret)


_WALL_RE = re.compile(
    r"LEFT:\s*(-?\d+)\s+RIGHT:\s*(-?\d+).*?ADJOIN:\s*(-?\d+)\s+MIRROR:\s*(-?\d+)"
    r"(?:.*?FLAGS:\s*(-?\d+))?",
    re.S,
)
_VERT_RE = re.compile(r"X:\s*(-?[\d.]+)\s+Z:\s*(-?[\d.]+)")


def _num(s: str) -> float:
    try:
        return float(s)
    except ValueError:
        return 0.0


def parse_lev(raw: bytes) -> Level:
    text = raw.decode("latin1", "replace")
    lvl = Level()
    cur: Sector | None = None
    mode = None  # 'verts' | 'walls' | None
    for line in text.splitlines():
        if "#" in line:
            # Comments start with '#', but vertex lines end with '# n'; strip trailing comment only.
            stripped = line.split("#", 1)[0]
            if not stripped.strip():
                # Whole-line comment; still may carry AUTHOR in the header.
                m = re.match(r"\s*#\s*AUTHOR\s+(.+)", line)
                if m and not lvl.author:
                    lvl.author = m.group(1).strip()
                continue
            line = stripped
        s = line.strip()
        if not s:
            continue
        up = s.upper()
        if up.startswith("SECTOR "):
            try:
                idx = int(s.split()[1])
            except (IndexError, ValueError):
                idx = len(lvl.sectors)
            cur = Sector(index=idx)
            lvl.sectors.append(cur)
            mode = None
            continue
        if cur is None:
            if up.startswith("LEVELNAME"):
                lvl.name = s.split(None, 1)[1].strip() if len(s.split(None, 1)) > 1 else ""
            elif up.startswith("PALETTE"):
                lvl.palette = s.split(None, 1)[1].strip() if len(s.split(None, 1)) > 1 else ""
            elif up.startswith("MUSIC"):
                lvl.music = s.split(None, 1)[1].strip() if len(s.split(None, 1)) > 1 else ""
            continue
        if mode == "verts" and up.startswith("X:"):
            m = _VERT_RE.search(s)
            if m:
                cur.verts.append((_num(m.group(1)), _num(m.group(2))))
            continue
        if mode == "walls" and up.startswith("WALL"):
            m = _WALL_RE.search(s)
            if m:
                cur.walls.append(Wall(int(m.group(1)), int(m.group(2)), int(m.group(3)),
                                      int(m.group(4)), int(m.group(5) or 0)))
            continue
        if up.startswith("NAME"):
            parts = s.split(None, 1)
            cur.name = parts[1].strip() if len(parts) > 1 else ""
        elif up.startswith("AMBIENT"):
            cur.ambient = int(_num(s.split()[1])) if len(s.split()) > 1 else 0
        elif up.startswith("FLOOR ALTITUDE"):
            cur.floor = _num(s.split()[-1])
        elif up.startswith("CEILING ALTITUDE"):
            cur.ceiling = _num(s.split()[-1])
        elif up.startswith("SECOND ALTITUDE"):
            cur.second = _num(s.split()[-1])
        elif up.startswith("FLAGS"):
            parts = s.split()
            cur.flags = int(_num(parts[1])) if len(parts) > 1 else 0
        elif up.startswith("LAYER"):
            parts = s.split()
            cur.layer = int(_num(parts[1])) if len(parts) > 1 else 0
        elif up.startswith("VERTICES"):
            mode = "verts"
        elif up.startswith("WALLS"):
            mode = "walls"
    return lvl


@dataclass
class ObjectInfo:
    player: tuple[float, float, float] | None = None  # x, z, yaw
    enemies: int = 0
    bosses: int = 0
    items: int = 0
    total: int = 0
    enemy_positions: list[tuple[float, float]] = field(default_factory=list)


_OBJ_RE = re.compile(
    r"CLASS:\s*(\w+)\s+DATA:\s*(-?\d+)\s+X:\s*(-?[\d.]+)\s+Y:\s*(-?[\d.]+)\s+Z:\s*(-?[\d.]+)"
    r"\s+PCH:\s*(-?[\d.]+)\s+YAW:\s*(-?[\d.]+)\s+ROL:\s*(-?[\d.]+)\s+DIFF:\s*(-?\d+)",
    re.I,
)


def parse_o(raw: bytes) -> ObjectInfo:
    text = raw.decode("latin1", "replace")
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    info = ObjectInfo()
    # Split into object blocks: each starts with CLASS:
    blocks = re.split(r"(?=CLASS:)", text)
    for b in blocks:
        m = _OBJ_RE.search(b)
        if not m:
            continue
        cls = m.group(1).upper()
        x, z, yaw = _num(m.group(3)), _num(m.group(5)), _num(m.group(7))
        info.total += 1
        logics = {l.upper() for l in re.findall(r"(?:LOGIC|TYPE):\s*(\w+)", b, re.I)}
        if "PLAYER" in logics:
            info.player = (x, z, yaw)
        elif logics & ENEMY_LOGICS:
            info.enemies += 1
            info.enemy_positions.append((x, z))
            if logics & BOSS_LOGICS:
                info.bosses += 1
        elif cls in ("FRAME", "SPRITE") and logics & {"ITEM", "SHIELD", "ENERGY", "BATTERY", "MEDKIT", "LIFE", "REVIVE", "SUPERCHARGE", "GOGGLES", "CLEATS", "MASK", "PLANS", "PHRIK", "NAVA", "DATATAPE", "DT_WEAPON", "CODE1", "CODE2", "CODE3", "CODE4", "CODE5", "CODE6", "CODE7", "CODE8", "CODE9", "RED", "BLUE", "YELLOW"}:
            info.items += 1
    return info


def parse_jedi_lvl(raw: bytes) -> list[tuple[str, str]]:
    """Return [(display name, level file stem), ...] from JEDI.LVL."""
    out = []
    text = raw.decode("latin1", "replace")
    for line in text.splitlines()[1:]:
        s = line.strip()
        if not s or s.startswith("//") or "," not in s:
            continue
        parts = [p.strip() for p in s.split(",")]
        if len(parts) >= 2 and parts[1]:
            out.append((parts[0], parts[1].upper()))
    return out


_KV_RE = re.compile(r"^\s*([A-Za-z][A-Za-z0-9 ./'()-]{1,40}?)\s*:\s?(.*)$")


def parse_readme(text: str) -> dict[str, str]:
    """Pull the common 'Key : value' header block out of a Dark Forces readme."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    fields: dict[str, str] = {}
    last_key = None
    for line in text.splitlines():
        m = _KV_RE.match(line)
        if m and line[:1] not in " \t" and len(m.group(1).strip()) <= 30:
            key = m.group(1).strip().lower()
            val = m.group(2).strip()
            fields[key] = val
            last_key = key
            continue
        if last_key and line.startswith((" ", "\t")) and line.strip():
            fields[last_key] = (fields[last_key] + " " + line.strip()).strip()
            continue
        if not line.strip():
            last_key = None
    return fields


def read_zip_text(z: zipfile.ZipFile, name: str) -> str:
    try:
        return z.read(name).decode("latin1", "replace")
    except Exception:
        return ""
