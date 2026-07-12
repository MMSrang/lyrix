"""Einstellungsdialog im Card-Design des Players (Punkte 9 + Redesign):

Dunkle, abgerundete Karten mit Akzent-Titeln statt roher Formularzeilen –
passend zum Look des Hauptfensters. Karten:

- Oberfläche      : Sprache
- Transkription   : Whisper-Modell, Rechengerät, Automatik-Hinweise
- KI-Pakete       : Whisper / Sprechertrennung / Geräusch-Erkennung / GPU –
                    jede Komponente einzeln mit Status-Chip, Aktiv-Schalter
                    und Installieren/Deinstallieren (Punkt 10)
- Online & Verlauf: Zuletzt-Liste, Cover/Songtexte, KI-Songtext-Timing
- Erweitert       : Hugging-Face-Token (eingeklappt)
"""

from __future__ import annotations

import os
import sys

from PySide6.QtCore import QProcess, QSettings, Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox,
                               QFormLayout, QFrame, QGridLayout, QLabel,
                               QLineEdit, QMessageBox, QProgressBar,
                               QPushButton, QVBoxLayout, QWidget)

from . import hardware, i18n, packs
from .i18n import tr
from .packs import PackDownloadThread, PackUninstallThread
from .thumbbar import apply_window_chrome
from .widgets import CollapsibleSection

_MODEL_SIZES = ["tiny", "base", "small", "medium", "large-v3"]

# (Paket-Schlüssel, Titel-Key, Settings-Key für den Aktiv-Schalter, Default)
_PACK_ROWS = [
    ("ai_whisper", "pack_whisper", "whisper_enabled", "true"),
    ("ai_speakers", "pack_speakers", "speakers_enabled", "false"),
    ("ai_sounds", "pack_sounds", "sounds_enabled", "true"),
    ("gpu", "gpu_pack", None, None),
]


def _hint_label(text: str, color: str | None = None) -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    if color:
        label.setStyleSheet(f"color:{color}; font-size:12px;")
    else:
        label.setObjectName("cardHint")
    return label


