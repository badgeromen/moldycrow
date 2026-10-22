"""AGENT MENU dialog: pick, create, rename, or remove agent profiles."""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QLineEdit, QLabel, QInputDialog, QMessageBox

from .library import Agents
from .dfwidgets import RedHeader, DFButton, GreenWell, SteelPanel, BitmapLabel, GREEN_DIM


class AgentDialog(QDialog):
    def __init__(self, current: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Agent Menu")
        self.setModal(True)
        self.chosen: str | None = None
        self.setStyleSheet("QDialog { background: #3a3a3a; }")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(8)
        lay.addWidget(RedHeader("AGENTS", 3))
        well = GreenWell()
        wl = QVBoxLayout(well)
        wl.setContentsMargins(4, 4, 4, 4)
        self.list = QListWidget()
        self.list.setStyleSheet("QListWidget { background: transparent; border: none; color: #3cff3c; font-size: 15px; font-weight: 700; }"
                                "QListWidget::item { padding: 6px; } QListWidget::item:selected { background: #1d8f1d; color: #000; }")
        self.list.itemDoubleClicked.connect(lambda _: self._select())
        wl.addWidget(self.list)
        lay.addWidget(well, 1)
        hint = BitmapLabel("EACH AGENT KEEPS THEIR OWN COMPLETED LIST AND RATINGS", 2, GREEN_DIM, Qt.AlignmentFlag.AlignHCenter)
        lay.addWidget(hint)
        row = QHBoxLayout()
        b_new = DFButton("NEW AGENT")
        b_new.clicked.connect(self._new)
        b_ren = DFButton("RENAME")
        b_ren.clicked.connect(self._rename)
        b_rm = DFButton("REMOVE AGENT")
        b_rm.clicked.connect(self._remove)
        b_ok = DFButton("SELECT AGENT", primary=True)
        b_ok.clicked.connect(self._select)
        b_cancel = DFButton("CANCEL")
        b_cancel.clicked.connect(self.reject)
        for b in (b_new, b_ren, b_rm):
            row.addWidget(b)
        row.addStretch(1)
        row.addWidget(b_ok)
        row.addWidget(b_cancel)
        lay.addLayout(row)
        self.resize(560, 420)
        self._reload(current)

    def _reload(self, select: str | None):
        self.list.clear()
        for n in Agents.names():
            self.list.addItem(n)
        if select:
            items = self.list.findItems(select, Qt.MatchFlag.MatchExactly)
            if items:
                self.list.setCurrentItem(items[0])
        if self.list.currentItem() is None and self.list.count():
            self.list.setCurrentRow(0)

    def _current_name(self) -> str | None:
        it = self.list.currentItem()
        return it.text() if it else None

    def _ask(self, title: str, label: str, default: str = "") -> str | None:
        text, ok = QInputDialog.getText(self, title, label, text=default)
        return text.strip() if ok and text.strip() else None

    def _new(self):
        name = self._ask("New agent", "Agent name:")
        if not name:
            return
        made = Agents.create(name)
        if made is None:
            QMessageBox.warning(self, "New agent", "That name is taken or not usable.")
            return
        self._reload(made)

    def _rename(self):
        cur = self._current_name()
        if not cur:
            return
        name = self._ask("Rename agent", "New name:", cur)
        if not name or name == cur:
            return
        made = Agents.rename(cur, name)
        if made is None:
            QMessageBox.warning(self, "Rename", "That name is taken or not usable.")
            return
        self._reload(made)

    def _remove(self):
        cur = self._current_name()
        if not cur:
            return
        if QMessageBox.question(self, "Remove agent", f"Remove agent {cur} and all their progress?") != QMessageBox.StandardButton.Yes:
            return
        if not Agents.remove(cur):
            QMessageBox.warning(self, "Remove agent", "You need at least one agent.")
            return
        self._reload(None)

    def _select(self):
        self.chosen = self._current_name()
        if self.chosen:
            self.accept()
