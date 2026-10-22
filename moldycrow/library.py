"""Mod index (cached scan of the mods folder) and per-mod play state."""
from __future__ import annotations

import configparser
import hashlib
import json
import re
import time
import zipfile
from dataclasses import dataclass, field, asdict
from pathlib import Path

from .df import Gob, parse_lev, parse_o, parse_jedi_lvl, parse_readme, read_zip_text
from . import paths
from .paths import CACHE_DIR, STATE_DIR

INDEX_FILE = CACHE_DIR / "index.json"
STATE_FILE = STATE_DIR / "state.json"          # legacy single-profile file (migrated on first run)
AGENTS_DIR = STATE_DIR / "agents"
PROFILE_FILE = STATE_DIR / "profile.json"
DEFAULT_AGENT = "Kyle Katarn"
INDEX_VERSION = 4


@dataclass
class LevelInfo:
    display: str            # name from JEDI.LVL
    stem: str               # e.g. SECBASE
    lev_file: str | None    # name inside the GOB, or None when the mod reuses a stock level
    o_file: str | None
    sectors: int = 0
    secrets: int = 0
    enemies: int = 0
    bosses: int = 0
    items: int = 0
    has_player: bool = False


@dataclass
class ModInfo:
    file: str               # zip basename
    path: str
    size: int
    mtime: float
    gob: str                # GOB name inside the zip
    title: str
    author: str = ""
    description: str = ""
    readme_name: str = ""
    levels: list[LevelInfo] = field(default_factory=list)
    images: list[str] = field(default_factory=list)
    has_briefing: bool = False
    has_cutscenes: bool = False
    error: str = ""
    dup_of: str = ""

    @property
    def key(self) -> str:
        return self.file

    @property
    def sectors(self) -> int:
        return sum(l.sectors for l in self.levels)

    @property
    def enemies(self) -> int:
        return sum(l.enemies for l in self.levels)

    @property
    def secrets(self) -> int:
        return sum(l.secrets for l in self.levels)

    @property
    def size_tag(self) -> str:
        s = self.sectors
        if s == 0:
            return "stock level"
        if s < 150:
            return "quick"
        if s < 500:
            return "medium"
        if s < 1200:
            return "big"
        return "epic"

    @property
    def readme(self) -> str:
        if not self.readme_name:
            return ""
        try:
            with zipfile.ZipFile(self.path) as z:
                return read_zip_text(z, self.readme_name).replace("\r\n", "\n").replace("\r", "\n")
        except Exception as ex:  # noqa: BLE001
            return f"(could not read readme: {ex})"


_VERSION_TAIL = re.compile(
    r"[\s,(-]*\b(?:version|ver\.?|v)\s*\.?\s*\d[\d.]*[a-z]?\)?\s*$", re.I)
_DATE_TAIL = re.compile(r"[\s,(-]*\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+(?:\d{1,2},?\s+)?\d{4}\)?\s*$", re.I)
_PAREN_VERSION = re.compile(r"\s*\((?:version|ver\.?|v)\s*\.?\s*\d[^)]*\)\s*$", re.I)
_RELEASE_TAIL = re.compile(r"\s*[-–]+\s*\d+(?:st|nd|rd|th)\s+release.*$", re.I)


def _clean_title(t: str) -> str:
    t = re.sub(r"\s+", " ", t).strip(" \t-=*")
    for _ in range(2):
        t = _PAREN_VERSION.sub("", t)
        t = _RELEASE_TAIL.sub("", t)
        t = _DATE_TAIL.sub("", t)
        t = _VERSION_TAIL.sub("", t)
    return t.strip(" \t-=*,(")


def _pick_title(fields: dict[str, str], jedi: list[tuple[str, str]], stem: str) -> str:
    t = fields.get("title", "")
    if t and not t.lower().startswith("filename") and len(t) < 90:
        return _clean_title(t)
    if jedi and jedi[0][0]:
        return _clean_title(jedi[0][0])
    return stem.replace("_modern", "").replace("_", " ").title()


