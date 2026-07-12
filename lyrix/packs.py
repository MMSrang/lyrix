"""Optionale Pakete: KI-Funktionen und NVIDIA-GPU-Beschleunigung.

Lyrix ist modular aufgebaut:
- Kern       : reiner Audio-Player (immer installiert)
- KI-Paket   : torch/ctranslate2/pyannote/PANNs-Dateien in _internal
               (Installer-Komponente oder Nachladen vom GitHub-Release)
- GPU-Paket  : cuBLAS/cuDNN-Laufzeitbibliotheken von NVIDIA (PyPI-Wheels),
               entpackt nach %LOCALAPPDATA%\\Lyrix\\gpu – damit rechnet
               faster-whisper (ctranslate2) auf der NVIDIA-GPU, während
               pyannote und die Geräusch-Erkennung parallel auf der CPU laufen.
"""

from __future__ import annotations

import json
import os
import shutil
import ssl
import sys
import tempfile
import urllib.request
import zipfile

from PySide6.QtCore import QThread, Signal

# Quelle für das nachladbare KI-Paket (GitHub-Release des Open-Source-Repos).
# Für Tests/eigene Builds per Umgebungsvariable LYRIX_AI_PACK_URL übersteuerbar.
# Vor dem Online-Download werden lokale Kopien des Archivs geprüft
# (_ai_pack_sources): neben der EXE, im Datenordner, im Downloads-Ordner.
AI_PACK_URL = ("https://github.com/lyrix-app/lyrix/releases/download/"
               "v{version}/lyrix-ai-pack-{version}.zip")


def ai_pack_name() -> str:
    from . import __version__
    return f"lyrix-ai-pack-{__version__}.zip"


def _ai_pack_sources() -> list[str]:
    """Quellen für das KI-Paket in Prüf-Reihenfolge: Umgebungsvariable,
    lokale Archiv-Kopien (App-Ordner, Datenordner, Downloads), GitHub."""
    from . import __version__
    name = ai_pack_name()
    sources: list[str] = []
    env = os.environ.get("LYRIX_AI_PACK_URL")
    if env:
        sources.append(env)
    folders = [os.path.dirname(sys.executable), data_dir(),
               os.path.join(os.path.expanduser("~"), "Downloads")]
    for folder in folders:
        candidate = os.path.join(folder, name)
        if os.path.isfile(candidate):
            sources.append("file:///" + candidate.replace("\\", "/"))
    sources.append(AI_PACK_URL.format(version=__version__))
    return sources

# NVIDIA-Laufzeit-Wheels (offizielle PyPI-Pakete von NVIDIA)
GPU_WHEELS = ["nvidia-cublas-cu12", "nvidia-cudnn-cu12",
              "nvidia-cuda-runtime-cu12"]


def data_dir() -> str:
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return os.path.join(base, "Lyrix")


def gpu_dir() -> str:
    return os.path.join(data_dir(), "gpu")


# ------------------------------------------------------------ Verfügbarkeit
def _internal_dir() -> str:
    return os.path.join(os.path.dirname(sys.executable), "_internal")


def _has_internal(name: str) -> bool:
    if not getattr(sys, "frozen", False):
        return True  # im Quellcode-Betrieb ist alles per pip da
    return os.path.isdir(os.path.join(_internal_dir(), name))


def transcription_available() -> bool:
    """Whisper-Komponente installiert? (ctranslate2 ist der Marker.)"""
    if not getattr(sys, "frozen", False):
        try:
            import ctranslate2  # noqa: F401
            return True
        except Exception:
            return False
    return _has_internal("ctranslate2")


def torch_available() -> bool:
    if not getattr(sys, "frozen", False):
        try:
            import torch  # noqa: F401
            return True
        except Exception:
            return False
    return _has_internal("torch")


def speakers_available() -> bool:
    """Sprechertrennungs-Komponente (pyannote + torch) installiert?"""
    return torch_available() and _has_internal("pyannote")


