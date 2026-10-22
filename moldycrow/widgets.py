"""Small reusable widgets: star rating, chips, flow row."""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel

from .theme import AMBER as ACCENT, BORDER, MUTED


class StarRating(QWidget):
    changed = pyqtSignal(int)

    def __init__(self, value: int = 0, size: int = 26, parent=None):
        super().__init__(parent)
        self._value = value
        self._hover = 0
        self._size = size
        self.setMouseTracking(True)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)
        self.stars: list[QLabel] = []
        for i in range(5):
            l = QLabel("★")
            l.setStyleSheet(f"font-size: {size}px;")
            l.setCursor(Qt.CursorShape.PointingHandCursor)
            l.setMouseTracking(True)
            l.installEventFilter(self)
            l.setProperty("idx", i + 1)
            lay.addWidget(l)
            self.stars.append(l)
        self.hint = QLabel("")
        self.hint.setObjectName("muted")
        lay.addSpacing(8)
        lay.addWidget(self.hint)
        lay.addStretch(1)
        self._paint()

    def value(self) -> int:
        return self._value

    def setValue(self, v: int):
        self._value = max(0, min(5, v))
        self._paint()

    def _paint(self):
        show = self._hover or self._value
        for i, l in enumerate(self.stars):
            lit = (i + 1) <= show
            color = ACCENT if lit else "#5a5a5a"
            l.setStyleSheet(f"font-size: {self._size}px; color: {color};")
        labels = {0: "unrated", 1: "rough", 2: "meh", 3: "solid", 4: "great", 5: "legendary"}
        self.hint.setText(labels.get(show, ""))

    def eventFilter(self, obj, ev):
        from PyQt6.QtCore import QEvent
        if ev.type() == QEvent.Type.Enter:
            self._hover = obj.property("idx"); self._paint()
        elif ev.type() == QEvent.Type.Leave:
            self._hover = 0; self._paint()
        elif ev.type() == QEvent.Type.MouseButtonPress:
            idx = obj.property("idx")
            self._value = 0 if idx == self._value else idx
            self._hover = 0
            self._paint()
            self.changed.emit(self._value)
            return True
        return super().eventFilter(obj, ev)


def chip(text: str, kind: str = "chip") -> QLabel:
    l = QLabel(text)
    l.setObjectName(kind)
    return l


class ChipRow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.lay = QHBoxLayout(self)
        self.lay.setContentsMargins(0, 0, 0, 0)
        self.lay.setSpacing(6)
        self.lay.addStretch(1)

    def set_chips(self, items: list[tuple[str, str]]):
        while self.lay.count() > 1:
            it = self.lay.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        for i, (text, kind) in enumerate(items):
            self.lay.insertWidget(i, chip(text, kind))