def scan_one(path: Path) -> ModInfo:
    info = ModInfo(file=path.name, path=str(path), size=path.stat().st_size,
                   mtime=path.stat().st_mtime, gob="", title=path.stem)
    try:
        z = zipfile.ZipFile(path)
    except Exception as ex:  # noqa: BLE001
        info.error = f"bad zip: {ex}"
        return info
    names = z.namelist()
    gobs = [n for n in names if n.lower().endswith(".gob")]
    info.images = [n for n in names if re.search(r"\.(jpe?g|png|gif|bmp|webp)$", n, re.I)]
    info.has_briefing = any(n.lower().endswith("dfbrief.lfd") for n in names)
    info.has_cutscenes = any(n.lower().endswith(".lfd") and not n.lower().endswith("dfbrief.lfd") for n in names)
    # Readme: prefer .txt then .doc, largest wins among candidates that look like headers
    texts = [n for n in names if re.search(r"\.(txt|doc|nfo)$", n, re.I) and "/" not in n.strip("/")]
    fields: dict[str, str] = {}
    for t in sorted(texts, key=lambda n: (not n.lower().endswith(".txt"), n)):
        f = parse_readme(read_zip_text(z, t))
        if "title" in f or "author" in f or "description" in f:
            fields = f
            info.readme_name = t
            break
    if not info.readme_name and texts:
        info.readme_name = texts[0]
        fields = parse_readme(read_zip_text(z, texts[0]))
    if not gobs:
        info.error = "no GOB inside zip"
        info.title = _pick_title(fields, [], path.stem)
        return info
    info.gob = gobs[0]
    try:
        gob = Gob(z.read(info.gob))
    except Exception as ex:  # noqa: BLE001
        info.error = f"bad GOB: {ex}"
        info.title = _pick_title(fields, [], path.stem)
        return info
    jedi = parse_jedi_lvl(gob.read("JEDI.LVL")) if "JEDI.LVL" in gob else []
    if not jedi:
        jedi = [(n[:-4].title(), n[:-4]) for n in gob.names("LEV")]
    info.title = _pick_title(fields, jedi, path.stem)
    info.author = _clean_title(fields.get("author", fields.get("authors", "")))
    info.description = fields.get("description", "").strip()
    for display, stem in jedi:
        lev_name = f"{stem}.LEV" if f"{stem}.LEV" in gob else None
        o_name = f"{stem}.O" if f"{stem}.O" in gob else None
        li = LevelInfo(display=display or stem.title(), stem=stem, lev_file=lev_name, o_file=o_name)
        if lev_name:
            try:
                lev = parse_lev(gob.read(lev_name))
                li.sectors = len(lev.sectors)
                li.secrets = lev.secrets
                if not info.author and lev.author:
                    info.author = lev.author
            except Exception as ex:  # noqa: BLE001
                info.error = f"LEV parse: {ex}"
        if o_name:
            try:
                o = parse_o(gob.read(o_name))
                li.enemies, li.bosses, li.items, li.has_player = o.enemies, o.bosses, o.items, o.player is not None
            except Exception as ex:  # noqa: BLE001
                info.error = f"O parse: {ex}"
        info.levels.append(li)
    return info


def _dedupe(mods: list[ModInfo]) -> None:
    """Mark byte-identical copies (e.g. 'foo (1).zip') as duplicates of the shortest-named one."""
    by_sig: dict[tuple[str, int], list[ModInfo]] = {}
    for m in mods:
        by_sig.setdefault((m.gob.upper(), m.size), []).append(m)
    for group in by_sig.values():
        if len(group) < 2:
            continue
        group.sort(key=lambda m: (len(m.file), m.file))
        keep = group[0]
        for d in group[1:]:
            d.dup_of = keep.file


def load_index() -> dict:
    try:
        data = json.loads(INDEX_FILE.read_text())
        if data.get("version") != INDEX_VERSION:
            return {}
        return data.get("mods", {})
    except Exception:  # noqa: BLE001
        return {}


