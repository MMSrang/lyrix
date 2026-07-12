"""Hintergrund-Thread für die Spracherkennung mit Faster-Whisper.

Die Transkription läuft als gechunktes Streaming: faster-whisper liefert die
Segmente über einen Generator nach und nach, jede fertige Zeile wird sofort
per Signal an die Oberfläche gemeldet.
"""

from __future__ import annotations

import os
import shutil
import sys
import traceback

from PySide6.QtCore import QThread, Signal

from . import hardware
from .i18n import tr
from .lines import split_words_into_lines


def _repo_dir(model_name: str) -> str | None:
    hf_home = os.environ.get("HF_HOME")
    if not hf_home:
        return None
    return os.path.join(hf_home, "hub",
                        f"models--Systran--faster-whisper-{model_name}")


def _purge_model_cache(model_name: str):
    """Entfernt einen (möglicherweise beschädigten) Whisper-Download aus dem
    Hugging-Face-Cache, damit er sauber neu geladen wird."""
    repo_dir = _repo_dir(model_name)
    if repo_dir and os.path.isdir(repo_dir):
        shutil.rmtree(repo_dir, ignore_errors=True)


def _materialize_snapshot(model_name: str) -> bool:
    """Ersetzt Symlinks im Cache-Snapshot durch echte Kopien der Blobs.

    huggingface_hub legt Snapshots als Symlinks auf blobs/ an. Auf manchen
    Systemen (z. B. Datei-Virtualisierung, Netzlaufwerke) kann weder Python
    noch die native C++-Dateiöffnung von ctranslate2 diese Links auflösen
    (u. a. WinError 448, "nicht vertrauenswürdiger Bereitstellungspunkt"),
    obwohl die Daten vollständig da sind. Kopien beheben das ohne erneuten
    Download. Geprüft wird JEDE Datei im Snapshot: nicht nur als Symlink
    markierte, sondern auch solche, die sich schlicht nicht öffnen lassen."""
    repo_dir = _repo_dir(model_name)
    if not repo_dir:
        return False
    snap_root = os.path.join(repo_dir, "snapshots")
    if not os.path.isdir(snap_root):
        return False

    def replace_with_copy(path: str) -> bool:
        real = os.path.realpath(path)
        if os.path.normcase(real) == os.path.normcase(path):
            return False  # nicht auflösbar -> Neuladen nötig
        if not os.path.isfile(real):
            return False  # Blob fehlt wirklich -> Neuladen nötig
        tmp = path + ".materialize"
        shutil.copyfile(real, tmp)
        os.remove(path)
        os.replace(tmp, path)
        return True

    changed = False
    for root, _dirs, files in os.walk(snap_root):
        for name in files:
            path = os.path.join(root, name)
            if os.path.islink(path):
                if not replace_with_copy(path):
                    return False
                changed = True
                continue
            try:
                with open(path, "rb") as fh:
                    fh.read(1)
            except OSError:
                if not replace_with_copy(path):
                    return False
                changed = True
    return changed

def _language_name(code: str) -> str:
    """Anzeigename der erkannten Audio-Sprache (in Landessprache)."""
    names = {
        "de": "Deutsch", "en": "English", "fr": "Français", "es": "Español",
        "it": "Italiano", "pt": "Português", "nl": "Nederlands",
        "pl": "Polski", "ru": "Русский", "tr": "Türkçe", "ar": "العربية",
        "uk": "Українська", "zh": "中文", "ja": "日本語", "ko": "한국어",
    }
    return names.get(code, code)


