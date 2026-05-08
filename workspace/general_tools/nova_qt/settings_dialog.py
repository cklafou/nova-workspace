"""
settings_dialog.py — Advanced settings dialog for Nova Qt.

Controls exposed:
  Nova inference  — temperature, top_p (sent as set_params WS message)
  Agent toggles   — mute Claude / mute Gemini (sent as mute_agent WS message)
  Display         — sidebar width, message font size (local Qt prefs only)

Opens from Tools → Advanced Settings or Ctrl+,
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSlider, QCheckBox, QGroupBox, QDialogButtonBox, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal

from .theme import NOVA, TEXT_DIM, BG, BG_ALT, BORDER, TEXT


def _slider_row(label: str, lo: float, hi: float, step: int,
                current: float, fmt="{:.2f}") -> tuple:
    """Returns (row_widget, slider, value_label)."""
    row = QHBoxLayout()
    lbl = QLabel(label)
    lbl.setFixedWidth(110)
    lbl.setStyleSheet(f"color: {TEXT}; font-size: 12px;")

    sl = QSlider(Qt.Orientation.Horizontal)
    sl.setRange(int(lo * step), int(hi * step))
    sl.setValue(int(current * step))
    sl.setFixedWidth(160)
    sl.setStyleSheet("""
        QSlider::groove:horizontal { height: 3px; background: #2a2a3a; border-radius: 2px; }
        QSlider::handle:horizontal {
            background: #8f90ff; border: none;
            width: 13px; height: 13px; margin: -5px 0; border-radius: 7px;
        }
        QSlider::sub-page:horizontal { background: #5a5aee; border-radius: 2px; }
    """)

    val_lbl = QLabel(fmt.format(current))
    val_lbl.setFixedWidth(40)
    val_lbl.setStyleSheet(f"color: {NOVA}; font-size: 12px; font-family: Consolas;")
    val_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)

    sl.valueChanged.connect(lambda v: val_lbl.setText(fmt.format(v / step)))

    row.addWidget(lbl)
    row.addWidget(sl)
    row.addWidget(val_lbl)
    return row, sl, val_lbl


class AdvancedSettingsDialog(QDialog):
    """
    Settings dialog. Emits params_changed when the user clicks Apply.
    The caller (window.py) sends the WS messages.
    """

    params_changed = pyqtSignal(dict)   # {"temperature": f, "top_p": f, ...}

    def __init__(self, current: dict = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Advanced Settings")
        self.setMinimumWidth(420)
        self.setModal(True)
        self.setStyleSheet(f"""
            QDialog  {{ background: {BG};     color: {TEXT}; }}
            QGroupBox {{
                color: {TEXT_DIM};
                font-size: 10px;
                font-weight: 600;
                letter-spacing: 0.06em;
                border: 1px solid {BORDER};
                border-radius: 6px;
                margin-top: 8px;
                padding-top: 8px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 6px;
                left: 10px;
            }}
        """)

        c = current or {}
        lay = QVBoxLayout(self)
        lay.setSpacing(14)
        lay.setContentsMargins(16, 16, 16, 16)

        # ── Nova Inference ────────────────────────────────────────────────────
        nova_group = QGroupBox("NOVA INFERENCE  (requires patch_autonomous_behavior.ps1)")
        nova_lay = QVBoxLayout(nova_group)
        nova_lay.setSpacing(10)

        temp_row, self._temp_sl, self._temp_lbl = _slider_row(
            "Temperature", 0.0, 2.0, 100, c.get("temperature", 0.7))
        topp_row, self._topp_sl, self._topp_lbl = _slider_row(
            "Top-P", 0.0, 1.0, 100, c.get("top_p", 0.9))

        nova_lay.addLayout(temp_row)

        temp_hint = QLabel(
            "Lower = more focused/deterministic.  Higher = more creative/varied.\n"
            "0.7 is Nova's default. Try 0.4 for precise tasks, 1.2 for creative."
        )
        temp_hint.setStyleSheet(f"color: {TEXT_DIM}; font-size: 10px; padding-left: 114px;")
        nova_lay.addWidget(temp_hint)
        nova_lay.addLayout(topp_row)

        topp_hint = QLabel(
            "Controls vocabulary diversity. 0.9 is Nova's default. Rarely needs changing."
        )
        topp_hint.setStyleSheet(f"color: {TEXT_DIM}; font-size: 10px; padding-left: 114px;")
        nova_lay.addWidget(topp_hint)
        lay.addWidget(nova_group)

        # ── Agent toggles ─────────────────────────────────────────────────────
        agent_group = QGroupBox("AGENT VISIBILITY")
        agent_lay = QVBoxLayout(agent_group)
        agent_lay.setSpacing(6)

        self._mute_claude = QCheckBox("Mute Claude  (stop Claude from responding)")
        self._mute_gemini = QCheckBox("Mute Gemini  (stop Gemini from responding)")
        for cb in (self._mute_claude, self._mute_gemini):
            cb.setStyleSheet(f"color: {TEXT}; font-size: 12px;")

        self._mute_claude.setChecked(c.get("mute_claude", True))
        self._mute_gemini.setChecked(c.get("mute_gemini", True))
        agent_lay.addWidget(self._mute_claude)
        agent_lay.addWidget(self._mute_gemini)

        mute_hint = QLabel(
            "Muting stops that model from receiving new messages. Existing in-flight\n"
            "responses will still complete."
        )
        mute_hint.setStyleSheet(f"color: {TEXT_DIM}; font-size: 10px;")
        agent_lay.addWidget(mute_hint)
        lay.addWidget(agent_group)

        # ── Separator ─────────────────────────────────────────────────────────
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background: {BORDER};")
        lay.addWidget(sep)

        # ── Buttons ───────────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        reset_btn = QPushButton("Reset Defaults")
        reset_btn.setStyleSheet(f"color: {TEXT_DIM}; background: transparent; border: 1px solid {BORDER}; border-radius: 4px; padding: 4px 12px;")
        reset_btn.clicked.connect(self._reset)
        btn_row.addWidget(reset_btn)

        apply_btn = QPushButton("Apply")
        apply_btn.setDefault(True)
        apply_btn.setStyleSheet(f"""
            QPushButton {{
                background: {NOVA}22;
                color: {NOVA};
                border: 1px solid {NOVA}66;
                border-radius: 4px;
                padding: 4px 18px;
                font-weight: 600;
            }}
            QPushButton:hover {{ background: {NOVA}44; }}
        """)
        apply_btn.clicked.connect(self._apply)
        btn_row.addWidget(apply_btn)

        lay.addLayout(btn_row)

    def _apply(self):
        params = {
            "temperature":  self._temp_sl.value() / 100.0,
            "top_p":        self._topp_sl.value() / 100.0,
            "mute_claude":  self._mute_claude.isChecked(),
            "mute_gemini":  self._mute_gemini.isChecked(),
        }
        self.params_changed.emit(params)
        self.accept()

    def _reset(self):
        self._temp_sl.setValue(70)   # 0.7
        self._topp_sl.setValue(90)   # 0.9
        self._mute_claude.setChecked(False)
        self._mute_gemini.setChecked(False)