class SettingsDialog(QDialog):
    def __init__(self, settings: QSettings, parent=None):
        super().__init__(parent)
        self._settings = settings
        self._worker: PackDownloadThread | PackUninstallThread | None = None
        self._rows: dict[str, dict] = {}
        self._chrome_applied = False
        self.setObjectName("settingsDialog")
        self.setWindowTitle(tr("settings_title"))
        self.setMinimumWidth(640)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 14)
        layout.setSpacing(12)

        layout.addWidget(self._build_ui_card())
        layout.addWidget(self._build_transcription_card())
        layout.addWidget(self._build_packs_card())
        layout.addWidget(self._build_online_card())
        layout.addWidget(self._build_advanced_card())
        layout.addWidget(_hint_label(tr("model_note_next")))

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                   QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        ok = buttons.button(QDialogButtonBox.StandardButton.Ok)
        if ok is not None:
            ok.setText(tr("btn_ok"))
            ok.setObjectName("primaryButton")  # Akzent-Stil (theme.py)
            ok.setDefault(True)
        cancel = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if cancel is not None:
            cancel.setText(tr("btn_cancel"))
        layout.addWidget(buttons)

        self._refresh_pack_rows()

    def showEvent(self, event):
        super().showEvent(event)
        if not self._chrome_applied:
            self._chrome_applied = True
            apply_window_chrome(self)  # dunkle Titelleiste + runde Ecken

    # ------------------------------------------------------------- Card-Bau
    def _card(self, title: str) -> tuple[QFrame, QVBoxLayout]:
        """Karte im Stil der Hauptfenster-Panels: Titel oben, Inhalt darunter."""
        frame = QFrame()
        frame.setObjectName("settingsCard")
        outer = QVBoxLayout(frame)
        outer.setContentsMargins(16, 12, 16, 14)
        outer.setSpacing(10)
        heading = QLabel(title.upper())
        heading.setObjectName("cardTitle")
        outer.addWidget(heading)
        return frame, outer

    # ------------------------------------------------------------ Oberfläche
    def _build_ui_card(self) -> QFrame:
        card, lay = self._card(tr("group_ui"))
        form = QFormLayout()
        form.setVerticalSpacing(8)
        form.setHorizontalSpacing(12)

        self.lang_combo = QComboBox()
        for code, name in i18n.LANGUAGES.items():
            self.lang_combo.addItem(name, code)
        current_lang = str(self._settings.value("ui_language", i18n.language()))
        self.lang_combo.setCurrentIndex(
            max(0, self.lang_combo.findData(current_lang)))
        self._initial_lang = self.lang_combo.currentData()
        form.addRow(tr("lang_label"), self.lang_combo)
        lay.addLayout(form)
        return card

    # --------------------------------------------------------- Transkription
    def _build_transcription_card(self) -> QFrame:
        card, lay = self._card(tr("group_transcription"))
        form = QFormLayout()
        form.setVerticalSpacing(8)
        form.setHorizontalSpacing(12)

        self.model_combo = QComboBox()
        self.model_combo.addItem(tr("model_auto"), "auto")
        for size in _MODEL_SIZES:
            self.model_combo.addItem(size, size)
        current = str(self._settings.value("model_override", "auto"))
        self.model_combo.setCurrentIndex(
            max(0, self.model_combo.findData(current)))
        form.addRow(tr("model_label"), self.model_combo)

        self.device_combo = QComboBox()
        self.device_combo.addItem(tr("device_auto"), "auto")
        self.device_combo.addItem(tr("device_gpu"), "cuda")
        self.device_combo.addItem(tr("device_cpu"), "cpu")
        current_dev = str(self._settings.value("device_override", "auto"))
        self.device_combo.setCurrentIndex(
            max(0, self.device_combo.findData(current_dev)))
        form.addRow(tr("device_label"), self.device_combo)
        lay.addLayout(form)

        lay.addWidget(_hint_label(tr("device_note")))
        gpu = hardware.detect_nvidia()
        if gpu is not None and not packs.gpu_runtime_installed():
            lay.addWidget(_hint_label(tr("gpu_missing_hint", name=gpu.name),
                                      color="#e3b341"))
        try:
            auto_choice = hardware.pick("auto", self.device_combo.currentData())
            lay.addWidget(_hint_label(tr("auto_hint",
                                         label=auto_choice.label(),
                                         reason=auto_choice.reason)))
        except Exception:
            pass
        return card

    # ------------------------------------------------------------- KI-Pakete
    def _build_packs_card(self) -> QFrame:
        card, lay = self._card(tr("packs_group"))
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(8)

        for row_idx, (pack, title_key, enable_key, default) in enumerate(_PACK_ROWS):
            name = QLabel(tr(title_key))
            name.setWordWrap(True)
            state = QLabel("")
            toggle = None
            if enable_key is not None:
                toggle = QCheckBox(tr("pack_active"))
                toggle.setToolTip(tr("speakers_tip") if pack == "ai_speakers"
                                  else tr("pack_active_tip"))
                toggle.setChecked(
                    str(self._settings.value(enable_key, default)).lower()
                    == "true")
            button = QPushButton("")
            button.setFixedWidth(126)
            button.clicked.connect(
                lambda _=False, p=pack: self._on_pack_button(p))
            grid.addWidget(name, row_idx, 0)
            grid.addWidget(state, row_idx, 1, Qt.AlignmentFlag.AlignCenter)
            if toggle is not None:
                grid.addWidget(toggle, row_idx, 2)
            grid.addWidget(button, row_idx, 3)
            self._rows[pack] = {"state": state, "toggle": toggle,
                                "button": button, "enable_key": enable_key}
        grid.setColumnStretch(0, 1)
        lay.addLayout(grid)

        self.pack_progress = QProgressBar()
        self.pack_progress.setTextVisible(False)
        self.pack_progress.hide()
        self.pack_status = _hint_label("")
        lay.addWidget(self.pack_progress)
        lay.addWidget(self.pack_status)
        return card

    # ------------------------------------------------------ Online & Verlauf
    def _build_online_card(self) -> QFrame:
        card, lay = self._card(tr("group_online"))

        self.recent_check = QCheckBox(tr("recent_toggle"))
        self.recent_check.setChecked(
            str(self._settings.value("recent_enabled", "true")).lower()
            == "true")
        lay.addWidget(self.recent_check)

        self.cover_check = QCheckBox(tr("cover_toggle"))
        self.cover_check.setChecked(
            str(self._settings.value("cover_search_enabled", "false")).lower()
            == "true")
        lay.addWidget(self.cover_check)

        self.align_check = QCheckBox(tr("align_toggle"))
        self.align_check.setToolTip(tr("align_tip"))
        self.align_check.setChecked(
            str(self._settings.value("align_enabled", "true")).lower()
            == "true")
        lay.addWidget(self.align_check)
        return card

    # ------------------------------------------------------------- Erweitert
    def _build_advanced_card(self) -> QWidget:
        advanced_content = QWidget()
        adv_lay = QFormLayout(advanced_content)
        adv_lay.setContentsMargins(8, 4, 0, 4)
        adv_lay.setHorizontalSpacing(12)
        self.token_edit = QLineEdit()
        self.token_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.token_edit.setPlaceholderText("hf_…")
        self.token_edit.setText(str(self._settings.value("hf_token", "")))
        adv_lay.addRow(tr("token_label"), self.token_edit)
        token_help = _hint_label(tr("token_help"))
        adv_lay.addRow("", token_help)
        return CollapsibleSection(tr("advanced"), advanced_content)

    # ------------------------------------------------- Paket-Zeilen-Zustand
    def _refresh_pack_rows(self):
        busy = self._worker is not None and self._worker.isRunning()
        frozen = bool(getattr(sys, "frozen", False))
        for pack, row in self._rows.items():
            installed = packs.component_installed(pack)
            state = row["state"]
            state.setText(tr("pack_installed") if installed
                          else tr("pack_missing"))
            state.setProperty("chip", "ok" if installed else "warn")
            state.style().unpolish(state)
            state.style().polish(state)
            button = row["button"]
            button.setText(tr("pack_uninstall") if installed
                           else tr("pack_install_short"))
            can_manage = frozen or (pack == "gpu")
            button.setEnabled(not busy and can_manage)
            button.setToolTip("" if can_manage else tr("pack_dev_hint"))
            if row["toggle"] is not None:
                row["toggle"].setEnabled(installed)

    def _on_pack_button(self, pack: str):
        if self._worker is not None and self._worker.isRunning():
            return
        if packs.component_installed(pack):
            title = next(tr(t) for p, t, _k, _d in _PACK_ROWS if p == pack)
            answer = QMessageBox.question(
                self, tr("settings_title"),
                tr("pack_uninstall_confirm", name=title))
            if answer != QMessageBox.StandardButton.Yes:
                return
            worker = PackUninstallThread(pack, self)
        else:
            worker = PackDownloadThread(pack, self)
        self.pack_progress.setRange(0, 0)
        self.pack_progress.show()
        self.pack_status.setText("…")
        worker.progress.connect(self._on_pack_progress)
        worker.finished_ok.connect(self._on_pack_done)
        worker.failed.connect(self._on_pack_failed)
        self._worker = worker
        worker.start()
        self._refresh_pack_rows()

    def _on_pack_progress(self, label: str, frac: float):
        self.pack_status.setText(label)
        if frac < 0:
            self.pack_progress.setRange(0, 0)
        else:
            if self.pack_progress.maximum() == 0:
                self.pack_progress.setRange(0, 1000)
            self.pack_progress.setValue(int(frac * 1000))

    def _on_pack_done(self, pack: str):
        self.pack_progress.hide()
        installed = packs.component_installed(pack)
        self.pack_status.setText(tr("pack_done") if installed
                                 else tr("pack_removed"))
        if not installed:
            packs.release_memory()
        self._refresh_pack_rows()

    def _on_pack_failed(self, message: str):
        self.pack_progress.hide()
        self.pack_status.setText("")
        self._refresh_pack_rows()
        QMessageBox.warning(self, tr("settings_title"),
                            tr("pack_failed", msg=message))

    # ------------------------------------------------------------------
    def accept(self):
        s = self._settings
        s.setValue("model_override", self.model_combo.currentData())
        s.setValue("device_override", self.device_combo.currentData())
        for row in self._rows.values():
            if row["toggle"] is not None:
                s.setValue(row["enable_key"],
                           "true" if row["toggle"].isChecked() else "false")
        s.setValue("hf_token", self.token_edit.text().strip())
        s.setValue("recent_enabled",
                   "true" if self.recent_check.isChecked() else "false")
        s.setValue("cover_search_enabled",
                   "true" if self.cover_check.isChecked() else "false")
        s.setValue("align_enabled",
                   "true" if self.align_check.isChecked() else "false")
        new_lang = self.lang_combo.currentData()
        s.setValue("ui_language", new_lang)
        s.sync()
        if new_lang != self._initial_lang:
            self._offer_restart()
        super().accept()

    def _offer_restart(self):
        answer = QMessageBox.question(self, tr("lang_restart_title"),
                                      tr("lang_restart_text"))
        if answer != QMessageBox.StandardButton.Yes:
            return
        if getattr(sys, "frozen", False):
            QProcess.startDetached(sys.executable, [])
        else:
            QProcess.startDetached(sys.executable, ["-m", "lyrix.main"])
        os._exit(0)
