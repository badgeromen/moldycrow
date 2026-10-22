"""DISPLAY dialog: which monitor The Force Engine opens on, and fullscreen or windowed."""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem, QRadioButton, QButtonGroup, QLabel

from .display import list_monitors
from .library import Profile
from .dfwidgets import RedHeader, DFButton, GreenWell, BitmapLabel, GREEN_DIM

MODES = [("fullscreen", "FULLSCREEN on that monitor"), ("windowed", "WINDOWED on that monitor"), ("leave", "LEAVE IT where Hyprland puts it")]


def display_settings() -> tuple[str | None, str]:
    d = Profile.get("display", {}) or {}
    return d.get("monitor"), d.get("mode", "fullscreen")


class DisplayDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Display")
        self.setModal(True)
        self.setStyleSheet("QDialog { background: #3a3a3a; } QRadioButton { color: #3cff3c; font-weight: 700; spacing: 8px; }"
                           "QRadioButton::indicator { width: 14px; height: 14px; border: 2px solid #151515; border-radius: 8px; background: #02160a; }"
                           "QRadioButton::indicator:checked { background: #3cff3c; }")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(8)
        lay.addWidget(RedHeader("DISPLAY", 3))
        lay.addWidget(BitmapLabel("MONITOR FOR THE FORCE ENGINE", 2, GREEN_DIM))
        well = GreenWell()
        wl = QVBoxLayout(well)
        wl.setContentsMargins(4, 4, 4, 4)
        self.list = QListWidget()
        self.list.setStyleSheet("QListWidget { background: transparent; border: none; color: #3cff3c; font-size: 14px; font-weight: 700; }"
                                "QListWidget::item { padding: 6px; } QListWidget::item:selected { background: #1d8f1d; color: #000; }")
        wl.addWidget(self.list)
        lay.addWidget(well, 1)
        self.group = QButtonGroup(self)
        self.radios = {}
        for key, label in MODES:
            rb = QRadioButton(label)
            self.group.addButton(rb)
            self.radios[key] = rb
            lay.addWidget(rb)
        note = QLabel("Moldy Crow waits for the game window after BEGIN MISSION and moves it with Hyprland. "
                      "Widescreen rendering itself is a Force Engine setting (Graphics → Widescreen) and is already on.")
        note.setObjectName("greendim")
        note.setWordWrap(True)
        lay.addWidget(note)
        row = QHBoxLayout()
        row.addStretch(1)
        b_ok = DFButton("SAVE", primary=True)
        b_ok.clicked.connect(self._save)
        b_cancel = DFButton("CANCEL")
        b_cancel.clicked.connect(self.reject)
        row.addWidget(b_ok)
        row.addWidget(b_cancel)
        lay.addLayout(row)
        self.resize(640, 420)
        cur_mon, cur_mode = display_settings()
        self.monitors = list_monitors()
        for m in self.monitors:
            it = QListWidgetItem(m.label)
            it.setData(Qt.ItemDataRole.UserRole, m.name)
            self.list.addItem(it)
            if m.name == cur_mon:
                self.list.setCurrentItem(it)
        if self.list.currentItem() is None and self.list.count():
            # Default to the widest monitor.
            best = max(range(len(self.monitors)), key=lambda i: self.monitors[i].width)
            self.list.setCurrentRow(best)
        self.radios.get(cur_mode, self.radios["fullscreen"]).setChecked(True)

    def _save(self):
        it = self.list.currentItem()
        mon = it.data(Qt.ItemDataRole.UserRole) if it else None
        mode = next((k for k, rb in self.radios.items() if rb.isChecked()), "fullscreen")
        Profile.set("display", {"monitor": mon, "mode": mode})
        self.accept()