def sounds_available() -> bool:
    """Geräusch-Erkennung braucht nur torch + die Modelldateien."""
    return torch_available()


def ai_available() -> bool:
    """Mindestens eine KI-Komponente installiert?"""
    return transcription_available() or torch_available()


# ------------------------------------------------- Einzel-Komponenten (Punkt 10)
AI_COMPONENTS = ("ai_whisper", "ai_speakers", "ai_sounds")


def manifest_path() -> str:
    if getattr(sys, "frozen", False):
        return os.path.join(_internal_dir(), "ai_manifest.txt")
    # Quellcode-Betrieb: das beim Build erzeugte Manifest (falls vorhanden)
    return os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "build", "ai_manifest.txt")


def read_manifest(path: str | None = None) -> list[tuple[str, list[str]]]:
    """Liest ai_manifest.txt: [(Eintrag, [Komponenten]), …].

    Einträge sind Namen unter _internal (Ordner oder Datei); Modelldateien
    stehen als "models/<name>". Die Komponentenliste stammt aus den
    Inno-Oder-Ausdrücken ("ai_speakers or ai_sounds")."""
    path = path or manifest_path()
    entries: list[tuple[str, list[str]]] = []
    try:
        with open(path, encoding="utf-8") as fh:
            for raw in fh:
                raw = raw.strip()
                if not raw or "\t" not in raw:
                    continue
                name, expr = raw.split("\t", 1)
                parts = [p.strip() for p in expr.split(" or ") if p.strip()]
                if name and parts:
                    entries.append((name, parts))
    except OSError:
        pass
    return entries


def component_installed(comp: str) -> bool:
    """Ist die Komponente (inklusive ihrer Modelldateien) installiert?"""
    if comp == "ai_whisper":
        return transcription_available()
    if comp == "ai_speakers":
        from . import diarizer
        return speakers_available() and diarizer.bundled_models_available()
    if comp == "ai_sounds":
        from . import soundtags
        return torch_available() and soundtags.model_available()
    if comp == "gpu":
        return gpu_runtime_installed()
    return False


def removable_entries(comp: str) -> list[str]:
    """Manifest-Einträge, die beim Deinstallieren von comp gelöscht werden
    dürfen: alles, was comp gehört und von keiner anderen (noch
    installierten) Komponente gebraucht wird – geteilte Gruppen wie der
    torch-Stack bleiben stehen, solange z. B. die Geräusch-Erkennung sie
    weiter nutzt."""
    result = []
    for name, parts in read_manifest():
        if comp not in parts:
            continue
        others = [p for p in parts if p != comp]
        if any(component_installed(o) for o in others):
            continue
        result.append(name)
    return result


def gpu_runtime_installed() -> bool:
    return bool(_gpu_dll_dirs())


def _gpu_dll_dirs() -> list[str]:
    root = gpu_dir()
    dirs = []
    for sub in ("cublas", "cudnn", "cuda_runtime"):
        candidate = os.path.join(root, "nvidia", sub, "bin")
        if os.path.isdir(candidate):
            dirs.append(candidate)
    return dirs


def load_gpu_runtime() -> bool:
    """Macht die NVIDIA-DLLs für ctranslate2 auffindbar (beim App-Start)."""
    dirs = _gpu_dll_dirs()
    if not dirs:
        return False
    ok = False
    for d in dirs:
        try:
            os.add_dll_directory(d)
            # ctranslate2 sucht z. T. über PATH (LoadLibrary ohne Pfad)
            os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")
            ok = True
        except OSError:
            pass
    return ok


# ------------------------------------------------------------------ Downloads
def _open_url(url: str):
    ctx = ssl.create_default_context()
    req = urllib.request.Request(url, headers={"User-Agent": "Lyrix"})
    return urllib.request.urlopen(req, context=ctx, timeout=60)


