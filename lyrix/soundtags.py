"""Geräusch- und Musik-Erkennung mit PANNs CNN14 (AudioSet, 527 Klassen).

Eigenständige CNN14-Implementierung (nur torch) – die STFT-Kernel und die
Mel-Filterbank stecken als Gewichte im Checkpoint, dadurch ist das Frontend
bitgenau ohne librosa/torchlibrosa reproduziert. Nicht-gesprochene Abschnitte
werden als Tags wie "[Musik]", "[Applaus]", "[Lachen]" gemeldet.

Checkpoint: Cnn14_16k (Kong et al., "PANNs", Apache-2.0, Zenodo 3987831),
einmalig zu reinen Tensoren konvertiert (lädt mit weights_only=True).
"""

from __future__ import annotations

import csv
import os
import sys
import traceback

from PySide6.QtCore import QThread, Signal

from .util import resource_path

SR = 16000
WINDOW_SEC = 4.0
HOP_SEC = 2.0
BATCH = 8

TAG_MIN_PROB = 0.30      # Mindest-Score für einen Geräusch-Tag
SPEECH_MAX_PROB = 0.30   # Fenster mit mehr Sprach-Score bekommen keinen Tag

MODEL_FILE = os.path.join("models", "cnn14_16k.pt")
LABELS_FILE = os.path.join("models", "audioset_labels.csv")

# AudioSet-Klassen, die nie als Tag gezeigt werden (Sprache/Meta/zu generisch)
_EXCLUDE = {
    "Speech", "Male speech, man speaking", "Female speech, woman speaking",
    "Child speech, kid speaking", "Conversation", "Narration, monologue",
    "Speech synthesizer", "Babbling", "Inside, small room",
    "Inside, large room or hall", "Inside, public space", "Outside, urban or manmade",
    "Outside, rural or natural", "Silence", "Sound effect", "Field recording",
    "Human voice", "Male singing", "Female singing", "Child singing",
}

# Deutsche Anzeigenamen für häufige AudioSet-Klassen; unbekannte Klassen
# erscheinen mit ihrem englischen Namen.
GERMAN = {
    "Music": "Musik", "Musical instrument": "Musik", "Singing": "Gesang",
    "Choir": "Chor", "Humming": "Summen", "Whistling": "Pfeifen",
    "Guitar": "Gitarre", "Acoustic guitar": "Gitarre", "Electric guitar": "E-Gitarre",
    "Piano": "Klavier", "Electric piano": "E-Piano", "Keyboard (musical)": "Keyboard",
    "Organ": "Orgel", "Synthesizer": "Synthesizer", "Drum": "Schlagzeug",
    "Drum kit": "Schlagzeug", "Percussion": "Percussion", "Violin, fiddle": "Geige",
    "Cello": "Cello", "Trumpet": "Trompete", "Saxophone": "Saxofon",
    "Flute": "Flöte", "Harmonica": "Mundharmonika", "Accordion": "Akkordeon",
    "Music box": "Spieluhr", "Bell": "Glocke", "Church bell": "Kirchenglocke",
    "Jingle bell": "Schelle", "Wind chime": "Windspiel", "Chime": "Glockenspiel",
    "Applause": "Applaus", "Clapping": "Klatschen", "Cheering": "Jubel",
    "Crowd": "Menschenmenge", "Chatter": "Stimmengewirr",
    "Laughter": "Lachen", "Giggle": "Kichern", "Chuckle, chortle": "Lachen",
    "Crying, sobbing": "Weinen", "Baby cry, infant cry": "Babyweinen",
    "Cough": "Husten", "Sneeze": "Niesen", "Snoring": "Schnarchen",
    "Breathing": "Atmen", "Whispering": "Flüstern", "Sigh": "Seufzen",
    "Walk, footsteps": "Schritte", "Run": "Laufen",
    "Door": "Tür", "Knock": "Klopfen", "Doorbell": "Türklingel",
    "Slam": "Türknallen", "Squeak": "Quietschen",
    "Telephone": "Telefon", "Telephone bell ringing": "Telefonklingeln",
    "Ringtone": "Klingelton", "Telephone dialing, DTMF": "Wähltöne",
    "Alarm": "Alarm", "Alarm clock": "Wecker", "Siren": "Sirene",
    "Smoke detector, smoke alarm": "Rauchmelder", "Buzzer": "Summer",
    "Beep, bleep": "Piepton", "Sine wave": "Ton",
    "Glass": "Glas", "Shatter": "Glas zerbricht", "Breaking": "Zerbrechen",
    "Gunshot, gunfire": "Schuss", "Explosion": "Explosion", "Fireworks": "Feuerwerk",
    "Dog": "Hund", "Bark": "Hundebellen", "Growling": "Knurren",
    "Cat": "Katze", "Meow": "Miauen", "Purr": "Schnurren",
    "Bird": "Vogel", "Bird vocalization, bird call, bird song": "Vogelgezwitscher",
    "Chirp, tweet": "Zwitschern", "Crow": "Krähe", "Rooster": "Hahn",
    "Insect": "Insekt", "Bee, wasp, etc.": "Bienensummen",
    "Water": "Wasser", "Rain": "Regen", "Raindrop": "Regentropfen",
    "Thunder": "Donner", "Thunderstorm": "Gewitter", "Wind": "Wind",
    "Stream": "Wasserlauf", "Waterfall": "Wasserfall", "Waves, surf": "Meeresrauschen",
    "Fire": "Feuer", "Crackle": "Knistern",
    "Vehicle": "Fahrzeug", "Car": "Auto", "Car passing by": "Vorbeifahrendes Auto",
    "Engine": "Motor", "Motorcycle": "Motorrad", "Truck": "LKW", "Bus": "Bus",
    "Train": "Zug", "Aircraft": "Flugzeug", "Helicopter": "Hubschrauber",
    "Bicycle": "Fahrrad", "Car alarm": "Autoalarm", "Air horn, truck horn": "Hupe",
    "Vehicle horn, car horn, honking": "Hupe", "Traffic noise, roadway noise": "Verkehrslärm",
    "Typing": "Tippen", "Computer keyboard": "Tastatur", "Typewriter": "Schreibmaschine",
    "Printer": "Drucker", "Camera": "Kamera",
    "Microwave oven": "Mikrowelle", "Blender": "Mixer",
    "Vacuum cleaner": "Staubsauger", "Frying (food)": "Braten",
    "Chopping (food)": "Schneiden", "Dishes, pots, and pans": "Geschirrklappern",
    "Cutlery, silverware": "Besteck", "Chewing, mastication": "Kauen",
    "Toilet flush": "Toilettenspülung", "Shower": "Dusche",
    "Clock": "Uhr", "Tick-tock": "Ticken",
    "Horse": "Pferd", "Cattle, bovinae": "Rinder", "Pig": "Schwein",
    "Sheep": "Schaf", "Frog": "Frosch",
}


