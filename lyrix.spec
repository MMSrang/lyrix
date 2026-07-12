# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller-Spezifikation für Lyrix (onedir + windowed)."""

from PyInstaller.utils.hooks import collect_all, copy_metadata

datas = [
    ("assets/icon.ico", "assets"),
    ("assets/tb_prev.ico", "assets"),
    ("assets/tb_play.ico", "assets"),
    ("assets/tb_pause.ico", "assets"),
    ("assets/tb_next.ico", "assets"),
    # Gebündelte Modelle: Sprechertrennung (pyannote, MIT) und
    # Geräusch-Erkennung (PANNs CNN14, Apache-2.0)
    ("models/segmentation-3.0.bin", "models"),
    ("models/wespeaker-voxceleb-resnet34-LM.bin", "models"),
    ("models/cnn14_16k.pt", "models"),
    ("models/audioset_labels.csv", "models"),
]
binaries = []
hiddenimports = []

# Pakete, deren Daten/Submodule vollständig eingesammelt werden müssen
for pkg in [
    "faster_whisper",        # enthält u. a. das Silero-VAD-Modell (assets/)
    "pyannote.audio",
    "pyannote.core",
    "pyannote.database",
    "pyannote.metrics",
    "pyannote.pipeline",
    "asteroid_filterbanks",
    "pytorch_metric_learning",
    "torchaudio",
    "lightning_fabric",
    "pytorch_lightning",
    "lightning",
    "speechbrain",
]:
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception:
        pass  # Paket nicht installiert (z. B. speechbrain) – dann egal

# Versionsmetadaten, die zur Laufzeit per importlib.metadata abgefragt werden
for meta in [
    "torch", "torchaudio", "lightning", "pytorch-lightning", "lightning-fabric",
    "pyannote.audio", "pyannote.core", "pyannote.database", "pyannote.metrics",
    "pyannote.pipeline", "huggingface-hub", "omegaconf", "rich",
    "asteroid-filterbanks", "pytorch-metric-learning", "einops", "soundfile",
    "faster-whisper", "ctranslate2", "onnxruntime", "numpy", "scipy",
    "scikit-learn", "optuna", "tqdm", "requests", "filelock", "packaging",
    "typing-extensions", "av",
]:
    try:
        datas += copy_metadata(meta)
    except Exception:
        pass

hiddenimports += [
    "lyrix",
    "PySide6.QtMultimedia",
    # Windows-Medienintegration
    "comtypes",
    "comtypes.client",
    "winrt.windows.foundation",
    "winrt.windows.foundation.collections",
    "winrt.windows.media",
    "winrt.windows.media.playback",
    "winrt.windows.storage",
    "winrt.windows.storage.streams",
    "winrt.system",
]

for pkg in ["winrt"]:
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception:
        pass

a = Analysis(
    ["launcher.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # matplotlib NICHT ausschließen: pyannote.audio.tasks importiert es hart.
    excludes=["tkinter", "IPython", "jupyter", "PyQt5", "PyQt6"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Lyrix",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon="assets/icon.ico",
)

# Zweite EXE mit Konsole für Fehlersuche (gleiches Bundle, sichtbare Tracebacks)
exe_debug = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Lyrix-Debug",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    icon="assets/icon.ico",
)

coll = COLLECT(
    exe,
    exe_debug,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="Lyrix",
)
