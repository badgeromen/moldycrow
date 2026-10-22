"""Qt stylesheet for the Agent Menu skin: steel bevels, red bands, green-on-black displays."""

BG = "#3a3a3a"
PANEL = "#4a4a4a"
PANEL2 = "#2b2b2b"
BORDER = "#1e1e1e"
TEXT = "#d8d8d8"
MUTED = "#9a9a9a"
ACCENT = "#ff3434"
ACCENT_DARK = "#8b0000"
CYAN = "#3cff3c"
GREEN = "#3cff3c"
GREEN_DIM = "#1d8f1d"
GREEN_BG = "#02160a"
RED = "#ff3434"
AMBER = "#ffd23b"

STYLESHEET = f"""
* {{ font-family: "Inter", "Cantarell", "Noto Sans", sans-serif; font-size: 13px; }}
QMainWindow, QWidget#root {{ background: {BG}; color: {TEXT}; }}
QWidget {{ color: {TEXT}; }}
QLabel#muted {{ color: {MUTED}; }}
QLabel#green {{ color: {GREEN}; }}
QLabel#greendim {{ color: {GREEN_DIM}; }}
QLabel#chip {{ background: {PANEL2}; border: 1px solid {BORDER}; border-radius: 2px; padding: 2px 7px; color: {GREEN_DIM}; font-size: 11px; font-weight: 700; text-transform: uppercase; }}
QLabel#chipAccent {{ background: {ACCENT_DARK}; border: 1px solid #b01414; border-radius: 2px; padding: 2px 7px; color: #ffb0b0; font-size: 11px; font-weight: 800; }}
QLabel#chipGreen {{ background: {GREEN_BG}; border: 1px solid {GREEN_DIM}; border-radius: 2px; padding: 2px 7px; color: {GREEN}; font-size: 11px; font-weight: 800; }}
QLineEdit, QComboBox, QTextEdit, QPlainTextEdit {{
  background: {GREEN_BG}; border: 2px solid #232323; border-top-color: #151515; border-left-color: #151515;
  border-bottom-color: #6a6a6a; border-right-color: #6a6a6a; padding: 5px 8px; color: {GREEN};
  selection-background-color: {GREEN_DIM}; selection-color: #000;
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{ border-bottom-color: {GREEN}; border-right-color: {GREEN}; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{ background: {GREEN_BG}; color: {GREEN}; border: 1px solid {GREEN_DIM}; selection-background-color: {GREEN_DIM}; selection-color: #000; }}
QPushButton {{
  background: {PANEL}; border: 2px solid; border-top-color: #8f8f8f; border-left-color: #8f8f8f;
  border-bottom-color: #2e2e2e; border-right-color: #2e2e2e; padding: 6px 12px; color: {GREEN}; font-weight: 700;
}}
QPushButton:hover {{ color: #a8ffa8; }}
QPushButton:pressed {{ border-top-color: #2e2e2e; border-left-color: #2e2e2e; border-bottom-color: #8f8f8f; border-right-color: #8f8f8f; }}
QPushButton:disabled {{ color: #6a6a6a; }}
QCheckBox {{ spacing: 8px; font-weight: 700; color: {GREEN}; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border: 2px solid; border-top-color: #151515; border-left-color: #151515; border-bottom-color: #6a6a6a; border-right-color: #6a6a6a; background: {GREEN_BG}; }}
QCheckBox::indicator:checked {{ background: {GREEN}; }}
QTreeWidget {{ background: {GREEN_BG}; border: none; color: {GREEN}; alternate-background-color: #041d0e; outline: 0; }}
QTreeWidget::item {{ padding: 4px 4px; }}
QTreeWidget::item:selected {{ background: {GREEN_DIM}; color: #000; }}
QTreeWidget::item:hover {{ background: #0b3a18; }}
QHeaderView::section {{ background: {PANEL}; color: {GREEN}; padding: 5px; border: 1px solid #2e2e2e; border-top-color: #8f8f8f; border-left-color: #8f8f8f; font-weight: 800; font-size: 11px; text-transform: uppercase; }}
QTabWidget::pane {{ border: 2px solid; border-top-color: #8f8f8f; border-left-color: #8f8f8f; border-bottom-color: #2e2e2e; border-right-color: #2e2e2e; background: {PANEL}; top: -1px; }}
QTabBar::tab {{ background: {PANEL2}; color: {MUTED}; padding: 7px 16px; border: 1px solid #1e1e1e; font-weight: 800; text-transform: uppercase; }}
QTabBar::tab:selected {{ background: {PANEL}; color: {GREEN}; border-bottom: none; }}
QSplitter::handle {{ background: {BG}; width: 8px; }}
QScrollBar:vertical {{ background: {PANEL2}; width: 12px; margin: 0; }}
QScrollBar::handle:vertical {{ background: {PANEL}; border: 1px solid #8f8f8f; border-bottom-color: #2e2e2e; border-right-color: #2e2e2e; min-height: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar:horizontal {{ background: {PANEL2}; height: 12px; }}
QScrollBar::handle:horizontal {{ background: {PANEL}; border: 1px solid #8f8f8f; min-width: 30px; }}
QProgressBar {{ background: {GREEN_BG}; border: 2px solid #232323; text-align: center; color: {GREEN}; font-weight: 700; }}
QProgressBar::chunk {{ background: {GREEN_DIM}; }}
QToolTip {{ background: {PANEL2}; color: {GREEN}; border: 1px solid {GREEN_DIM}; padding: 4px; }}
QMenu {{ background: {PANEL2}; border: 1px solid #8f8f8f; }}
QMenu::item:selected {{ background: {GREEN_DIM}; color: #000; }}
"""