def _pypi_wheel_url(package: str) -> tuple[str, int]:
    """Neueste win_amd64/py3-Wheel-URL eines PyPI-Pakets + Größe."""
    with _open_url(f"https://pypi.org/pypi/{package}/json") as fh:
        meta = json.load(fh)
    releases = meta["urls"]
    for entry in releases:
        name = entry["filename"]
        if name.endswith(".whl") and ("win_amd64" in name or "none-any" in name):
            return entry["url"], int(entry.get("size") or 0)
    raise RuntimeError(f"Kein Windows-Wheel für {package} gefunden")


class PackDownloadThread(QThread):
    """Lädt und installiert ein Paket mit Fortschritt.

    pack: 'gpu', 'ai' (alle KI-Komponenten) oder eine Einzel-Komponente
    ('ai_whisper' / 'ai_speakers' / 'ai_sounds' – Punkt 10). Einzel-
    Komponenten kommen aus demselben KI-Paket-Archiv; entpackt und kopiert
    wird dann nur der Teil, der laut Manifest zur Komponente gehört."""

    progress = Signal(str, float)   # Beschreibung, 0..1 (-1 = unbestimmt)
    finished_ok = Signal(str)       # Paketname
    failed = Signal(str)

    def __init__(self, pack: str, parent=None):
        super().__init__(parent)
        self.pack = pack
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        try:
            if self.pack == "gpu":
                self._install_gpu()
            elif self.pack == "ai":
                self._install_ai()
            elif self.pack in AI_COMPONENTS:
                self._install_ai(only=self.pack)
            else:
                raise ValueError(self.pack)
            self.finished_ok.emit(self.pack)
        except Exception as exc:  # noqa: BLE001
            import traceback
            traceback.print_exc(file=sys.stderr)
            if not self._cancel:
                self.failed.emit(f"{exc.__class__.__name__}: {exc}")

    # ------------------------------------------------------------------
    def _download(self, url: str, dest: str, label: str, total_hint: int = 0):
        with _open_url(url) as resp, open(dest, "wb") as out:
            total = int(resp.headers.get("Content-Length") or total_hint or 0)
            done = 0
            while True:
                if self._cancel:
                    raise RuntimeError("Abgebrochen")
                chunk = resp.read(1 << 20)
                if not chunk:
                    break
                out.write(chunk)
                done += len(chunk)
                self.progress.emit(label, done / total if total else -1.0)

    def _install_gpu(self):
        target = gpu_dir()
        os.makedirs(target, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="lyrix_gpu_") as tmp:
            for i, package in enumerate(GPU_WHEELS, start=1):
                label = f"GPU-Paket {i}/{len(GPU_WHEELS)}: {package}"
                self.progress.emit(label, -1.0)
                url, size = _pypi_wheel_url(package)
                wheel_path = os.path.join(tmp, package + ".whl")
                self._download(url, wheel_path, label, size)
                self.progress.emit(f"Entpacke {package} …", -1.0)
                # Wheels sind Zip-Archive; wir brauchen nur den nvidia/-Baum
                with zipfile.ZipFile(wheel_path) as zf:
                    for info in zf.infolist():
                        if info.filename.startswith("nvidia/"):
                            zf.extract(info, target)
        if not gpu_runtime_installed():
            raise RuntimeError("GPU-Laufzeit nach Installation nicht gefunden")
        load_gpu_runtime()

    def _fetch_ai_pack(self, archive: str):
        """Beschafft das KI-Paket-Archiv aus der ersten erreichbaren Quelle
        (lokale Kopie oder Download). Scheitern alle Quellen, gibt es eine
        verständliche Fehlermeldung mit Handlungsanleitung statt eines
        nackten HTTP-404 (Punkt 4)."""
        from .i18n import tr
        last_error: Exception | None = None
        for url in _ai_pack_sources():
            try:
                if url.startswith("file://"):
                    local = url.split("://", 1)[1].lstrip("/")
                    local = (local.replace("/", os.sep) if os.name == "nt"
                             else "/" + local)
                    shutil.copyfile(local, archive)
                else:
                    self._download(url, archive, "KI-Paket wird geladen …")
                return
            except Exception as exc:  # noqa: BLE001 - nächste Quelle probieren
                if self._cancel:
                    raise
                last_error = exc
        detail = (f"{last_error.__class__.__name__}: {last_error}"
                  if last_error else "?")
        raise RuntimeError(tr("pack_source_missing",
                              name=ai_pack_name(), err=detail))

    def _install_ai(self, only: str | None = None):
        app_dir = os.path.dirname(sys.executable)
        internal = os.path.join(app_dir, "_internal")
        if not getattr(sys, "frozen", False):
            raise RuntimeError("Nachladen ist nur in der installierten "
                               "Version möglich (im Quellcode: pip install).")

        with tempfile.TemporaryDirectory(prefix="lyrix_ai_") as tmp:
            archive = os.path.join(tmp, "ai-pack.zip")
            self._fetch_ai_pack(archive)
            self.progress.emit("KI-Paket wird entpackt …", -1.0)
            extract_dir = os.path.join(tmp, "unpacked")
            with zipfile.ZipFile(archive) as zf:
                zf.extractall(extract_dir)
            if only:
                self._prune_to_component(extract_dir, only)
            # Direkt ins Programmverzeichnis kopieren; wenn das nicht
            # beschreibbar ist (Installation für alle Benutzer), einmalig
            # mit Administratorrechten kopieren.
            try:
                shutil.copytree(extract_dir, internal, dirs_exist_ok=True)
            except PermissionError:
                self.progress.emit("Warte auf Administrator-Bestätigung …", -1.0)
                self._elevated_copy(extract_dir, internal)
        if only and not component_installed(only):
            raise RuntimeError("Komponente nach Installation nicht gefunden")
        if not ai_available():
            raise RuntimeError("KI-Paket nach Installation nicht gefunden")

    @staticmethod
    def _prune_to_component(extract_dir: str, comp: str):
        """Reduziert das entpackte KI-Paket auf die Einträge der gewünschten
        Komponente (laut mitgeliefertem Manifest); das Manifest selbst
        bleibt für spätere Verwaltung erhalten."""
        manifest = read_manifest(os.path.join(extract_dir, "ai_manifest.txt"))
        if not manifest:
            raise RuntimeError("ai_manifest.txt fehlt im KI-Paket")
        keep = {name for name, parts in manifest if comp in parts}
        keep_models = {name.split("/", 1)[1] for name in keep
                       if name.startswith("models/")}
        for entry in os.listdir(extract_dir):
            full = os.path.join(extract_dir, entry)
            if entry == "ai_manifest.txt":
                continue
            if entry == "models":
                for fname in os.listdir(full):
                    if fname not in keep_models:
                        os.remove(os.path.join(full, fname))
                if not os.listdir(full):
                    os.rmdir(full)
                continue
            if entry in keep:
                continue
            if os.path.isdir(full):
                shutil.rmtree(full)
            else:
                os.remove(full)

    @staticmethod
    def _elevated_copy(src: str, dst: str):
        import subprocess
        cmd = (f'Start-Process -Verb RunAs -Wait -WindowStyle Hidden '
               f'-FilePath robocopy -ArgumentList '
               f'\'"{src}" "{dst}" /E /NFL /NDL /NJH /NJS\'')
        rc = subprocess.run(["powershell", "-NoProfile", "-Command", cmd],
                            capture_output=True, text=True, timeout=1800)
        if rc.returncode != 0:
            raise RuntimeError("Kopieren mit Administratorrechten "
                               "fehlgeschlagen oder abgelehnt")


