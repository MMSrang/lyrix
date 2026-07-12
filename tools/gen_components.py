"""Teilt die PyInstaller-Ausgabe (dist/Lyrix) in Installer-Komponenten auf.

Komponenten:
  core        Kern-Player (fest)
  ai_whisper  Transkription (faster-whisper/ctranslate2)
  ai_speakers Sprechertrennung (pyannote + torch-Stack)
  ai_sounds   Geräusch-Erkennung (PANNs, braucht torch)

Geteilte Abhängigkeiten (torch, numpy, huggingface_hub, …) bekommen
Oder-Ausdrücke ("ai_speakers or ai_sounds"), sodass Inno sie installiert,
sobald mindestens eine betroffene Komponente gewählt ist.

Erzeugt:
- build/components_files.iss                     [Files]-Zeilen für Inno
- build/components_sizes.iss                     Gruppengrößen (MB) für die
  korrekte Speicherplatz-Anzeige im Installer (geteilte Gruppen einmal zählen)
- build/ai_manifest.txt                          KI-Einträge + Zuordnung
  (wird mit installiert: Grundlage für Einzel-Deinstallation in den
  Einstellungen; Modelldateien als "models/<name>"-Zeilen enthalten)
- installer_out/lyrix-ai-pack-<version>.zip      komplettes KI-Paket
  (In-App-Nachladen; GitHub-Release-Asset; enthält ai_manifest.txt)
"""

from __future__ import annotations

import os
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(ROOT, "dist", "Lyrix")
INTERNAL = os.path.join(DIST, "_internal")

sys.path.insert(0, ROOT)
from lyrix import __version__  # noqa: E402

W = "ai_whisper"
S = "ai_speakers"
N = "ai_sounds"
TORCH = f"{S} or {N}"                 # torch-Stack: Sprecher ODER Geräusche
HUB = f"{W} or {S}"                   # Hugging-Face-Hub: Modell-Downloads
ANY_AI = f"{W} or {S} or {N}"         # Audio-Dekodierung / numpy

# Top-Level-Namen in _internal -> Komponenten-Ausdruck
AI_GROUPS: dict[str, str] = {
    # Whisper / CTranslate2
    "ctranslate2": W, "faster_whisper": W, "onnxruntime": W,
    "tokenizers": W, "regex": W,
    # torch-Kern (inkl. seiner Pflicht-Abhängigkeiten)
    "torch": TORCH, "torchgen": TORCH, "functorch": TORCH,
    "sympy": TORCH, "networkx": TORCH, "mpmath": TORCH,
    # pyannote-Stack (nur Sprechertrennung)
    "pyannote": S, "torchaudio": S, "lightning": S, "pytorch_lightning": S,
    "lightning_fabric": S, "lightning_utilities": S, "torchmetrics": S,
    "torch_audiomentations": S, "torch_pitch_shift": S, "speechbrain": S,
    "julius": S, "asteroid_filterbanks": S, "pytorch_metric_learning": S,
    "primepy": S, "semver": S, "omegaconf": S, "soundfile": S,
    "_soundfile_data": S, "optuna": S, "alembic": S, "sqlalchemy": S,
    "colorlog": S, "hyperpyyaml": S, "ruamel": S, "sklearn": S, "scipy": S,
    "pandas": S, "matplotlib": S, "matplotlib_inline": S, "joblib": S,
    "threadpoolctl": S, "kiwisolver": S, "pillow": S, "pil": S,
    "contourpy": S, "cycler": S, "fonttools": S, "pyparsing": S,
    "dateutil": S, "pytz": S, "tzdata": S, "einops": S, "docopt": S,
    "tabulate": S, "rich": S, "markdown_it": S, "mdurl": S, "pygments": S,
    # Hugging-Face-Hub (Whisper-Downloads + pyannote-Fallback)
    "huggingface_hub": HUB, "hf_xet": HUB, "requests": HUB, "urllib3": HUB,
    "certifi": HUB, "idna": HUB, "charset_normalizer": HUB,
    "safetensors": HUB, "tqdm": HUB, "yaml": HUB, "_yaml": HUB,
    # Von mehreren Stacks gebraucht
    "av": ANY_AI, "numpy": ANY_AI, "filelock": ANY_AI, "fsspec": ANY_AI,
}