def model_available() -> bool:
    return (os.path.exists(resource_path(MODEL_FILE))
            and os.path.exists(resource_path(LABELS_FILE)))


def load_labels() -> list[str]:
    with open(resource_path(LABELS_FILE), encoding="utf-8") as fh:
        return [row["display_name"] for row in csv.DictReader(fh)]


def display_tag(label: str) -> str:
    from .i18n import tag_display
    return tag_display(label, GERMAN.get(label))


# ------------------------------------------------------------------ Modell
def _build_model():
    import torch
    from torch import nn
    import torch.nn.functional as F

    class _Stft(nn.Module):
        def __init__(self):
            super().__init__()
            # Fourier-Basis * Hann-Fenster, kommt fertig aus dem Checkpoint
            self.conv_real = nn.Conv1d(1, 257, 512, stride=160, bias=False)
            self.conv_imag = nn.Conv1d(1, 257, 512, stride=160, bias=False)

    class _Spectrogram(nn.Module):
        def __init__(self):
            super().__init__()
            self.stft = _Stft()

        def forward(self, x):  # (B, N) -> Leistungsspektrum (B, 257, T)
            x = x.unsqueeze(1)
            x = F.pad(x, (256, 256), mode="reflect")
            return self.stft.conv_real(x) ** 2 + self.stft.conv_imag(x) ** 2

    class _Logmel(nn.Module):
        def __init__(self):
            super().__init__()
            self.melW = nn.Parameter(torch.empty(257, 64), requires_grad=False)

        def forward(self, spec):  # (B, 257, T) -> (B, T, 64)
            import torch as _t
            mel = spec.transpose(1, 2) @ self.melW
            return 10.0 * _t.log10(_t.clamp(mel, min=1e-10))

    class _ConvBlock(nn.Module):
        def __init__(self, cin, cout):
            super().__init__()
            self.conv1 = nn.Conv2d(cin, cout, 3, padding=1, bias=False)
            self.conv2 = nn.Conv2d(cout, cout, 3, padding=1, bias=False)
            self.bn1 = nn.BatchNorm2d(cout)
            self.bn2 = nn.BatchNorm2d(cout)

        def forward(self, x, pool=(2, 2)):
            x = F.relu_(self.bn1(self.conv1(x)))
            x = F.relu_(self.bn2(self.conv2(x)))
            if pool != (1, 1):
                x = F.avg_pool2d(x, pool)
            return x

    class Cnn14(nn.Module):
        def __init__(self):
            super().__init__()
            self.spectrogram_extractor = _Spectrogram()
            self.logmel_extractor = _Logmel()
            self.bn0 = nn.BatchNorm2d(64)
            self.conv_block1 = _ConvBlock(1, 64)
            self.conv_block2 = _ConvBlock(64, 128)
            self.conv_block3 = _ConvBlock(128, 256)
            self.conv_block4 = _ConvBlock(256, 512)
            self.conv_block5 = _ConvBlock(512, 1024)
            self.conv_block6 = _ConvBlock(1024, 2048)
            self.fc1 = nn.Linear(2048, 2048)
            self.fc_audioset = nn.Linear(2048, 527)

        def forward(self, wav):  # (B, N) -> Klassen-Wahrscheinlichkeiten (B, 527)
            import torch as _t
            x = self.logmel_extractor(self.spectrogram_extractor(wav))
            x = x.unsqueeze(1)                     # (B, 1, T, 64)
            x = self.bn0(x.transpose(1, 3)).transpose(1, 3)
            for block in (self.conv_block1, self.conv_block2, self.conv_block3,
                          self.conv_block4, self.conv_block5):
                x = block(x)
            x = self.conv_block6(x, pool=(1, 1))
            x = _t.mean(x, dim=3)
            x = _t.max(x, dim=2).values + _t.mean(x, dim=2)
            x = F.relu_(self.fc1(x))
            return _t.sigmoid(self.fc_audioset(x))

    return Cnn14()


