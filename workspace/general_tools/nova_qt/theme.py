"""
theme.py — Dark palette and stylesheet for Nova Qt app.
VS Code-inspired dark theme with Nova purple accent.
"""
from PyQt6.QtGui import QPalette, QColor
from PyQt6.QtCore import Qt

# ── Color tokens ───────────────────────────────────────────────────────────────
BG          = "#0a0a0f"
BG_ALT      = "#12121a"
BG_CARD     = "#16161c"
BG_INPUT    = "#0e0e14"
BORDER      = "#2a2a3a"
TEXT        = "#f0f0f0"
TEXT_DIM    = "#6b7280"
NOVA        = "#8f90ff"   # Nova purple
CLAUDE      = "#d97757"   # Claude orange
GEMINI      = "#4e86e4"   # Gemini blue
COLE        = "#e2eaf8"   # Cole white-blue
ERROR       = "#f87171"
SUCCESS     = "#4ade80"
WARNING     = "#facc15"
SCROLLBAR   = "#2a2a3a"
SCROLLBAR_H = "#4a4a6a"

FONT_SANS = "Inter, Segoe UI, Arial, sans-serif"
FONT_MONO = "JetBrains Mono, Fira Code, Cascadia Code, Consolas, monospace"


def apply_palette(app):
    """Apply dark QPalette to the QApplication."""
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window,          QColor(BG))
    palette.setColor(QPalette.ColorRole.WindowText,      QColor(TEXT))
    palette.setColor(QPalette.ColorRole.Base,            QColor(BG_ALT))
    palette.setColor(QPalette.ColorRole.AlternateBase,   QColor(BG_CARD))
    palette.setColor(QPalette.ColorRole.Text,            QColor(TEXT))
    palette.setColor(QPalette.ColorRole.Button,          QColor(BG_CARD))
    palette.setColor(QPalette.ColorRole.ButtonText,      QColor(TEXT))
    palette.setColor(QPalette.ColorRole.Highlight,       QColor(NOVA))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(TEXT_DIM))
    palette.setColor(QPalette.ColorRole.Link,            QColor(NOVA))
    palette.setColor(QPalette.ColorRole.ToolTipBase,     QColor(BG_CARD))
    palette.setColor(QPalette.ColorRole.ToolTipText,     QColor(TEXT))
    app.setPalette(palette)


STYLESHEET = f"""
/* ── Global ── */
QWidget {{
    background-color: {BG};
    color: {TEXT};
    font-family: "Segoe UI", Arial, sans-serif;
    font-size: 13px;
    border: none;
    outline: none;
}}

/* ── Scrollbars ── */
QScrollBar:vertical {{
    background: transparent; width: 8px; margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {SCROLLBAR}; border-radius: 4px; min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{ background: {SCROLLBAR_H}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{
    background: transparent; height: 8px; margin: 0;
}}
QScrollBar::handle:horizontal {{
    background: {SCROLLBAR}; border-radius: 4px; min-width: 24px;
}}
QScrollBar::handle:horizontal:hover {{ background: {SCROLLBAR_H}; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

/* ── Menu bar ── */
QMenuBar {{
    background: #111111;
    border-bottom: 1px solid {BORDER};
    padding: 2px 8px;
    spacing: 2px;
}}
QMenuBar::item {{
    padding: 4px 10px;
    border-radius: 4px;
    color: {TEXT_DIM};
}}
QMenuBar::item:selected, QMenuBar::item:pressed {{
    background: rgba(255,255,255,0.06);
    color: {TEXT};
}}
QMenu {{
    background: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 4px 0;
}}
QMenu::item {{
    padding: 6px 20px;
    color: {TEXT};
}}
QMenu::item:selected {{
    background: {NOVA};
    color: #fff;
}}
QMenu::separator {{
    height: 1px;
    background: {BORDER};
    margin: 4px 0;
}}

/* ── Splitter ── */
QSplitter::handle {{
    background: {BORDER};
    width: 1px;
    height: 1px;
}}
QSplitter::handle:hover {{
    background: {NOVA};
}}

/* ── Tab bar (session tabs) ── */
QTabBar {{
    background: {BG_ALT};
}}
QTabBar::tab {{
    background: {BG_ALT};
    color: {TEXT_DIM};
    padding: 6px 16px;
    border-top: 2px solid transparent;
    border-right: 1px solid {BORDER};
    font-size: 12px;
}}
QTabBar::tab:selected {{
    background: {BG};
    color: {TEXT};
    border-top: 2px solid {NOVA};
}}
QTabBar::tab:hover:!selected {{
    color: {TEXT};
    background: rgba(255,255,255,0.04);
}}
QTabWidget::pane {{
    border: none;
    background: {BG};
}}

/* ── Buttons ── */
QPushButton {{
    background: rgba(255,255,255,0.04);
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 6px 14px;
    color: {TEXT};
    font-size: 12px;
}}
QPushButton:hover {{
    border-color: {NOVA};
    color: {NOVA};
    background: rgba(143,144,255,0.08);
}}
QPushButton:pressed {{
    background: rgba(143,144,255,0.15);
}}
QPushButton:disabled {{
    color: {TEXT_DIM};
    border-color: {BORDER};
}}
QPushButton#send-btn {{
    background: {NOVA};
    color: #fff;
    border: none;
    border-radius: 6px;
    padding: 8px 18px;
    font-weight: 600;
    font-size: 13px;
}}
QPushButton#send-btn:hover {{
    background: #a0a1ff;
}}
QPushButton#send-btn:disabled {{
    background: {BG_CARD};
    color: {TEXT_DIM};
}}
QPushButton#stop-btn {{
    background: rgba(248,113,113,0.1);
    border: 1px solid rgba(248,113,113,0.4);
    color: {ERROR};
}}
QPushButton#stop-btn:hover {{
    background: rgba(248,113,113,0.2);
}}

/* ── Text input ── */
QTextEdit, QLineEdit {{
    background: {BG_INPUT};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 8px 12px;
    color: {TEXT};
    selection-background-color: {NOVA};
}}
QTextEdit:focus, QLineEdit:focus {{
    border-color: {NOVA};
}}

/* ── Tree widget (file explorer) ── */
QTreeWidget {{
    background: {BG_ALT};
    border: none;
    font-family: "Consolas", monospace;
    font-size: 12px;
}}
QTreeWidget::item {{
    padding: 3px 4px;
    border-radius: 3px;
    color: {TEXT};
}}
QTreeWidget::item:hover {{
    background: rgba(255,255,255,0.04);
}}
QTreeWidget::item:selected {{
    background: rgba(143,144,255,0.15);
    color: {NOVA};
}}
QTreeWidget::branch {{
    background: transparent;
}}

/* ── Status bar ── */
QStatusBar {{
    background: #111111;
    border-top: 1px solid {BORDER};
    color: {TEXT_DIM};
    font-size: 11px;
    padding: 0 8px;
}}
QStatusBar::item {{
    border: none;
}}

/* ── Tool tips ── */
QToolTip {{
    background: {BG_CARD};
    border: 1px solid {BORDER};
    color: {TEXT};
    padding: 4px 8px;
    border-radius: 4px;
}}

/* ── Label ── */
QLabel {{
    background: transparent;
    color: {TEXT};
}}

/* ── Combo box ── */
QComboBox {{
    background: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 4px 8px;
    color: {TEXT};
    font-size: 12px;
}}
QComboBox::drop-down {{
    border: none;
    width: 20px;
}}
QComboBox QAbstractItemView {{
    background: {BG_CARD};
    border: 1px solid {BORDER};
    selection-background-color: {NOVA};
    color: {TEXT};
}}
"""
