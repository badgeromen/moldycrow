# Moldy Crow

Tracker and random mission picker for Dark Forces mods, built for The Force Engine. Runs on Windows, macOS and Linux.

## Download

**Don't use the green Code button, that's the source code.** Grab the file for your system:

| System | Download | How to run |
|---|---|---|
| **Windows** | [MoldyCrow-windows.exe](https://github.com/badgeromen/moldycrow/releases/latest/download/MoldyCrow-windows.exe) | Double-click it. If SmartScreen warns about an unknown publisher: **More info → Run anyway**. |
| **Mac (M1/M2/M3/M4)** | [MoldyCrow-macos-apple-silicon.zip](https://github.com/badgeromen/moldycrow/releases/latest/download/MoldyCrow-macos-apple-silicon.zip) | Unzip, then **right-click MoldyCrow.app → Open** the first time (the app isn't signed). |
| **Mac (Intel)** | [MoldyCrow-macos-intel.zip](https://github.com/badgeromen/moldycrow/releases/latest/download/MoldyCrow-macos-intel.zip) | Same as above. |
| **Linux** | [MoldyCrow-linux.tar.gz](https://github.com/badgeromen/moldycrow/releases/latest/download/MoldyCrow-linux.tar.gz) | Extract and run `MoldyCrow/MoldyCrow`. |

No install and no internet needed after the download. You also need [The Force Engine](https://theforceengine.github.io) set up with your own copy of Dark Forces.

Styled after the game's own Agent Menu. At startup it reads art straight from your Dark Forces install
(the path The Force Engine is configured with): the 8px menu font from `menu.lfd`, the PDA bezel, the
starfield from `darklogo.lfd`, and UI sounds from `sounds.gob`. No game assets are stored in this repo;
without the base game the app falls back to plain drawing and stays silent.

- Check off completed missions, rate them 1–5 stars, keep notes
- **Random Mission**: a slot-reel picks the next mission from the unplayed pool, reveals it with its map and stats, then launches it
- Search the list to find a mission someone suggested, mark it done without the random flow
- **Spoiler-free by default**: the level map stays classified until you mark the mission completed (a reveal button exists if you really want it)
- **PDA automap**: the level drawn as green vectors on black inside the real PDA frame, rendered straight from the LEV geometry inside each mod's GOB: walls, doors, secret sectors, floor height shading, hostiles, and your start position
- Multi-level campaigns get a level picker; mods that only replace objects on a stock level borrow geometry from the game's own `dark.gob`

## Run from source

```
pip install .            # installs the `moldycrow` command (needs Python 3.9+ and PyQt6)
python3 -m moldycrow     # or run straight from this folder
```

## First run

- **Mods folder**: Moldy Crow first checks `MOLDYCROW_MODS`, then `~/mods`, then The Force Engine's own Mods folders. If none of those has zips, it asks you to pick a folder. Change it any time with **MODS FOLDER**.
  The Force Engine only loads `-u<mod>.zip` from its own Mods folders, so put your zips in one of them:
  - Windows: `Mods\` next to `TheForceEngine.exe`
  - macOS: `~/Library/Application Support/TheForceEngine/Mods/`
  - Linux: `~/.local/share/TheForceEngine/Mods/`, or any folder named `mods` (Moldy Crow launches the game from its parent)
  - any OS: `Mods/` inside your Dark Forces install
- **The Force Engine**: found on PATH, in the usual install spots (`Program Files`, `/Applications`), or from `MOLDYCROW_TFE`. If it isn't found, Moldy Crow asks for it the first time you hit BEGIN MISSION.
- **Game art and sounds** come from the Dark Forces folder set in The Force Engine's `settings.ini`. That file is read from wherever The Force Engine keeps it on your system, including portable installs.

## Where things live

| What | Linux | macOS | Windows |
|---|---|---|---|
| Play state (agents, completed, ratings, notes) | `~/.local/share/moldycrow/` | `~/Library/Application Support/moldycrow/` | `%APPDATA%\moldycrow\` |
| Scan, art and sound cache | `~/.cache/moldycrow/` | `~/Library/Caches/moldycrow/` | `%LOCALAPPDATA%\moldycrow\cache\` |

Launching runs `theforceengine -gDark -skip_load_delay -u<zip>`.

**DISPLAY** (choose which monitor the game opens on, fullscreen or windowed) only works on Hyprland and is hidden everywhere else. On other systems, set fullscreen and the display in The Force Engine's own settings.

## Releasing

Push a version tag and GitHub Actions builds Windows, macOS and Linux zips and attaches them to a release:

```
git tag v0.1.0
git push origin v0.1.0
```

## Sounds

Cues live in `moldycrow/sound.py` (`CUES`): reel tick, lock-in, reveal, begin mission, mission complete, rating. Toggle with the SFX button; the choice is remembered.

## Keys

`Ctrl+F` search · `F5` / `Ctrl+R` random pull · in the pull: `Space` spin again, `Enter` play, `Esc` close · double-click a row to launch it

## License

GPL-3.0. See [LICENSE](LICENSE). Dark Forces and its assets belong to their owners; none are included here.