def load_model():
    import torch
    model = _build_model()
    sd = torch.load(resource_path(MODEL_FILE), map_location="cpu",
                    weights_only=True)
    sd = {k: (v.float() if v.is_floating_point() else v) for k, v in sd.items()}
    model.load_state_dict(sd, strict=True)
    model.eval()
    for p in model.parameters():
        p.requires_grad_(False)
    return model


# ------------------------------------------------------------------ Thread
class SoundTagThread(QThread):
    """Fährt mit 4-s-Fenstern (2 s Versatz) über die Datei und meldet
    zusammengefasste Geräusch-Ereignisse."""

    status = Signal(str)
    tag_ready = Signal(dict)   # {"start","end","text","label","prob"}
    done = Signal(list)
    failed = Signal(str)

    def __init__(self, path: str, parent=None):
        super().__init__(parent)
        self._path = path
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        try:
            self._run()
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc(file=sys.stderr)
            if not self._cancel:
                self.failed.emit(f"{exc.__class__.__name__}: {exc}")

    def _run(self):
        import numpy as np
        import torch

        from .i18n import tr
        self.status.emit(tr("tags_loading"))
        labels = load_labels()
        speech_idx = labels.index("Speech")
        model = load_model()

        from .audioio import decode_audio
        wav = decode_audio(self._path, sampling_rate=SR)
        if self._cancel:
            return
        total = len(wav) / SR
        win = int(WINDOW_SEC * SR)
        hop = int(HOP_SEC * SR)
        if len(wav) < SR:  # unter 1 s gibt es nichts Sinnvolles zu taggen
            self.done.emit([])
            return

        self.status.emit(tr("tags_running"))
        starts = list(range(0, max(1, len(wav) - win // 2), hop))
        events: list[dict] = []
        current: dict | None = None

        with torch.inference_mode():
            for i in range(0, len(starts), BATCH):
                if self._cancel:
                    return
                chunk_starts = starts[i:i + BATCH]
                batch = np.stack([
                    np.pad(wav[s:s + win], (0, max(0, win - len(wav[s:s + win]))))
                    for s in chunk_starts
                ])
                probs = model(torch.from_numpy(batch)).numpy()
                for s, p in zip(chunk_starts, probs):
                    t0, t1 = s / SR, min((s + win) / SR, total)
                    tag = self._pick_tag(labels, speech_idx, p)
                    if tag is None:
                        current = self._flush(current, events)
                        continue
                    name, prob = tag
                    if current is not None and current["label"] == name:
                        current["end"] = t1
                        current["prob"] = max(current["prob"], prob)
                    else:
                        current = self._flush(current, events)
                        current = {"start": t0, "end": t1, "label": name,
                                   "prob": prob}
        self._flush(current, events)
        self.done.emit(events)

    def _pick_tag(self, labels, speech_idx, probs):
        if probs[speech_idx] > SPEECH_MAX_PROB:
            return None
        order = probs.argsort()[::-1]
        for idx in order[:5]:
            name = labels[idx]
            if name in _EXCLUDE:
                continue
            if probs[idx] < TAG_MIN_PROB:
                return None
            return name, float(probs[idx])
        return None

    def _flush(self, current, events):
        if current is not None:
            event = {
                "start": round(current["start"], 2),
                "end": round(current["end"], 2),
                "label": current["label"],
                "text": f"[{display_tag(current['label'])}]",
                "prob": round(current["prob"], 3),
            }
            events.append(event)
            self.tag_ready.emit(event)
        return None
