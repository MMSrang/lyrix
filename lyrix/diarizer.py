"""Hintergrund-Thread für die Sprechertrennung mit pyannote.audio.

Die Modelle (segmentation-3.0 + wespeaker-Embedding, beide MIT-lizenziert)
werden mit der Anwendung ausgeliefert und lokal geladen – es ist kein
Hugging-Face-Konto oder -Token mehr nötig. Nur wenn die gebündelten Dateien
fehlen (z. B. Quellcode-Betrieb ohne models/-Ordner), wird als Fallback die
Pipeline von Hugging Face geladen; dafür braucht es dann ein Token.

Die Pipeline wird mit den offiziellen Hyperparametern von
pyannote/speaker-diarization-3.1 aufgebaut.
"""

from __future__ import annotations

import os
import sys
import traceback

from PySide6.QtCore import QThread, Signal

from .util import resource_path

DIAR_MODEL = "pyannote/speaker-diarization-3.1"
SEG_FILE = os.path.join("models", "segmentation-3.0.bin")
EMB_FILE = os.path.join("models", "wespeaker-voxceleb-resnet34-LM.bin")

# Offizielle Hyperparameter aus der config.yaml von speaker-diarization-3.1
_PIPELINE_PARAMS = {
    "clustering": {
        "method": "centroid",
        "min_cluster_size": 12,
        "threshold": 0.7045654963945799,
    },
    "segmentation": {"min_duration_off": 0.0},
}

SPEAKER_COLORS = ["#1DB954", "#58A6FF", "#F778BA", "#FFA657",
                  "#D2A8FF", "#7EE7D8", "#FF7B72", "#E3B341"]

_LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def bundled_models_available() -> bool:
    return (os.path.exists(resource_path(SEG_FILE))
            and os.path.exists(resource_path(EMB_FILE)))


def display_names(turns: list[tuple[float, float, str]]) -> dict[str, str]:
    """Rohe pyannote-Labels (SPEAKER_00, …) -> lokalisierte Anzeige­namen
    („Person A“ / "Speaker A" / …) in der Reihenfolge des ersten Auftretens."""
    from .i18n import tr
    names: dict[str, str] = {}
    for _, _, label in sorted(turns, key=lambda t: t[0]):
        if label not in names:
            i = len(names)
            suffix = _LETTERS[i] if i < len(_LETTERS) else str(i + 1)
            names[label] = tr("speaker_name", id=suffix)
    return names


def speaker_color(names: dict[str, str], label: str) -> str:
    idx = list(names).index(label) if label in names else 0
    return SPEAKER_COLORS[idx % len(SPEAKER_COLORS)]


def speaker_for_span(turns: list[tuple[float, float, str]],
                     start: float, end: float) -> str | None:
    """Label mit der größten zeitlichen Überlappung zum Abschnitt, sonst None."""
    best, best_ov = None, 0.0
    for ts, te, label in turns:
        if te <= start:
            continue
        if ts >= end:
            break
        ov = min(end, te) - max(start, ts)
        if ov > best_ov:
            best_ov, best = ov, label
    return best


def _allow_pyannote_globals():
    """torch>=2.6 lädt mit weights_only=True nur allowgelistete Klassen.
    Die pyannote-Checkpoints brauchen genau diese vier harmlosen Typen."""
    import torch
    from pyannote.audio.core import task as pt
    torch.serialization.add_safe_globals([
        torch.torch_version.TorchVersion,
        pt.Specifications, pt.Problem, pt.Resolution,
    ])


def _load_bundled_pipeline():
    from pyannote.audio import Model
    from pyannote.audio.pipelines import SpeakerDiarization

    _allow_pyannote_globals()
    seg = Model.from_pretrained(resource_path(SEG_FILE))
    emb = Model.from_pretrained(resource_path(EMB_FILE))
    pipe = SpeakerDiarization(
        segmentation=seg,
        embedding=emb,
        embedding_exclude_overlap=True,
        clustering="AgglomerativeClustering",
        embedding_batch_size=32,
        segmentation_batch_size=32,
    )
    pipe.instantiate(_PIPELINE_PARAMS)
    return pipe


def _load_hub_pipeline(token: str | None):
    from pyannote.audio import Pipeline

    _allow_pyannote_globals()
    try:
        pipe = Pipeline.from_pretrained(DIAR_MODEL, use_auth_token=token)
    except TypeError:
        # neuere pyannote-Versionen heißen den Parameter "token"
        pipe = Pipeline.from_pretrained(DIAR_MODEL, token=token)
    if pipe is None:
        raise RuntimeError(
            "Die mitgelieferten Sprecher-Modelle fehlen und das Modell konnte "
            "nicht von Hugging Face geladen werden. Bitte in den Einstellungen "
            "ein gültiges Token hinterlegen und die Nutzungsbedingungen von "
            "pyannote/speaker-diarization-3.1 sowie pyannote/segmentation-3.0 "
            "akzeptieren.")
    return pipe


class DiarizerThread(QThread):
    status = Signal(str)
    done = Signal(list)     # [(start, end, label), ...] zeitlich sortiert
    failed = Signal(str)

    def __init__(self, path: str, hf_token: str = "", parent=None):
        super().__init__(parent)
        self._path = path
        self._token = (hf_token or "").strip()
        self._cancel = False

    def cancel(self):
        """Kooperativer Abbruch (Punkt 11): wird zwischen den Arbeitsschritten
        geprüft; die pyannote-Pipeline selbst lässt sich nicht unterbrechen,
        aber Ergebnis-Signale unterbleiben und der Thread endet danach."""
        self._cancel = True

    def run(self):
        try:
            self._run()
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc(file=sys.stderr)
            if not self._cancel:
                self.failed.emit(str(exc))

    def _run(self):
        from .i18n import tr
        self.status.emit(tr("diar_loading"))
        import torch
        from .audioio import decode_audio

        if bundled_models_available():
            pipe = _load_bundled_pipeline()
        else:
            pipe = _load_hub_pipeline(self._token or None)
        if self._cancel:
            return

        # Bewusst KEIN pipe.to(cuda): Die Sprechertrennung läuft parallel auf
        # der CPU, während Whisper (ctranslate2) die GPU nutzen darf.

        self.status.emit(tr("diar_running"))
        # Audio selbst dekodieren (PyAV) – unabhängig vom torchaudio-Backend
        wav = decode_audio(self._path, sampling_rate=16000)
        if self._cancel:
            return
        waveform = torch.from_numpy(wav).unsqueeze(0)
        annotation = pipe({"waveform": waveform, "sample_rate": 16000})
        if self._cancel:
            return

        turns = [(float(seg.start), float(seg.end), str(label))
                 for seg, _, label in annotation.itertracks(yield_label=True)]
        turns.sort(key=lambda t: t[0])
        self.done.emit(turns)
