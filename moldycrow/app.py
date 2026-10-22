"""Moldy Crow main window, styled after the Dark Forces Agent Menu."""
from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QProcess, QUrl
from PyQt6.QtGui import QKeySequence, QShortcut, QColor, QDesktopServices
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
                             QComboBox, QSplitter, QTreeWidget, QTreeWidgetItem, QTabWidget, QPlainTextEdit,
                             QTextEdit, QCheckBox, QProgressBar, QMessageBox, QHeaderView, QAbstractItemView,
                             QStackedWidget, QSizePolicy, QFileDialog)

from .library import (ModInfo, State, Agents, scan_library, load_level, stock_gob_path, game_dir,
                      mods_dir, set_mods_dir, tfe_binary, set_tfe_binary)
from . import paths
from .agents_ui import AgentDialog
from .display_ui import DisplayDialog, display_settings
from .display import tfe_windows, wait_and_place, apply_rule, available as placement_available
from .mapview import MapView
from .pull import PullOverlay, MapCover
from .theme import STYLESHEET, MUTED, GREEN, GREEN_DIM, AMBER, RED
from .widgets import StarRating, ChipRow
from .assets import Art
from .dfwidgets import BitmapLabel, DFButton, RedHeader, SteelPanel, GreenWell, PdaFrame, GREEN as QGREEN, GREEN_DIM as QGREEN_DIM
from .sound import Sfx

COL_DONE, COL_TITLE, COL_LEVELS, COL_SIZE, COL_ENEMIES, COL_RATING = range(6)


class Placer(QThread):
    """After launch: wait for the Force Engine window and put it where the agent wants it."""
    done = pyqtSignal(list)

    def __init__(self, known: set[str], monitor: str | None, mode: str, parent=None):
        super().__init__(parent)
        self.known, self.monitor, self.mode = known, monitor, mode

    def run(self):
        self.done.emit(wait_and_place(self.known, self.monitor, self.mode))


class Indexer(QThread):
    progress = pyqtSignal(int, int, str)
    done = pyqtSignal(list)

    def __init__(self, mods_dir: Path, parent=None):
        super().__init__(parent)
        self.mods_dir = mods_dir

    def run(self):
        mods = scan_library(self.mods_dir, progress=lambda i, n, t: self.progress.emit(i, n, t))
        self.done.emit(mods)


class ModItem(QTreeWidgetItem):
    def __lt__(self, other):
        col = self.treeWidget().sortColumn()
        a = self.data(col, Qt.ItemDataRole.UserRole)
        b = other.data(col, Qt.ItemDataRole.UserRole)
        if a is None or b is None:
            return self.text(col).lower() < other.text(col).lower()
        return a < b