# Modelldateien einzeln zuordnen
MODEL_FILES: dict[str, str] = {
    "segmentation-3.0.bin": S,
    "wespeaker-voxceleb-resnet34-LM.bin": S,
    "cnn14_16k.pt": N,
    "audioset_labels.csv": N,
}


def _top_name(entry: str) -> str:
    base = entry
    for suffix in (".dll", ".pyd", ".py"):
        if base.lower().endswith(suffix):
            base = base[: -len(suffix)]
    for sep in (".", "-"):
        if sep in base:
            base = base.split(sep)[0]
    return base.lower()


def classify() -> dict[str, str]:
    """entry -> Komponenten-Ausdruck ("core" für den Kern)."""
    mapping: dict[str, str] = {}
    for entry in sorted(os.listdir(INTERNAL)):
        if entry == "models":
            continue  # wird dateiweise zugeordnet
        name = _top_name(entry)
        mapping[entry] = AI_GROUPS.get(name) or AI_GROUPS.get(
            entry.lower()) or "core"
    return mapping


def _dir_size(path: str) -> int:
    if os.path.isfile(path):
        return os.path.getsize(path)
    total = 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            total += os.path.getsize(os.path.join(root, name))
    return total


def write_iss(mapping: dict[str, str]) -> str:
    lines = ["; AUTOMATISCH ERZEUGT von tools/gen_components.py – nicht von Hand ändern",
             "[Files]"]
    for entry in sorted(os.listdir(DIST)):
        if entry == "_internal":
            continue
        lines.append(
            f'Source: "dist\\Lyrix\\{entry}"; DestDir: "{{app}}"; '
            f'Flags: ignoreversion; Components: core')
    for entry, comp in mapping.items():
        src = os.path.join(INTERNAL, entry)
        if os.path.isdir(src):
            lines.append(
                f'Source: "dist\\Lyrix\\_internal\\{entry}\\*"; '
                f'DestDir: "{{app}}\\_internal\\{entry}"; '
                f'Flags: recursesubdirs ignoreversion; Components: {comp}')
        else:
            lines.append(
                f'Source: "dist\\Lyrix\\_internal\\{entry}"; '
                f'DestDir: "{{app}}\\_internal"; '
                f'Flags: ignoreversion; Components: {comp}')
    for fname, comp in MODEL_FILES.items():
        if os.path.exists(os.path.join(INTERNAL, "models", fname)):
            lines.append(
                f'Source: "dist\\Lyrix\\_internal\\models\\{fname}"; '
                f'DestDir: "{{app}}\\_internal\\models"; '
                f'Flags: ignoreversion; Components: {comp}')
    # Manifest mitliefern: die App braucht es für die Einzel-Verwaltung
    # (Installieren/Deinstallieren je KI-Komponente) in den Einstellungen.
    lines.append(
        'Source: "build\\ai_manifest.txt"; DestDir: "{app}\\_internal"; '
        'Flags: ignoreversion; Components: core')
    out = os.path.join(ROOT, "build", "components_files.iss")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8-sig") as fh:
        fh.write("\n".join(lines) + "\n")
    return out


def write_ai_pack(mapping: dict[str, str]) -> str:
    out_dir = os.path.join(ROOT, "installer_out")
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, f"lyrix-ai-pack-{__version__}.zip")
    entries = [e for e, c in mapping.items() if c != "core"] + ["models"]
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        manifest = os.path.join(ROOT, "build", "ai_manifest.txt")
        if os.path.exists(manifest):
            zf.write(manifest, "ai_manifest.txt")
        for entry in entries:
            src = os.path.join(INTERNAL, entry)
            if os.path.isfile(src):
                zf.write(src, entry)
                continue
            for root, _dirs, files in os.walk(src):
                for name in files:
                    full = os.path.join(root, name)
                    zf.write(full, os.path.relpath(full, INTERNAL))
    return out


