"""Programmstart: Umgebung vorbereiten, Migration, Qt-App aufbauen."""

from __future__ import annotations

import multiprocessing
import os
import shutil
import sys


def _setup_env():
    # OpenMP wird von ctranslate2 UND torch mitgebracht – ohne diese Variable
    # bricht der Prozess unter Windows mit "OMP Error #15" ab.
    os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
    os.environ.setdefault("OMP_NUM_THREADS", str(max(1, (os.cpu_count() or 4) - 1)))
    # OpenMP-Threads sollen nach getaner Arbeit sofort schlafen statt aktiv
    # zu warten (Spin-Wait) – sonst frisst die App im Leerlauf CPU (Punkt 11).
    os.environ.setdefault("KMP_BLOCKTIME", "0")
    os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
    os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
    # Hugging-Face-Cache OHNE Symlinks anlegen: Windows-Symlinks im Snapshot
    # scheitern je nach Umgebung (Datei-Virtualisierung, "nicht vertrauens-
    # würdiger Bereitstellungspunkt" = WinError 448). Echte Kopien statt
    # Links beheben das dauerhaft (Punkt 3).
    os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS", "1")
    # Modelle landen sichtbar und dauerhaft unter %LOCALAPPDATA%\Lyrix
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    os.environ.setdefault("HF_HOME", os.path.join(base, "Lyrix", "Modelle"))


def _migrate_from_transkriptor():
    """Übernimmt Einstellungen und Modell-Cache der Vorgängerversion."""
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    old_models = os.path.join(base, "Transkriptor", "Modelle")
    new_models = os.path.join(base, "Lyrix", "Modelle")
    if os.path.isdir(old_models) and not os.path.isdir(new_models):
        try:
            os.makedirs(os.path.dirname(new_models), exist_ok=True)
            shutil.move(old_models, new_models)
        except OSError:
            pass

    try:
        from PySide6.QtCore import QSettings
        from . import APP_NAME, LEGACY_APP_NAME, ORG_NAME
        new = QSettings(ORG_NAME, APP_NAME)
        if new.contains("migrated_v2"):
            return
        old = QSettings(LEGACY_APP_NAME, LEGACY_APP_NAME)
        for key in old.allKeys():
            if not new.contains(key):
                new.setValue(key, old.value(key))
        new.setValue("migrated_v2", "true")
        new.sync()
    except Exception:
        pass


def _init_language():
    """Oberflächensprache: Einstellung > Installer-Vorgabe > Systemsprache."""
    try:
        from PySide6.QtCore import QSettings
        from . import APP_NAME, ORG_NAME, i18n
        settings = QSettings(ORG_NAME, APP_NAME)
        lang = str(settings.value("ui_language", "")).strip()
        if not lang:
            lang = i18n.system_default()
            settings.setValue("ui_language", lang)
        i18n.set_language(lang)
    except Exception:
        pass


def _selftest() -> int:
    """Schneller Funktionstest ohne Fenster (auch in der EXE nutzbar)."""
    from . import __version__, hardware, packs
    choice = hardware.pick("auto")
    gpu = hardware.detect_nvidia()
    report = (f"Lyrix {__version__} Selbsttest\n"
              f"Modellwahl: {choice.model} | {choice.device} | "
              f"{choice.compute_type} | Threads: {choice.cpu_threads}\n"
              f"Begründung: {choice.reason}\n"
              f"NVIDIA-GPU: {gpu.name + f' ({gpu.vram_gb:.0f} GB)' if gpu else 'keine erkannt'}\n"
              f"GPU-Paket: {'installiert' if packs.gpu_runtime_installed() else 'nicht installiert'}\n"
              f"KI-Paket: {'installiert' if packs.ai_available() else 'nicht installiert'}\n")
    ok = True
    if packs.ai_available():
        for mod in ("faster_whisper", "pyannote.audio"):
            try:
                __import__(mod)
                report += f"Import OK: {mod}\n"
            except Exception as exc:  # noqa: BLE001
                report += f"Import FEHLER: {mod}: {exc}\n"
                ok = False
        from . import diarizer, soundtags
        report += ("Sprecher-Modelle: vorhanden\n" if diarizer.bundled_models_available()
                   else "Sprecher-Modelle: FEHLEN\n")
        report += ("Geräusch-Modell (CNN14): vorhanden\n" if soundtags.model_available()
                   else "Geräusch-Modell (CNN14): FEHLT\n")
        if not (diarizer.bundled_models_available() and soundtags.model_available()):
            ok = False
    for mod in ("PySide6.QtMultimedia", "comtypes", "winrt.windows.media.playback"):
        try:
            __import__(mod)
            report += f"Import OK: {mod}\n"
        except Exception as exc:  # noqa: BLE001
            report += f"Import FEHLER: {mod}: {exc}\n"
            ok = False
    report += "ERGEBNIS: OK\n" if ok else "ERGEBNIS: FEHLER\n"
    try:
        print(report, end="")
    except Exception:
        pass
    out = os.path.join(os.environ.get("TEMP", "."), "lyrix_selftest.txt")
    try:
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(report)
    except OSError:
        pass
    return 0 if ok else 1