class DetailPanel(SteelPanel):
    completed_changed = pyqtSignal(str, bool)
    rating_changed = pyqtSignal(str, int)
    notes_changed = pyqtSignal(str, str)
    launch = pyqtSignal(object)
    now_playing = pyqtSignal(object)

    def __init__(self, state: State, sfx: Sfx, parent=None):
        super().__init__(parent)
        self.state = state
        self.sfx = sfx
        self.mod: ModInfo | None = None
        self._loading = False
        self.revealed: set[str] = set()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(6)
        self.header = RedHeader("MISSION", 2)
        lay.addWidget(self.header)

        body = QVBoxLayout()
        body.setContentsMargins(8, 4, 8, 4)
        body.setSpacing(6)
        lay.addLayout(body, 1)

        self.title = BitmapLabel("SELECT A MISSION", 3, QGREEN)
        body.addWidget(self.title)
        self.author = QLabel("")
        self.author.setObjectName("greendim")
        self.author.setWordWrap(True)
        body.addWidget(self.author)
        self.chips = ChipRow()
        body.addWidget(self.chips)

        self.tabs = QTabWidget()
        body.addWidget(self.tabs, 1)

        # Map tab: PDA frame with a stack of cover/map inside
        map_w = QWidget()
        ml = QVBoxLayout(map_w)
        ml.setContentsMargins(8, 8, 8, 8)
        ml.setSpacing(6)
        top = QHBoxLayout()
        lvl = BitmapLabel("LEVEL", 2, QGREEN_DIM)
        top.addWidget(lvl)
        self.level_combo = QComboBox()
        self.level_combo.currentIndexChanged.connect(self._level_changed)
        top.addWidget(self.level_combo, 1)
        self.enemies_cb = QCheckBox("hostiles")
        self.enemies_cb.setChecked(True)
        self.enemies_cb.toggled.connect(lambda on: self.map.set_show_enemies(on))
        top.addWidget(self.enemies_cb)
        fit = DFButton("FIT")
        fit.clicked.connect(lambda: self.map.fit())
        top.addWidget(fit)
        ml.addLayout(top)
        self.map = MapView()
        self.cover = MapCover()
        self.map_stack = QStackedWidget()
        self.map_stack.addWidget(self.cover)
        self.map_stack.addWidget(self.map)
        self.pda = PdaFrame(self.map_stack)
        self.pda.setMinimumHeight(340)
        ml.addWidget(self.pda, 1)
        under = QHBoxLayout()
        self.map_note = QLabel("")
        self.map_note.setObjectName("greendim")
        self.map_note.setWordWrap(True)
        under.addWidget(self.map_note, 1)
        self.b_reveal = DFButton("REVEAL MAP (SPOILERS)")
        self.b_reveal.clicked.connect(self._toggle_map)
        under.addWidget(self.b_reveal)
        ml.addLayout(under)
        legend = QLabel(
            f"<span style='color:{GREEN}'>▬</span> wall &nbsp; <span style='color:{GREEN_DIM}'>▬</span> passage / ledge &nbsp; "
            f"<span style='color:{AMBER}'>▬</span> door &nbsp; <span style='color:{RED}'>▨</span> secret &nbsp; "
            f"<span style='color:#a8ffa8'>●</span> start &nbsp; <span style='color:{RED}'>•</span> hostile"
        )
        legend.setObjectName("greendim")
        ml.addWidget(legend)
        self.tabs.addTab(map_w, "PDA Map")

        self.readme = QPlainTextEdit()
        self.readme.setReadOnly(True)
        self.readme.setStyleSheet("font-family: monospace; font-size: 12px;")
        self.tabs.addTab(self.readme, "Readme")

        notes_w = QWidget()
        nl = QVBoxLayout(notes_w)
        nl.setContentsMargins(8, 8, 8, 8)
        self.notes = QTextEdit()
        self.notes.setPlaceholderText("Agent notes: where you got stuck, favorite bits, whether it crashed…")
        self.notes.textChanged.connect(self._notes_edited)
        nl.addWidget(self.notes)
        self.tabs.addTab(notes_w, "Agent Notes")

        # Footer
        row1 = QHBoxLayout()
        self.done_cb = QCheckBox("MISSION COMPLETE")
        self.done_cb.toggled.connect(self._done_toggled)
        row1.addWidget(self.done_cb)
        row1.addSpacing(18)
        self.stars = StarRating()
        self.stars.changed.connect(self._rating_changed)
        row1.addWidget(self.stars, 1)
        body.addLayout(row1)
        row2 = QHBoxLayout()
        self.b_launch = DFButton("BEGIN MISSION", primary=True)
        self.b_launch.clicked.connect(lambda: self.mod and self.launch.emit(self.mod))
        row2.addWidget(self.b_launch)
        self.b_now = DFButton("SET NOW PLAYING")
        self.b_now.clicked.connect(lambda: self.mod and self.now_playing.emit(self.mod))
        row2.addWidget(self.b_now)
        row2.addStretch(1)
        self.b_folder = DFButton("SHOW FILE")
        self.b_folder.clicked.connect(self._show_file)
        row2.addWidget(self.b_folder)
        body.addLayout(row2)
        self.setEnabled(False)

    # ----- populate -----
    def set_mod(self, mod: ModInfo | None):
        self._loading = True
        self.mod = mod
        self.setEnabled(mod is not None)
        if mod is None:
            self.title.setText("SELECT A MISSION")
            self.author.setText("")
            self.chips.set_chips([])
            self.level_combo.clear()
            self.map.set_level(None)
            self.map_stack.setCurrentWidget(self.cover)
            self.readme.setPlainText("")
            self.notes.setPlainText("")
            self.map_note.setText("")
            self._loading = False
            return
        self.title.setText(mod.title.upper())
        bits = []
        if mod.author:
            bits.append(f"by {mod.author}")
        bits.append(mod.file)
        self.author.setText("  ·  ".join(bits))
        chips = [(mod.size_tag.upper(), "chipAccent"), (f"{len(mod.levels)} level{'s' if len(mod.levels) != 1 else ''}", "chip")]
        if mod.sectors:
            chips.append((f"{mod.sectors:,} sectors", "chip"))
        if mod.enemies:
            chips.append((f"{mod.enemies} hostiles", "chip"))
        if mod.secrets:
            chips.append((f"{mod.secrets} secrets", "chip"))
        if mod.has_cutscenes:
            chips.append(("cutscenes", "chip"))
        if mod.has_briefing:
            chips.append(("briefing", "chip"))
        e = self.state.data["mods"].get(mod.file, {})
        if e.get("completed"):
            chips.append(("COMPLETE", "chipGreen"))
        if e.get("pulls"):
            chips.append((f"pulled ×{e['pulls']}", "chip"))
        self.chips.set_chips(chips)
        self.level_combo.blockSignals(True)
        self.level_combo.clear()
        for i, l in enumerate(mod.levels):
            extra = f"  ({l.sectors} sectors)" if l.sectors else "  (stock level)"
            self.level_combo.addItem(f"{i + 1}. {l.display}{extra}", i)
        self.level_combo.blockSignals(False)
        self.level_combo.setEnabled(len(mod.levels) > 1)
        self._level_changed(0)
        self.readme.setPlainText(mod.readme or "(no readme in this zip)")
        self.done_cb.setChecked(self.state.is_completed(mod.file))
        self.stars.setValue(self.state.rating(mod.file))
        self.notes.setPlainText(e.get("notes", ""))
        self._loading = False

    def map_allowed(self) -> bool:
        if self.mod is None:
            return False
        key = self.mod.file
        if key in self.revealed:
            return True
        return self.state.is_completed(key) and not self.state.map_hidden(key)

    def _toggle_map(self):
        if self.mod is None:
            return
        key = self.mod.file
        if self.map_allowed():
            # Hide: drop the session reveal; for completed missions remember the choice.
            self.revealed.discard(key)
            if self.state.is_completed(key):
                self.state.set_map_hidden(key, True)
        else:
            self.revealed.add(key)
            if self.state.is_completed(key):
                self.state.set_map_hidden(key, False)
        self.sfx.cue("click")
        self._level_changed(self.level_combo.currentIndex())

    # kept for callers/tests
    def _reveal_map(self):
        if self.mod is not None and not self.map_allowed():
            self._toggle_map()

    def _level_changed(self, idx: int):
        if self.mod is None or idx < 0 or idx >= len(self.mod.levels):
            self.map.set_level(None)
            self.map_stack.setCurrentWidget(self.cover)
            self.b_reveal.setVisible(False)
            return
        self.b_reveal.setVisible(True)
        if not self.map_allowed():
            self.map.set_level(None)
            self.map_stack.setCurrentWidget(self.cover)
            self.map_note.setText("")
            self.b_reveal.setText("REVEAL MAP (SPOILERS)")
            return
        self.b_reveal.setText("HIDE MAP")
        self.map_stack.setCurrentWidget(self.map)
        lv = self.mod.levels[idx]
        try:
            level, objs = load_level(self.mod, lv)
        except Exception as ex:  # noqa: BLE001
            self.map.set_level(None)
            self.map_note.setText(f"Could not read level: {ex}")
            return
        if level is None:
            self.map.set_level(None)
            self.map_note.setText(
                f"This mod only replaces objects on the stock level {lv.stem} and the base game's dark.gob "
                "was not found, so there is no geometry to draw.")
            return
        self.map.set_level(level, objs)
        self.map.set_show_enemies(self.enemies_cb.isChecked())
        note = []
        if not lv.lev_file:
            note.append(f"Geometry from the stock {lv.stem} level; this mod only changes objects.")
        if objs:
            note.append(f"{objs.enemies} hostiles on hard, {objs.bosses} bosses, {level.secrets} secret sectors.")
        note.append("Scroll to zoom, drag to pan, double-click to fit.")
        self.map_note.setText("  ".join(note))

    # ----- edits -----
    def _done_toggled(self, on: bool):
        if self._loading or self.mod is None:
            return
        self.completed_changed.emit(self.mod.file, on)
        if on:
            self.sfx.cue("complete")
            if self.stars.value() == 0:
                self.stars.hint.setText("← rate it!")
        self._level_changed(self.level_combo.currentIndex())

    def _rating_changed(self, v: int):
        if self._loading or self.mod is None:
            return
        self.sfx.cue("rate")
        self.rating_changed.emit(self.mod.file, v)

    def _notes_edited(self):
        if self._loading or self.mod is None:
            return
        self.notes_changed.emit(self.mod.file, self.notes.toPlainText())

    def _show_file(self):
        if self.mod:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(self.mod.path).parent)))


