"""Per-OS locations: Moldy Crow's own data and cache, The Force Engine's data folder, binary, and Mods folders.

Where The Force Engine looks (from its source, TFE_FileSystem/paths*.cpp):
  settings.ini   Linux  ~/.local/share/TheForceEngine/   (or $TFE_DATA_HOME)
                 macOS  ~/Library/Application Support/TheForceEngine/
                 Win    Documents\\TheForceEngine\\       (or OneDrive\\Documents\\TheForceEngine\\)
                 any    next to the executable for a portable install
  -u<mod.zip>    <program dir>/Mods/, <program data>/Mods/, <game install>/Mods/
                 program dir is the launch directory on Linux and the executable's folder elsewhere.
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

WINDOWS = sys.platform == "win32"
MACOS = sys.platform == "darwin"
LINUX = not WINDOWS and not MACOS
HOME = Path.home()


def _env_path(name: str) -> Path | None:
    v = os.environ.get(name, "").strip()
    return Path(v).expanduser() if v else None


if WINDOWS:
    CACHE_DIR = (_env_path("LOCALAPPDATA") or HOME / "AppData" / "Local") / "moldycrow" / "cache"
    STATE_DIR = (_env_path("APPDATA") or HOME / "AppData" / "Roaming") / "moldycrow"
elif MACOS:
    CACHE_DIR = HOME / "Library" / "Caches" / "moldycrow"
    STATE_DIR = HOME / "Library" / "Application Support" / "moldycrow"
else:
    CACHE_DIR = (_env_path("XDG_CACHE_HOME") or HOME / ".cache") / "moldycrow"
    STATE_DIR = (_env_path("XDG_DATA_HOME") or HOME / ".local" / "share") / "moldycrow"


# ---------- The Force Engine binary ----------

def _app_bundle_exe(p: Path) -> Path | None:
    """macOS: a .app bundle -> the executable inside Contents/MacOS."""
    macos = p / "Contents" / "MacOS"
    if macos.is_dir():
        for f in sorted(macos.iterdir()):
            if f.is_file() and os.access(f, os.X_OK):
                return f
    return None


def resolve_tfe(p: str | Path | None) -> Path | None:
    if not p:
        return None
    p = Path(p).expanduser()
    if p.suffix.lower() == ".app":
        return _app_bundle_exe(p)
    if p.is_file():
        return p
    found = shutil.which(str(p))
    return Path(found) if found else None


def find_tfe(saved: str | None = None) -> Path | None:
    """MOLDYCROW_TFE, then the path the user picked, then PATH, then the usual install spots."""
    for cand in (os.environ.get("MOLDYCROW_TFE"), saved):
        exe = resolve_tfe(cand)
        if exe:
            return exe
    for name in ("theforceengine", "TheForceEngine", "theforceengine_osx"):
        found = shutil.which(name)
        if found:
            return Path(found)
    cands: list[Path] = []
    if WINDOWS:
        for root in (os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)"),
                     os.environ.get("LOCALAPPDATA") and str(Path(os.environ["LOCALAPPDATA"]) / "Programs")):
            if root:
                cands += [Path(root) / "TheForceEngine" / "TheForceEngine.exe",
                          Path(root) / "The Force Engine" / "TheForceEngine.exe"]
        cands += [HOME / "TheForceEngine" / "TheForceEngine.exe", HOME / "Desktop" / "TheForceEngine" / "TheForceEngine.exe",
                  Path("C:/TheForceEngine/TheForceEngine.exe"), Path("C:/Games/TheForceEngine/TheForceEngine.exe")]
    elif MACOS:
        for root in (Path("/Applications"), HOME / "Applications"):
            cands += [root / "TheForceEngine.app", root / "The Force Engine.app"]
    for c in cands:
        exe = resolve_tfe(c)
        if exe:
            return exe
    return None


def launch_dir(tfe: Path | None, mods_dir: Path | None) -> Path:
    """Working directory for the launch. On Linux TFE treats it as its program dir and searches <cwd>/Mods/,
    so the mods folder's parent works when the folder is called mods/Mods. Elsewhere TFE uses its own folder."""
    if LINUX:
        if mods_dir and mods_dir.name.lower() == "mods":
            return mods_dir.parent
        return HOME
    return tfe.parent if tfe else HOME


# ---------- The Force Engine data ----------

def tfe_settings_file(tfe: Path | None = None) -> Path | None:
    cands: list[Path] = []
    if tfe:
        cands.append(tfe.parent / "settings.ini")  # portable install
    tdh = _env_path("TFE_DATA_HOME")
    if tdh and not WINDOWS:
        cands.append(tdh / "settings.ini")
    if WINDOWS:
        docs = [HOME / "Documents", HOME / "OneDrive" / "Documents"]
        od = _env_path("OneDrive")
        if od:
            docs.append(od / "Documents")
        cands += [d / "TheForceEngine" / "settings.ini" for d in docs]
    elif MACOS:
        cands.append(HOME / "Library" / "Application Support" / "TheForceEngine" / "settings.ini")
    else:
        cands.append(HOME / ".local" / "share" / "TheForceEngine" / "settings.ini")
    for c in cands:
        if c.is_file():
            return c
    return None


def tfe_mod_dirs(tfe: Path | None, game_dir: Path | None) -> list[Path]:
    """Folders The Force Engine searches for -u<mod.zip>, most likely first."""
    out: list[Path] = []
    if tfe and not LINUX:
        out.append(tfe.parent / "Mods")
    if WINDOWS:
        out.append((_env_path("ProgramData") or Path("C:/ProgramData")) / "TheForceEngine" / "Mods")
    elif MACOS:
        out += [HOME / "Library" / "Application Support" / "TheForceEngine" / "Mods",
                Path("/Library/Application Support/TheForceEngine/Mods")]
    else:
        out += [(_env_path("TFE_DATA_HOME") or HOME / ".local" / "share" / "TheForceEngine") / "Mods",
                Path("/usr/local/share/TheForceEngine/Mods"), Path("/usr/share/TheForceEngine/Mods")]
    if game_dir:
        out.append(game_dir / "Mods")
    return out


def _same(a: Path, b: Path) -> bool:
    try:
        return os.path.samefile(a, b)
    except OSError:
        return os.path.normcase(str(a.resolve())) == os.path.normcase(str(b.resolve()))


def tfe_can_see(mods_dir: Path, tfe: Path | None, game_dir: Path | None) -> bool:
    if LINUX and mods_dir.name.lower() == "mods":
        return True  # launched from its parent, see launch_dir
    return any(_same(mods_dir, d) for d in tfe_mod_dirs(tfe, game_dir) if d.exists())


def default_mods_dir(saved: str | None, tfe: Path | None, game_dir: Path | None) -> Path | None:
    """MOLDYCROW_MODS, the folder the user picked, ~/mods, then whichever Force Engine Mods folder holds zips."""
    for cand in (_env_path("MOLDYCROW_MODS"), Path(saved) if saved else None, HOME / "mods"):
        if cand and cand.is_dir():
            return cand
    for d in tfe_mod_dirs(tfe, game_dir):
        try:
            if d.is_dir() and any(d.glob("*.zip")):
                return d
        except OSError:
            pass
    return None