def write_sizes_iss(sizes: dict[str, float]) -> str:
    """Gruppengrößen als #define-Konstanten für installer.iss.

    Inno zählt Dateien mit Oder-Ausdrücken ("ai_speakers or ai_sounds") in
    JEDER genannten Komponente – die eingebaute Speicherplatz-Summe ist bei
    Mehrfachauswahl deshalb um Hunderte MB zu hoch. installer.iss rechnet die
    Summe darum selbst; hier kommen die Bausteine (MB, einmal je Gruppe)."""
    def mb(expr: str) -> int:
        return int(round(sizes.get(expr, 0) / 1048576))
    lines = [
        "; AUTOMATISCH ERZEUGT von tools/gen_components.py – nicht von Hand ändern",
        f"#define SizeCoreMB {mb('core')}",
        f"#define SizeWhisperMB {mb(W)}",
        f"#define SizeSpeakersMB {mb(S)}",
        f"#define SizeSoundsMB {mb(N)}",
        f"#define SizeTorchSharedMB {mb(TORCH)}",
        f"#define SizeHubSharedMB {mb(HUB)}",
        f"#define SizeAnyAiSharedMB {mb(ANY_AI)}",
    ]
    out = os.path.join(ROOT, "build", "components_sizes.iss")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8-sig") as fh:
        fh.write("\n".join(lines) + "\n")
    return out


def main():
    if not os.path.isdir(INTERNAL):
        raise SystemExit("dist/Lyrix fehlt – erst PyInstaller laufen lassen")
    mapping = classify()

    manifest = os.path.join(ROOT, "build", "ai_manifest.txt")
    os.makedirs(os.path.dirname(manifest), exist_ok=True)
    with open(manifest, "w", encoding="utf-8") as fh:
        for entry, comp in mapping.items():
            if comp != "core":
                fh.write(f"{entry}\t{comp}\n")
        for fname, comp in MODEL_FILES.items():
            if os.path.exists(os.path.join(INTERNAL, "models", fname)):
                fh.write(f"models/{fname}\t{comp}\n")

    sizes: dict[str, float] = {}
    for entry in os.listdir(DIST):
        if entry != "_internal":  # Lyrix.exe & Co. gehören zum Kern
            sizes["core"] = sizes.get("core", 0) + _dir_size(
                os.path.join(DIST, entry))
    for entry, comp in mapping.items():
        sizes[comp] = sizes.get(comp, 0) + _dir_size(
            os.path.join(INTERNAL, entry))
    for fname, comp in MODEL_FILES.items():
        path = os.path.join(INTERNAL, "models", fname)
        if os.path.exists(path):
            sizes[comp] = sizes.get(comp, 0) + os.path.getsize(path)
    print("Größen nach Komponenten-Ausdruck:")
    for comp, size in sorted(sizes.items(), key=lambda kv: -kv[1]):
        print(f"  {size / 1e6:8.1f} MB  {comp}")
    # Effektive Installationsgrößen je Einzel-Auswahl
    def eff(*names):
        total = 0
        for comp, size in sizes.items():
            if comp == "core":
                continue
            parts = [p.strip() for p in comp.split(" or ")]
            if any(n in parts for n in names):
                total += size
        return total / 1e6
    print(f"\nEffektiv: nur Whisper  {eff(W):7.1f} MB")
    print(f"Effektiv: nur Sprecher {eff(S):7.1f} MB")
    print(f"Effektiv: nur Geräusche{eff(N):7.1f} MB")
    print(f"Effektiv: alle drei    {eff(W, S, N):7.1f} MB")

    print("ISS  :", write_iss(mapping))
    print("Sizes:", write_sizes_iss(sizes))
    if "--no-zip" not in sys.argv:
        print("Pack :", write_ai_pack(mapping))

    print("\nGroße Kern-Einträge (Kontrolle auf KI-Reste):")
    for entry, comp in mapping.items():
        if comp == "core":
            size = _dir_size(os.path.join(INTERNAL, entry))
            if size > 3e6:
                print(f"  {size / 1e6:8.1f} MB  {entry}")


if __name__ == "__main__":
    main()