def save_index(mods: list[ModInfo]) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"version": INDEX_VERSION, "mods": {m.file: asdict(m) for m in mods}}
    INDEX_FILE.write_text(json.dumps(payload))


def _from_dict(d: dict) -> ModInfo:
    levels = [LevelInfo(**l) for l in d.pop("levels", [])]
    m = ModInfo(**d)
    m.levels = levels
    return m


def scan_library(mods_dir: Path, progress=None) -> list[ModInfo]:
    """Scan the mods folder, reusing cached entries whose size/mtime are unchanged."""
    cached = load_index()
    files = sorted(p for p in mods_dir.glob("*.zip") if p.is_file())
    out: list[ModInfo] = []
    for i, p in enumerate(files):
        st = p.stat()
        c = cached.get(p.name)
        if c and c.get("size") == st.st_size and abs(c.get("mtime", 0) - st.st_mtime) < 1:
            m = _from_dict(dict(c))
            m.path = str(p)
        else:
            m = scan_one(p)
        m.dup_of = ""
        out.append(m)
        if progress:
            progress(i + 1, len(files), m.title)
    _dedupe(out)
    save_index(out)
    return out


# ---------- level geometry on demand ----------

def tfe_binary() -> Path | None:
    return paths.find_tfe(Profile.get("tfe_path"))


def set_tfe_binary(path: str):
    Profile.set("tfe_path", path)


def mods_dir() -> Path | None:
    return paths.default_mods_dir(Profile.get("mods_dir"), tfe_binary(), game_dir())


def set_mods_dir(path: str):
    Profile.set("mods_dir", path)


def game_dir() -> Path | None:
    p = stock_gob_path()
    return p.parent if p else None


def stock_gob_path() -> Path | None:
    try:
        settings = paths.tfe_settings_file(tfe_binary())
        if settings is None:
            return None
        cp = configparser.ConfigParser(interpolation=None, strict=False)
        cp.read(settings, encoding="utf-8")
        src = cp.get("Dark_Forces", "sourcePath", fallback="").strip('"')
        if src:
            for cand in ("dark.gob", "DARK.GOB"):
                p = Path(src) / cand
                if p.exists():
                    return p
    except Exception:  # noqa: BLE001
        pass
    return None


_stock_cache: dict[str, Gob] = {}


def load_level(mod: ModInfo, level: LevelInfo):
    """Return (Level, ObjectInfo|None). Falls back to the stock game's LEV when the mod ships none."""
    with zipfile.ZipFile(mod.path) as z:
        gob = Gob(z.read(mod.gob))
    lev = None
    if level.lev_file and level.lev_file in gob:
        lev = parse_lev(gob.read(level.lev_file))
    else:
        sp = stock_gob_path()
        if sp:
            sg = _stock_cache.get(str(sp))
            if sg is None:
                sg = Gob(sp.read_bytes())
                _stock_cache[str(sp)] = sg
            name = f"{level.stem}.LEV"
            if name in sg:
                lev = parse_lev(sg.read(name))
    objs = None
    if level.o_file and level.o_file in gob:
        objs = parse_o(gob.read(level.o_file))
    return lev, objs


# ---------- play state ----------

def _safe_agent_name(name: str) -> str:
    name = re.sub(r"[^A-Za-z0-9 _.-]", "", name).strip()
    return name[:24]


