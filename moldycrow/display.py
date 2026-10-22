"""Put The Force Engine's window on the monitor the agent chose, using Hyprland's IPC after launch.
Everywhere else (Windows, macOS, other Linux desktops) this is off and the game opens where TFE's own settings say."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from dataclasses import dataclass

TFE_CLASS = "theforceengine"


@dataclass
class Monitor:
    name: str
    width: int
    height: int
    x: int
    y: int
    description: str

    @property
    def label(self) -> str:
        wide = " ultrawide" if self.width / max(1, self.height) > 2.0 else ""
        return f"{self.name}  {self.width}x{self.height}{wide}  {self.description}".strip()


def available() -> bool:
    return bool(os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")) and shutil.which("hyprctl") is not None


def _hyprctl(*args: str, timeout: float = 3.0) -> str:
    if not available():
        return ""
    try:
        return subprocess.run(["hyprctl", *args], capture_output=True, text=True, timeout=timeout).stdout
    except Exception:  # noqa: BLE001
        return ""


def list_monitors() -> list[Monitor]:
    out = []
    try:
        for m in json.loads(_hyprctl("monitors", "-j") or "[]"):
            out.append(Monitor(m.get("name", "?"), int(m.get("width", 0)), int(m.get("height", 0)),
                               int(m.get("x", 0)), int(m.get("y", 0)), m.get("description", "")))
    except Exception:  # noqa: BLE001
        pass
    return out


def tfe_windows() -> list[dict]:
    try:
        return [c for c in json.loads(_hyprctl("clients", "-j") or "[]") if c.get("class") == TFE_CLASS]
    except Exception:  # noqa: BLE001
        return []


def dispatch(expr: str) -> str:
    return _hyprctl("dispatch", expr).strip()


def focused_monitor() -> str | None:
    try:
        return json.loads(_hyprctl("activeworkspace", "-j") or "{}").get("monitor")
    except Exception:  # noqa: BLE001
        return None


def apply_rule(monitor: str | None, mode: str) -> str:
    """Install a Hyprland window rule so the game window is created on the right monitor, in the right state.
    Rules added with `hyprctl eval` last until Hyprland reloads its config; we re-apply before every launch."""
    if mode == "leave":
        monitor = focused_monitor()
        if not monitor:
            return "leave: no rule"
        return "rule: " + _hyprctl("eval", f'hl.window_rule({{ match = {{ class = "^{TFE_CLASS}$" }}, monitor = "{monitor}" }})').strip()
    parts = [f'match = {{ class = "^{TFE_CLASS}$" }}']
    if monitor:
        parts.append(f'monitor = "{monitor}"')
    parts.append("fullscreen = " + ("true" if mode == "fullscreen" else "false"))
    return "rule: " + _hyprctl("eval", "hl.window_rule({ " + ", ".join(parts) + " })").strip()


def _monitor_id(name: str) -> int | None:
    try:
        for m in json.loads(_hyprctl("monitors", "-j") or "[]"):
            if m.get("name") == name:
                return int(m.get("id"))
    except Exception:  # noqa: BLE001
        pass
    return None


def _window(address: str) -> dict | None:
    for w in tfe_windows():
        if w.get("address") == address:
            return w
    return None


def place_window(address: str, monitor: str | None, mode: str) -> list[str]:
    """mode: 'fullscreen' | 'windowed' | 'leave'. Returns hyprctl replies for logging."""
    log = []
    sel = f'window = "address:{address}"'
    if monitor:
        w = _window(address)
        want_id = _monitor_id(monitor)
        if w is not None and want_id is not None and int(w.get("monitor", -1)) == want_id:
            log.append("move: already")
        else:
            log.append("move: " + dispatch(f'hl.dsp.window.move({{ monitor = "{monitor}", {sel} }})'))
            time.sleep(0.3)
    if mode in ("fullscreen", "windowed"):
        # Hyprland's fullscreen dispatcher toggles, so read the state and only flip when it differs.
        want = mode == "fullscreen"
        for attempt in range(3):
            w = _window(address)
            if w is None:
                break
            is_full = int(w.get("fullscreen", 0)) != 0
            if is_full == want:
                log.append(f"{mode}: already")
                break
            log.append(f"{mode}: " + dispatch(f'hl.dsp.window.fullscreen({{ mode = "fullscreen", {sel} }})'))
            time.sleep(0.4)
    if any(not entry.endswith("already") for entry in log):
        log.append("focus: " + dispatch(f'hl.dsp.focus({{ {sel} }})'))
    return log


def wait_and_place(known: set[str], monitor: str | None, mode: str, timeout: float = 25.0) -> list[str]:
    """Poll for a TFE window that wasn't there before launch, then place it."""
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout:
        for w in tfe_windows():
            addr = w.get("address", "")
            if addr and addr not in known:
                time.sleep(0.4)  # let SDL finish its initial fullscreen/resize dance
                return place_window(addr, monitor, mode)
        time.sleep(0.25)
    return ["timed out waiting for the Force Engine window"]