class TranscriberThread(QThread):
    status = Signal(str)        # Fortschritts-/Zustandstext
    model_info = Signal(str)    # z. B. "Whisper small · CPU (int8)"
    line_ready = Signal(dict)   # eine fertige Textzeile mit Zeitstempeln
    progress = Signal(float)    # 0.0 .. 1.0
    finished_ok = Signal(str)   # erkannte Sprache
    failed = Signal(str)

    def __init__(self, path: str, model_override: str = "auto",
                 device_override: str = "auto", parent=None):
        super().__init__(parent)
        self._path = path
        self._override = model_override or "auto"
        self._device = device_override or "auto"
        self._cancel = False

    def cancel(self):
        self._cancel = True

    # ------------------------------------------------------------------
    def run(self):
        try:
            self._run()
        except Exception as exc:  # noqa: BLE001 - alles der UI melden
            traceback.print_exc(file=sys.stderr)
            if not self._cancel:
                self.failed.emit(f"{exc.__class__.__name__}: {exc}")

    def _run(self):
        from faster_whisper import WhisperModel

        self.status.emit(tr("hw_analyzing"))
        choice = hardware.pick(self._override, self._device)
        self.model_info.emit(choice.label())
        if self._cancel:
            return

        self.status.emit(tr("model_loading", model=choice.model))

        def load(c):
            return WhisperModel(c.model, device=c.device,
                                compute_type=c.compute_type,
                                cpu_threads=c.cpu_threads)

        def load_healing(c):
            """Lädt das Modell; bei unlesbarem Cache-Snapshot erst Symlinks
            durch Kopien ersetzen, dann notfalls neu herunterladen.

            "Unlesbar" heißt: ctranslate2 meldet "Unable to open file"
            (RuntimeError) ODER schon das Lesen von config.json & Co.
            scheitert an Windows-Symlink-Problemen (OSError, z. B.
            WinError 448 "nicht vertrauenswürdiger Bereitstellungspunkt")."""
            def unreadable(err):
                if "Unable to open file" in str(err):
                    return True
                winerror = getattr(err, "winerror", None)
                if winerror in (448, 1920):  # Mount-Point/Symlink nicht lesbar
                    return True
                text = str(err).lower()
                return ("bereitstellungspunkt" in text
                        or "mount point" in text
                        or "symlink" in text
                        or "reparse" in text)
            try:
                return load(c)
            except (RuntimeError, OSError) as err:
                if not unreadable(err):
                    raise
            self.status.emit(tr("cache_repair"))
            if _materialize_snapshot(c.model):
                try:
                    return load(c)
                except (RuntimeError, OSError) as err:
                    if not unreadable(err):
                        raise
            # Neu herunterladen: dank HF_HUB_DISABLE_SYMLINKS entstehen dabei
            # echte Dateien statt Symlinks – der Fehler kehrt nicht zurück.
            self.status.emit(tr("model_redownload"))
            _purge_model_cache(c.model)
            try:
                return load(c)
            except (RuntimeError, OSError) as err:
                if not unreadable(err):
                    raise
                _materialize_snapshot(c.model)
                return load(c)

        def cpu_retry():
            self.status.emit(tr("gpu_fallback"))
            fallback = hardware.pick(self._override, "cpu", allow_cuda=False)
            self.model_info.emit(fallback.label())
            return fallback, load_healing(fallback)

        try:
            model = load_healing(choice)
        except Exception:
            if choice.device != "cuda":
                raise
            # GPU-Initialisierung fehlgeschlagen (z. B. fehlende cuDNN-DLLs)
            choice, model = cpu_retry()
        if self._cancel:
            return

        try:
            self._transcribe_loop(model)
        except RuntimeError as exc:
            # ctranslate2 lädt cuBLAS/cuDNN erst beim ersten Encode – Fehler
            # der GPU-Laufzeit können deshalb auch HIER auftreten. Einmal
            # komplett auf der CPU wiederholen statt hart zu scheitern.
            gpu_error = any(k in str(exc).lower()
                            for k in ("cublas", "cudnn", "cuda"))
            if choice.device != "cuda" or not gpu_error or self._cancel:
                raise
            choice, model = cpu_retry()
            if self._cancel:
                return
            self._transcribe_loop(model)

    def _transcribe_loop(self, model):
        self.status.emit(tr("transcribing"))
        segments, info = model.transcribe(
            self._path,
            vad_filter=True,
            word_timestamps=True,
            beam_size=5,
        )
        duration = float(getattr(info, "duration", 0.0) or 0.0)
        lang_code = getattr(info, "language", "") or ""
        lang = _language_name(lang_code)

        for seg in segments:
            if self._cancel:
                return
            words = list(seg.words or [])
            if words:
                for line in split_words_into_lines(words):
                    self.line_ready.emit(line)
            else:
                text = (seg.text or "").strip()
                if text:
                    self.line_ready.emit({
                        "start": float(seg.start), "end": float(seg.end),
                        "text": text, "words": [],
                    })
            if duration > 0:
                self.progress.emit(min(1.0, float(seg.end) / duration))
            if lang:
                self.status.emit(tr("transcribing_lang", lang=lang))
                lang = ""  # nur einmal aktualisieren

        self.finished_ok.emit(_language_name(lang_code))