class Agents:
    """Agent profiles, one JSON file each under agents/. Mirrors the game's NEW AGENT / REMOVE AGENT."""

    @staticmethod
    def _migrate():
        AGENTS_DIR.mkdir(parents=True, exist_ok=True)
        if STATE_FILE.exists() and not any(AGENTS_DIR.glob("*.json")):
            STATE_FILE.replace(AGENTS_DIR / f"{DEFAULT_AGENT}.json")
        if not any(AGENTS_DIR.glob("*.json")):
            (AGENTS_DIR / f"{DEFAULT_AGENT}.json").write_text(json.dumps({"mods": {}, "now_playing": None, "history": []}))

    @classmethod
    def names(cls) -> list[str]:
        cls._migrate()
        return sorted((p.stem for p in AGENTS_DIR.glob("*.json")), key=str.lower)

    @classmethod
    def current(cls) -> str:
        cls._migrate()
        try:
            name = json.loads(PROFILE_FILE.read_text()).get("agent", "")
        except Exception:  # noqa: BLE001
            name = ""
        names = cls.names()
        if name in names:
            return name
        return names[0] if names else DEFAULT_AGENT

    @classmethod
    def set_current(cls, name: str):
        Profile.set("agent", name)

    @classmethod
    def path(cls, name: str) -> Path:
        return AGENTS_DIR / f"{name}.json"

    @classmethod
    def create(cls, name: str) -> str | None:
        name = _safe_agent_name(name)
        if not name or cls.path(name).exists():
            return None
        AGENTS_DIR.mkdir(parents=True, exist_ok=True)
        cls.path(name).write_text(json.dumps({"mods": {}, "now_playing": None, "history": []}))
        return name

    @classmethod
    def remove(cls, name: str) -> bool:
        if len(cls.names()) <= 1:
            return False
        p = cls.path(name)
        if p.exists():
            p.unlink()
        return True

    @classmethod
    def rename(cls, old: str, new: str) -> str | None:
        new = _safe_agent_name(new)
        if not new or cls.path(new).exists() or not cls.path(old).exists():
            return None
        cls.path(old).replace(cls.path(new))
        return new


class Profile:
    """Global (not per-agent) settings: current agent, display placement."""

    @staticmethod
    def load() -> dict:
        try:
            return json.loads(PROFILE_FILE.read_text())
        except Exception:  # noqa: BLE001
            return {}

    @staticmethod
    def save(data: dict):
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        PROFILE_FILE.write_text(json.dumps(data, indent=2))

    @classmethod
    def get(cls, key: str, default=None):
        return cls.load().get(key, default)

    @classmethod
    def set(cls, key: str, value):
        d = cls.load()
        d[key] = value
        cls.save(d)


class State:
    def __init__(self, agent: str | None = None):
        self.agent = agent or Agents.current()
        self.file = Agents.path(self.agent)
        self.data = {"mods": {}, "now_playing": None, "history": []}
        self.load()

    def load(self):
        try:
            self.data.update(json.loads(self.file.read_text()))
        except Exception:  # noqa: BLE001
            pass

    def save(self):
        self.file.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.file.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, indent=2))
        tmp.replace(self.file)

    def entry(self, key: str) -> dict:
        return self.data["mods"].setdefault(key, {"completed": False, "rating": 0, "notes": "", "pulls": 0})

    def is_completed(self, key: str) -> bool:
        return bool(self.data["mods"].get(key, {}).get("completed"))

    def rating(self, key: str) -> int:
        return int(self.data["mods"].get(key, {}).get("rating", 0))

    def set_completed(self, key: str, value: bool):
        e = self.entry(key)
        e["completed"] = value
        e["completed_at"] = time.time() if value else None
        if value and self.data.get("now_playing") == key:
            self.data["now_playing"] = None
        self.save()

    def set_rating(self, key: str, value: int):
        self.entry(key)["rating"] = max(0, min(5, int(value)))
        self.save()

    def set_notes(self, key: str, text: str):
        self.entry(key)["notes"] = text
        self.save()

    def map_hidden(self, key: str) -> bool:
        return bool(self.data["mods"].get(key, {}).get("map_hidden"))

    def set_map_hidden(self, key: str, hidden: bool):
        self.entry(key)["map_hidden"] = hidden
        self.save()

    def set_now_playing(self, key: str | None):
        self.data["now_playing"] = key
        if key:
            e = self.entry(key)
            e["played_at"] = time.time()
            self.data["history"] = ([key] + [h for h in self.data["history"] if h != key])[:50]
        self.save()

    def record_pull(self, key: str):
        self.entry(key)["pulls"] = self.entry(key).get("pulls", 0) + 1
        self.save()

    @property
    def now_playing(self) -> str | None:
        return self.data.get("now_playing")