def main() -> int:
    multiprocessing.freeze_support()
    _setup_env()
    _migrate_from_transkriptor()

    from . import packs
    packs.load_gpu_runtime()  # NVIDIA-DLLs bereitstellen, falls installiert

    if "--selftest" in sys.argv:
        return _selftest()
    if "--diag-whisper" in sys.argv:
        # Diagnose: Whisper direkt (ohne GUI) laufen lassen; hängt es,
        # schreibt faulthandler nach 45 s alle Thread-Stacks auf stderr.
        import faulthandler
        faulthandler.enable()
        faulthandler.dump_traceback_later(45, exit=True)
        args = [a for a in sys.argv[1:] if not a.startswith("--")]
        device = "cuda" if "--diag-gpu" in sys.argv else "cpu"
        print(f"Lade WhisperModel(tiny, {device}) ...", flush=True)
        from faster_whisper import WhisperModel
        model = WhisperModel("tiny", device=device,
                             compute_type="int8_float16" if device == "cuda" else "int8",
                             cpu_threads=4)
        print("Modell geladen. Transkribiere ...", flush=True)
        segments, info = model.transcribe(args[0], vad_filter=True,
                                          word_timestamps=True, beam_size=5)
        for seg in segments:
            print(f"  {seg.start:.2f}-{seg.end:.2f}: {seg.text}", flush=True)
        print("DIAG OK", flush=True)
        faulthandler.cancel_dump_traceback_later()
        return 0
    smoketest = "--smoketest" in sys.argv

    from PySide6.QtCore import QTimer
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication

    from . import APP_NAME, ORG_NAME
    _init_language()
    from .mainwindow import MainWindow
    from .theme import build_qss
    from .util import resource_path

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(ORG_NAME)
    app.setStyle("Fusion")
    app.setStyleSheet(build_qss())
    icon_file = resource_path(os.path.join("assets", "icon.ico"))
    if os.path.exists(icon_file):
        app.setWindowIcon(QIcon(icon_file))

    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    path = args[0] if args else None

    window = MainWindow(path)
    window.show()

    if smoketest:
        # Marker VOR dem Schließen schreiben – closeEvent beendet den Prozess
        # bewusst hart (os._exit 0). Absichtlich derselbe Weg wie beim
        # Nutzer-Klick auf X: app.quit() liefe in den Interpreter-Teardown,
        # in dem späte winrt/Qt-Callbacks crashen (0xC000041D).
        def _finish_smoketest():
            out = os.path.join(os.environ.get("TEMP", "."),
                               "lyrix_smoketest.txt")
            lines = window.lyrics.lines
            n_tags = sum(1 for l in lines if l.seg.get("is_tag"))
            try:
                with open(out, "w", encoding="utf-8") as fh:
                    fh.write(f"smoketest ok, lines={len(lines) - n_tags}, "
                             f"tags={n_tags}, "
                             f"sprecher={window.lyrics.speaker_count()}\n")
            except OSError:
                pass
            window.close()

        budget = int(os.environ.get("LYRIX_SMOKETEST_MS", "45000"))
        QTimer.singleShot(budget if path else 2500, _finish_smoketest)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