class MainWindow(QMainWindow):
    def __init__(self, mods_dir: Path):
        super().__init__()
        self.mods_dir = mods_dir
        self._warned_mods_dir = False
        self.setWindowTitle("Moldy Crow — Dark Forces")
        self.resize(1560, 940)
        self.state = State()
        self.mods: list[ModInfo] = []
        self.by_key: dict[str, ModInfo] = {}
        self.current_key: str | None = None
        base = stock_gob_path()
        self.sfx = Sfx(base.parent / "sounds.gob" if base else None,
                       enabled=bool(self.state.data.get("sfx", True)))
        self.sfx.preload_cues()
        self._build()
        self.overlay = PullOverlay(self, self.sfx)
        self.overlay.play.connect(self._pull_play)
        self.overlay.closed.connect(self._refresh_status)
        self.indexer = Indexer(mods_dir, self)
        self.indexer.progress.connect(self._progress)
        self.indexer.done.connect(self._indexed)
        self.indexer.start()

    # ----- UI -----
    def _build(self):
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        v = QVBoxLayout(root)
        v.setContentsMargins(10, 8, 10, 8)
        v.setSpacing(8)

        v.addWidget(RedHeader("MOLDY CROW", 3))

        top = QHBoxLayout()
        top.setSpacing(8)
        self.b_agent = DFButton(f"AGENT: {self.state.agent.upper()}")
        self.b_agent.setToolTip("Switch, create, rename, or remove agents")
        self.b_agent.clicked.connect(self._agent_menu)
        top.addWidget(self.b_agent)
        top.addSpacing(10)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search title, author, level, file…   (Ctrl+F)")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._refresh_list)
        top.addWidget(self.search, 1)
        self.filter = QComboBox()
        self.filter.addItems(["All", "Unplayed", "Completed", "Rated 4+", "Recently played", "Quick (<150 sectors)", "Big & epic"])
        self.filter.currentIndexChanged.connect(self._refresh_list)
        top.addWidget(self.filter)
        self.unplayed_only = QCheckBox("pull from unplayed only")
        self.unplayed_only.setChecked(True)
        top.addWidget(self.unplayed_only)
        self.b_display = DFButton("DISPLAY")
        self.b_display.setToolTip("Which monitor the game opens on, fullscreen or windowed")
        self.b_display.clicked.connect(self._display_menu)
        top.addWidget(self.b_display)
        self.b_display.setVisible(placement_available())  # monitor placement needs Hyprland
        self.b_mods = DFButton("MODS FOLDER")
        self.b_mods.setToolTip(str(self.mods_dir))
        self.b_mods.clicked.connect(self._pick_mods_dir)
        top.addWidget(self.b_mods)
        self.b_sfx = DFButton("SFX ON" if self.sfx.enabled else "SFX OFF")
        self.b_sfx.clicked.connect(self._toggle_sfx)
        top.addWidget(self.b_sfx)
        self.b_pull = DFButton("RANDOM MISSION", primary=True, scale=3)
        self.b_pull.clicked.connect(self.random_pull)
        self.b_pull.setEnabled(False)
        top.addWidget(self.b_pull)
        v.addLayout(top)

        # Now playing strip
        self.now_strip = SteelPanel()
        nl = QHBoxLayout(self.now_strip)
        nl.setContentsMargins(10, 6, 10, 6)
        nl.setSpacing(10)
        self.now_hdr = BitmapLabel("NOW PLAYING", 2, QColor("#ff3434"))
        nl.addWidget(self.now_hdr)
        self.now_title = BitmapLabel("", 2, QGREEN)
        self.now_title.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        nl.addWidget(self.now_title, 1)
        b_show = DFButton("SHOW")
        b_show.clicked.connect(lambda: self._select_key(self.state.now_playing))
        nl.addWidget(b_show)
        b_launch = DFButton("LAUNCH")
        b_launch.clicked.connect(lambda: self._launch_key(self.state.now_playing))
        nl.addWidget(b_launch)
        b_done = DFButton("MISSION COMPLETE", primary=True)
        b_done.clicked.connect(self._finish_now_playing)
        nl.addWidget(b_done)
        b_clear = DFButton("X")
        b_clear.setToolTip("Clear now playing")
        b_clear.clicked.connect(lambda: self._set_now_playing(None))
        nl.addWidget(b_clear)
        v.addWidget(self.now_strip)
        self.now_strip.hide()

        self.progress = QProgressBar()
        self.progress.setTextVisible(True)
        v.addWidget(self.progress)

        split = QSplitter(Qt.Orientation.Horizontal)
        v.addWidget(split, 1)
        left = SteelPanel()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(6, 6, 6, 6)
        ll.setSpacing(6)
        ll.addWidget(RedHeader("MISSIONS", 2))
        self.tree = QTreeWidget()
        self.tree.setColumnCount(6)
        self.tree.setHeaderLabels(["✓", "Mission", "Lvls", "Size", "Hostiles", "Rating"])
        self.tree.setRootIsDecorated(False)
        self.tree.setAlternatingRowColors(True)
        self.tree.setSortingEnabled(True)
        self.tree.sortByColumn(COL_TITLE, Qt.SortOrder.AscendingOrder)
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tree.setUniformRowHeights(True)
        hdr = self.tree.header()
        hdr.setSectionResizeMode(COL_TITLE, QHeaderView.ResizeMode.Stretch)
        for c in (COL_DONE, COL_LEVELS, COL_SIZE, COL_ENEMIES, COL_RATING):
            hdr.setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.currentItemChanged.connect(self._current_changed)
        self.tree.itemDoubleClicked.connect(lambda it, c: self._launch_key(it.data(0, Qt.ItemDataRole.UserRole + 1)))
        well = GreenWell()
        wl = QVBoxLayout(well)
        wl.setContentsMargins(3, 3, 3, 3)
        wl.addWidget(self.tree)
        ll.addWidget(well, 1)
        split.addWidget(left)
        self.detail = DetailPanel(self.state, self.sfx)
        self.detail.completed_changed.connect(self._set_completed)
        self.detail.rating_changed.connect(self._set_rating)
        self.detail.notes_changed.connect(self.state.set_notes)
        self.detail.launch.connect(self.launch_mod)
        self.detail.now_playing.connect(lambda m: self._set_now_playing(m.file))
        split.addWidget(self.detail)
        split.setStretchFactor(0, 4)
        split.setStretchFactor(1, 6)
        split.setSizes([620, 920])

        self.status = BitmapLabel("", 2, QGREEN_DIM)
        v.addWidget(self.status)

        QShortcut(QKeySequence("Ctrl+F"), self, activated=lambda: (self.search.setFocus(), self.search.selectAll()))
        QShortcut(QKeySequence("F5"), self, activated=self.random_pull)
        QShortcut(QKeySequence("Ctrl+R"), self, activated=self.random_pull)

    def _agent_menu(self):
        self.sfx.cue("click")
        dlg = AgentDialog(self.state.agent, self)
        if dlg.exec() and dlg.chosen:
            self._switch_agent(dlg.chosen)
        else:
            # The current agent may have been renamed or removed while the dialog was open.
            if not Agents.path(self.state.agent).exists():
                self._switch_agent(Agents.current())

    def _switch_agent(self, name: str):
        Agents.set_current(name)
        self.state = State(name)
        self.state.data.setdefault("sfx", self.sfx.enabled)
        self.detail.state = self.state
        self.detail.revealed.clear()
        self.b_agent.setText(f"AGENT: {name.upper()}")
        self._refresh_list()
        self._refresh_now_strip()
        self.detail.set_mod(self.by_key.get(self.current_key) if self.current_key else None)

    def _display_menu(self):
        self.sfx.cue("click")
        DisplayDialog(self).exec()

    def _pick_mods_dir(self):
        self.sfx.cue("click")
        picked = QFileDialog.getExistingDirectory(self, "Mods folder", str(self.mods_dir))
        if not picked or self.indexer.isRunning():
            return
        set_mods_dir(picked)
        self.mods_dir = Path(picked)
        self.b_mods.setToolTip(picked)
        self._warned_mods_dir = False
        self.b_pull.setEnabled(False)
        self.progress.show()
        self.indexer = Indexer(self.mods_dir, self)
        self.indexer.progress.connect(self._progress)
        self.indexer.done.connect(self._indexed)
        self.indexer.start()

    def _toggle_sfx(self):
        self.sfx.enabled = not self.sfx.enabled
        self.state.data["sfx"] = self.sfx.enabled
        self.state.save()
        self.b_sfx.setText("SFX ON" if self.sfx.enabled else "SFX OFF")
        self.sfx.cue("click")

    # ----- indexing -----
    def _progress(self, i, n, title):
        self.progress.setMaximum(n)
        self.progress.setValue(i)
        self.progress.setFormat(f"Reading missions… {i}/{n}  {title}")

    def _indexed(self, mods: list):
        self.mods = mods
        self.by_key = {m.file: m for m in mods}
        self.progress.hide()
        self.b_pull.setEnabled(True)
        self._refresh_list()
        self._refresh_now_strip()
        if self.tree.topLevelItemCount():
            self.tree.setCurrentItem(self.tree.topLevelItem(0))

    # ----- list -----
    def _visible_mods(self) -> list[ModInfo]:
        q = self.search.text().strip().lower()
        f = self.filter.currentText()
        out = []
        for m in self.mods:
            if m.dup_of:
                continue
            e = self.state.data["mods"].get(m.file, {})
            done = bool(e.get("completed"))
            if f == "Unplayed" and done:
                continue
            if f == "Completed" and not done:
                continue
            if f == "Rated 4+" and int(e.get("rating", 0)) < 4:
                continue
            if f == "Recently played" and not e.get("played_at"):
                continue
            if f.startswith("Quick") and not (0 < m.sectors < 150):
                continue
            if f.startswith("Big") and m.sectors < 500:
                continue
            if q:
                hay = " ".join([m.title, m.author, m.file, " ".join(l.display for l in m.levels), m.description]).lower()
                if all(tok in hay for tok in q.split()):
                    out.append(m)
            else:
                out.append(m)
        return out

    def _refresh_list(self):
        cur = self.tree.currentItem()
        cur_key = (cur.data(0, Qt.ItemDataRole.UserRole + 1) if cur else None) or self.current_key
        self.tree.setSortingEnabled(False)
        self.tree.clear()
        select_item = None
        for m in self._visible_mods():
            e = self.state.data["mods"].get(m.file, {})
            done = bool(e.get("completed"))
            rating = int(e.get("rating", 0))
            it = ModItem(["✓" if done else "", m.title, str(len(m.levels)), m.size_tag,
                          str(m.enemies) if m.enemies else "", "★" * rating])
            it.setData(0, Qt.ItemDataRole.UserRole + 1, m.file)
            it.setData(COL_DONE, Qt.ItemDataRole.UserRole, 1 if done else 0)
            it.setData(COL_TITLE, Qt.ItemDataRole.UserRole, m.title.lower())
            it.setData(COL_LEVELS, Qt.ItemDataRole.UserRole, len(m.levels))
            it.setData(COL_SIZE, Qt.ItemDataRole.UserRole, m.sectors)
            it.setData(COL_ENEMIES, Qt.ItemDataRole.UserRole, m.enemies)
            it.setData(COL_RATING, Qt.ItemDataRole.UserRole, rating)
            it.setForeground(COL_DONE, QColor(GREEN))
            it.setForeground(COL_RATING, QColor(AMBER))
            it.setForeground(COL_SIZE, QColor(GREEN_DIM))
            it.setForeground(COL_ENEMIES, QColor(GREEN_DIM))
            it.setForeground(COL_LEVELS, QColor(GREEN_DIM))
            it.setTextAlignment(COL_DONE, Qt.AlignmentFlag.AlignCenter)
            if done:
                it.setForeground(COL_TITLE, QColor(GREEN_DIM))
            if m.file == self.state.now_playing:
                it.setForeground(COL_TITLE, QColor(RED))
            it.setToolTip(COL_TITLE, f"{m.title}\n{m.file}\n" + ("\n".join(l.display for l in m.levels)))
            self.tree.addTopLevelItem(it)
            if m.file == cur_key:
                select_item = it
        self.tree.setSortingEnabled(True)
        if select_item:
            self.tree.setCurrentItem(select_item)
        self._refresh_status()

    def _refresh_status(self):
        total = sum(1 for m in self.mods if not m.dup_of)
        done = sum(1 for m in self.mods if not m.dup_of and self.state.is_completed(m.file))
        rated = sum(1 for m in self.mods if not m.dup_of and self.state.rating(m.file) > 0)
        shown = self.tree.topLevelItemCount()
        self.status.setText(f"{shown} SHOWN   {total} MISSIONS   {done} COMPLETE   {rated} RATED   {total - done} IN THE POOL")

    def _current_changed(self, cur, prev):
        key = cur.data(0, Qt.ItemDataRole.UserRole + 1) if cur else None
        if key:
            self.current_key = key
        self.detail.set_mod(self.by_key.get(key) if key else None)

    def _select_key(self, key: str | None):
        if not key:
            return
        for i in range(self.tree.topLevelItemCount()):
            it = self.tree.topLevelItem(i)
            if it.data(0, Qt.ItemDataRole.UserRole + 1) == key:
                self.tree.setCurrentItem(it)
                self.tree.scrollToItem(it)
                return
        self.filter.setCurrentIndex(0)
        self.search.clear()
        self._select_key(key)

    # ----- state edits -----
    def _set_completed(self, key: str, on: bool):
        self.state.set_completed(key, on)
        self._refresh_list()
        self._refresh_now_strip()
        self.detail.set_mod(self.by_key.get(key))

    def _set_rating(self, key: str, v: int):
        self.state.set_rating(key, v)
        self._refresh_list()

    def _set_now_playing(self, key: str | None):
        self.state.set_now_playing(key)
        self._refresh_now_strip()
        self._refresh_list()

    def _refresh_now_strip(self):
        key = self.state.now_playing
        m = self.by_key.get(key) if key else None
        if m is None:
            self.now_strip.hide()
            return
        self.now_title.setText(m.title.upper())
        self.now_strip.show()

    def _finish_now_playing(self):
        key = self.state.now_playing
        if not key:
            return
        self.state.set_completed(key, True)
        self.sfx.cue("complete")
        self._refresh_list()
        self._refresh_now_strip()
        self._select_key(key)
        self.detail.tabs.setCurrentIndex(0)
        self.detail.stars.hint.setText("← rate it!")

    # ----- launching -----
    def _launch_key(self, key: str | None):
        if key and key in self.by_key:
            self.launch_mod(self.by_key[key])

    def _ask_tfe(self) -> Path | None:
        QMessageBox.information(self, "Find The Force Engine",
                                "Moldy Crow could not find The Force Engine.\nPoint it at the program "
                                "(TheForceEngine.exe on Windows, TheForceEngine.app on macOS).")
        if paths.MACOS:
            picked = QFileDialog.getExistingDirectory(self, "The Force Engine app", "/Applications") \
                or QFileDialog.getOpenFileName(self, "The Force Engine", "/Applications")[0]
        else:
            filt = "The Force Engine (*.exe)" if paths.WINDOWS else "All files (*)"
            picked = QFileDialog.getOpenFileName(self, "The Force Engine", str(Path.home()), filt)[0]
        exe = paths.resolve_tfe(picked) if picked else None
        if exe:
            set_tfe_binary(picked)
        return exe

    def launch_mod(self, mod: ModInfo):
        tfe = tfe_binary() or self._ask_tfe()
        if tfe is None:
            return
        if not self._warned_mods_dir and not paths.tfe_can_see(self.mods_dir, tfe, game_dir()):
            self._warned_mods_dir = True
            where = "\n".join(f"  {d}" for d in paths.tfe_mod_dirs(tfe, game_dir())[:3])
            QMessageBox.warning(self, "Mods folder",
                                f"The Force Engine only loads mods from its own Mods folders, for example:\n{where}\n\n"
                                f"{self.mods_dir} is not one of them, so the game may start without the mod. "
                                "Move your zips into one of those folders and pick it from MODS FOLDER.")
        args = ["-gDark", "-skip_load_delay", f"-u{mod.file}"]
        placing = placement_available()
        known = {w.get("address", "") for w in tfe_windows()} if placing else set()
        mon, mode = display_settings()
        if placing:
            apply_rule(mon, mode)   # window is born on the right monitor; no visible move
        ok = QProcess.startDetached(str(tfe), args, str(paths.launch_dir(tfe, self.mods_dir)))
        if ok and placing and mode != "leave":  # silent fallback: only acts if the rule somehow didn't take
            self.placer = Placer(known, mon, mode, self)
            self.placer.done.connect(lambda log: None)
            self.placer.start()
        if not ok:
            QMessageBox.warning(self, "Launch failed",
                                f"Could not start {tfe}.\nSet MOLDYCROW_TFE to the Force Engine program if it lives elsewhere.")
            return
        self.sfx.cue("play")
        if self.state.now_playing != mod.file:
            self._set_now_playing(mod.file)
        self.status.setText(f"LAUNCHED THE FORCE ENGINE WITH {mod.file.upper()}")

    # ----- random pull -----
    def random_pull(self):
        if not self.mods or self.overlay.isVisible():
            return
        pool = [m for m in self.mods if not m.dup_of]
        if self.unplayed_only.isChecked():
            pool = [m for m in pool if not self.state.is_completed(m.file)]
        self.overlay.start(pool)

    def _pull_play(self, mod: ModInfo):
        self.state.record_pull(mod.file)
        self._set_now_playing(mod.file)
        self._select_key(mod.file)
        self.launch_mod(mod)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self.overlay.isVisible():
            self.overlay.setGeometry(self.rect())


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Moldy Crow")
    app.setStyleSheet(STYLESHEET)
    folder = mods_dir()
    if folder is None:
        QMessageBox.information(None, "Moldy Crow",
                                "Pick the folder that holds your Dark Forces mod zips.\n"
                                "Best choice: The Force Engine's own Mods folder, so the game can load them.")
        picked = QFileDialog.getExistingDirectory(None, "Mods folder", str(Path.home()))
        if not picked:
            return 1
        set_mods_dir(picked)
        folder = Path(picked)
    Art.get()
    w = MainWindow(folder)
    w.show()
    return app.exec()
