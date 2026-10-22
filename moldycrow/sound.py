"""Dark Forces VOC sounds → WAV in a temp dir, played through QSoundEffect. Silent no-op when audio is unavailable."""
from __future__ import annotations

import struct
import wave
from pathlib import Path

from .df import Gob
from .paths import CACHE_DIR

CACHE = CACHE_DIR / "sfx"

# Cue name -> (sounds.gob VOC stem, volume). Swap these freely.
CUES = {
    "tick": ("BEEP-10", 0.18),
    "land": ("KEY", 0.55),
    "reveal": ("BEEP-01", 0.45),
    "play": ("DOOR2-1", 0.6),
    "complete": ("COMPLETE", 0.6),
    "rate": ("SWITCH1", 0.45),
    "open": ("ELEV1-1", 0.35),
    "click": ("SWITCH3", 0.35),
}


def voc_to_wav(voc: bytes) -> bytes | None:
    """Decode Creative Voice File blocks (types 1 and 9, 8-bit PCM) to a WAV byte string."""
    if not voc.startswith(b"Creative Voice File"):
        return None
    data_off = struct.unpack_from("<H", voc, 20)[0]
    p = data_off
    rate = None
    pcm = bytearray()
    while p < len(voc):
        t = voc[p]
        if t == 0:
            break
        size = voc[p + 1] | (voc[p + 2] << 8) | (voc[p + 3] << 16)
        body = voc[p + 4:p + 4 + size]
        if t == 1:
            fd, codec = body[0], body[1]
            if rate is None:
                rate = int(1000000 / (256 - fd))
            if codec == 0:
                pcm += body[2:]
        elif t == 2:
            pcm += body
        elif t == 9:
            sr, bits, ch, fmt = struct.unpack_from("<IBBH", body, 0)
            if rate is None:
                rate = sr
            if bits == 8 and ch == 1:
                pcm += body[12:]
        elif t == 8:
            pass
        p += 4 + size
    if not pcm or not rate:
        return None
    import io
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(1)
        w.setframerate(rate)
        w.writeframes(bytes(pcm))
    return buf.getvalue()


class Sfx:
    """Lazy loader: names like 'BEEP-10' map to sounds.gob entries."""

    def __init__(self, sounds_gob: Path | None, enabled: bool = True):
        self.enabled = enabled
        self.gob: Gob | None = None
        self.effects: dict[str, object] = {}
        self.volume = 0.5
        if sounds_gob and sounds_gob.exists():
            try:
                self.gob = Gob(sounds_gob.read_bytes())
            except Exception:  # noqa: BLE001
                self.gob = None

    def _wav_path(self, name: str) -> Path | None:
        if self.gob is None:
            return None
        CACHE.mkdir(parents=True, exist_ok=True)
        out = CACHE / f"{name}.wav"
        if out.exists():
            return out
        key = f"{name}.VOC"
        if key not in self.gob:
            return None
        wav = voc_to_wav(self.gob.read(key))
        if not wav:
            return None
        out.write_bytes(wav)
        return out

    def _effect(self, name: str):
        if name in self.effects:
            return self.effects[name]
        eff = None
        path = self._wav_path(name)
        if path:
            try:
                from PyQt6.QtCore import QUrl
                from PyQt6.QtMultimedia import QSoundEffect
                eff = QSoundEffect()
                eff.setSource(QUrl.fromLocalFile(str(path)))
                eff.setVolume(self.volume)
            except Exception:  # noqa: BLE001
                eff = None
        self.effects[name] = eff
        return eff

    def play(self, name: str, volume: float | None = None):
        if not self.enabled:
            return
        eff = self._effect(name)
        if eff is None:
            return
        try:
            eff.setVolume(self.volume if volume is None else volume)
            eff.play()
        except Exception:  # noqa: BLE001
            pass

    def cue(self, name: str):
        stem, vol = CUES.get(name, (None, 0.5))
        if stem:
            self.play(stem, vol)

    def preload(self, names: list[str]):
        for n in names:
            self._effect(n)

    def preload_cues(self):
        for stem, _ in CUES.values():
            self._effect(stem)
