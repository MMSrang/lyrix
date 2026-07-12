"""Hardware-Erkennung und Wahl von Whisper-Modellgröße und Rechengerät.

GPU-Logik:
- Erkannt wird eine NVIDIA-GPU über nvidia-smi (funktioniert immer, wenn der
  Treiber installiert ist – unabhängig von torch/ctranslate2).
- Genutzt wird sie von faster-whisper (ctranslate2), sobald das optionale
  GPU-Paket (cuBLAS/cuDNN) installiert ist. torch bleibt bewusst die
  CPU-Version: Sprecher- und Geräusch-Erkennung laufen parallel auf der CPU,
  während Whisper auf der GPU rechnet.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass

from . import packs

MODEL_SIZES = ["tiny", "base", "small", "medium", "large-v3"]


@dataclass
class GpuInfo:
    name: str
    vram_gb: float


@dataclass
class ModelChoice:
    model: str
    device: str        # "cuda" | "cpu"
    compute_type: str  # "float16" | "int8_float16" | "int8"
    cpu_threads: int
    reason: str

    def label(self) -> str:
        dev = "GPU" if self.device == "cuda" else "CPU"
        return f"Whisper {self.model} · {dev} ({self.compute_type})"


def detect_nvidia() -> GpuInfo | None:
    """NVIDIA-GPU über nvidia-smi erkennen (auch ohne GPU-Paket)."""
    try:
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10, creationflags=flags)
        if out.returncode != 0 or not out.stdout.strip():
            return None
        line = out.stdout.strip().splitlines()[0]
        name, mem = [part.strip() for part in line.split(",")[:2]]
        return GpuInfo(name=name, vram_gb=float(mem) / 1024.0)
    except Exception:
        return None


def gpu_usable() -> bool:
    """GPU vorhanden UND GPU-Paket (cuBLAS/cuDNN) installiert?"""
    return packs.gpu_runtime_installed() and detect_nvidia() is not None


def _ram_gb() -> float:
    try:
        import psutil
        return psutil.virtual_memory().total / 2**30
    except Exception:
        return 8.0


def _physical_cores() -> int:
    try:
        import psutil
        return psutil.cpu_count(logical=False) or psutil.cpu_count() or 4
    except Exception:
        return os.cpu_count() or 4


def _cuda_choice(model: str | None, vram: float, threads: int,
                 reason: str) -> ModelChoice:
    if model is None:
        if vram >= 9:
            model = "large-v3"
        elif vram >= 5:
            model = "medium"
        else:
            model = "small"
    compute = "float16" if vram >= 5 else "int8_float16"
    return ModelChoice(model, "cuda", compute, threads, reason)


def _cpu_choice(model: str | None, threads: int, cores: int,
                ram: float) -> ModelChoice:
    reason = f"CPU mit {cores} Kernen, {ram:.0f} GB RAM"
    if model is None:
        if ram >= 16 and cores >= 8:
            model = "small"
        elif ram >= 8 and cores >= 4:
            model = "base"
        else:
            model = "tiny"
            reason = f"schwache Hardware: {cores} Kerne, {ram:.0f} GB RAM"
    return ModelChoice(model, "cpu", "int8", threads, reason)


def pick(model_override: str | None = "auto",
         device_override: str = "auto",
         allow_cuda: bool = True) -> ModelChoice:
    """Wählt Modell + Gerät.

    model_override : "auto" oder fester Modellname
    device_override: "auto" | "cuda" | "cpu"  (Einstellung „Rechengerät“)
    allow_cuda     : False erzwingt CPU (interner Fallback nach GPU-Fehlern)
    """
    cores = _physical_cores()
    threads = max(1, cores - 1)
    ram = _ram_gb()
    model = (model_override
             if model_override and model_override != "auto"
             and model_override in MODEL_SIZES else None)

    if device_override == "cpu":
        allow_cuda = False
    gpu = detect_nvidia() if allow_cuda else None
    runtime = packs.gpu_runtime_installed()

    if allow_cuda and gpu is not None and device_override == "cuda":
        # Ausdrücklicher Nutzerwunsch – auch ohne Paket versuchen
        # (der Transcriber fällt bei Fehlern selbstständig auf CPU zurück).
        return _cuda_choice(model, gpu.vram_gb, threads,
                            f"GPU erzwungen: {gpu.name}, {gpu.vram_gb:.0f} GB")
    if allow_cuda and gpu is not None and device_override == "auto" and runtime:
        return _cuda_choice(model, gpu.vram_gb, threads,
                            f"{gpu.name}, {gpu.vram_gb:.0f} GB VRAM")
    return _cpu_choice(model, threads, cores, ram)
