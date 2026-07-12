"""Audio-Dekodierung über PyAV (FFmpeg) – unabhängig vom Whisper-Stack.

Bewusst eigenständig statt faster_whisper.audio: Der Import von
faster_whisper zieht ctranslate2/tokenizers/onnxruntime mit – Sprecher- und
Geräusch-Erkennung sollen aber auch ohne installierte Whisper-Komponente
funktionieren (modulare Installation).
"""

from __future__ import annotations


def decode_audio(path: str, sampling_rate: int = 16000):
    """Datei -> mono float32-Numpy-Array mit gewünschter Abtastrate."""
    import av
    import numpy as np

    resampler = av.audio.resampler.AudioResampler(
        format="s16", layout="mono", rate=sampling_rate)

    chunks: list[bytes] = []
    with av.open(path, mode="r", metadata_errors="ignore") as container:
        stream = container.streams.audio[0]
        for frame in container.decode(stream):
            frame.pts = None
            for resampled in resampler.resample(frame):
                chunks.append(bytes(resampled.to_ndarray().tobytes()))
        for resampled in resampler.resample(None):  # Resampler leeren
            chunks.append(bytes(resampled.to_ndarray().tobytes()))

    pcm = np.frombuffer(b"".join(chunks), dtype=np.int16)
    return pcm.astype(np.float32) / 32768.0