class PackUninstallThread(QThread):
    """Deinstalliert eine KI-Komponente ('ai_whisper' / 'ai_speakers' /
    'ai_sounds') oder das GPU-Paket ('gpu') – Punkt 10.

    Geteilte Abhängigkeiten (z. B. torch für Sprecher UND Geräusche) werden
    nur entfernt, wenn keine andere installierte Komponente sie braucht."""

    progress = Signal(str, float)
    finished_ok = Signal(str)
    failed = Signal(str)

    def __init__(self, pack: str, parent=None):
        super().__init__(parent)
        self.pack = pack

    def run(self):
        try:
            if self.pack == "gpu":
                self._uninstall_gpu()
            elif self.pack in AI_COMPONENTS:
                self._uninstall_component(self.pack)
            else:
                raise ValueError(self.pack)
            self.finished_ok.emit(self.pack)
        except Exception as exc:  # noqa: BLE001
            import traceback
            traceback.print_exc(file=sys.stderr)
            self.failed.emit(f"{exc.__class__.__name__}: {exc}")

    def _uninstall_gpu(self):
        target = gpu_dir()
        if not os.path.isdir(target):
            return
        try:
            shutil.rmtree(target)
        except OSError as exc:
            # DLLs sind nach einer GPU-Transkription noch im Prozess geladen
            raise RuntimeError(
                "GPU-Dateien sind gerade in Benutzung. Bitte Lyrix neu "
                "starten und die Deinstallation direkt danach wiederholen."
            ) from exc

    def _uninstall_component(self, comp: str):
        if not getattr(sys, "frozen", False):
            raise RuntimeError("Deinstallation einzelner Komponenten ist nur "
                               "in der installierten Version möglich.")
        names = removable_entries(comp)
        if not names:
            return
        internal = _internal_dir()
        paths = [os.path.join(internal, name.replace("/", os.sep))
                 for name in names]
        paths = [p for p in paths if os.path.exists(p)]
        leftovers: list[str] = []
        for i, path in enumerate(paths):
            self.progress.emit(f"Entferne {os.path.basename(path)} …",
                               i / max(1, len(paths)))
            try:
                if os.path.isdir(path):
                    shutil.rmtree(path)
                else:
                    os.remove(path)
            except OSError:
                leftovers.append(path)
        if leftovers:
            # Programmverzeichnis nicht beschreibbar (Installation für alle
            # Benutzer) oder Datei gesperrt -> einmalig mit Adminrechten.
            self.progress.emit("Warte auf Administrator-Bestätigung …", -1.0)
            self._elevated_delete(leftovers)
        if component_installed(comp):
            raise RuntimeError("Komponente konnte nicht vollständig entfernt "
                               "werden (Dateien in Benutzung? Bitte Lyrix "
                               "neu starten und erneut versuchen).")

    @staticmethod
    def _elevated_delete(paths: list[str]):
        import subprocess
        script = os.path.join(tempfile.gettempdir(), "lyrix_uninstall.ps1")
        with open(script, "w", encoding="utf-8-sig") as fh:
            for p in paths:
                safe = p.replace("'", "''")
                fh.write(f"Remove-Item -LiteralPath '{safe}' -Recurse -Force "
                         f"-ErrorAction SilentlyContinue\n")
        cmd = (f"Start-Process -Verb RunAs -Wait -WindowStyle Hidden "
               f"powershell -ArgumentList @('-NoProfile', "
               f"'-ExecutionPolicy', 'Bypass', '-File', '{script}')")
        rc = subprocess.run(["powershell", "-NoProfile", "-Command", cmd],
                            capture_output=True, text=True, timeout=1800)
        try:
            os.remove(script)
        except OSError:
            pass
        if rc.returncode != 0:
            raise RuntimeError("Löschen mit Administratorrechten "
                               "fehlgeschlagen oder abgelehnt")


def release_memory():
    """Gibt nach dem Deaktivieren/Deinstallieren von Komponenten belegte
    Ressourcen frei (Punkt 11): Python-Garbage-Collection, torch-Caches
    und das Working Set des Prozesses."""
    import gc
    gc.collect()
    torch = sys.modules.get("torch")
    if torch is not None:
        try:
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass
    if os.name == "nt":
        try:
            import ctypes
            handle = ctypes.windll.kernel32.GetCurrentProcess()
            ctypes.windll.psapi.EmptyWorkingSet(handle)
        except Exception:
            pass
