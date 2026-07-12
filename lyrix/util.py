"""Kleine Helfer: Ressourcen-Pfade und Zeitformatierung."""

import os
import sys


def resource_path(rel: str) -> str:
    """Pfad zu mitgelieferten Dateien – funktioniert im Quellcode-Betrieb und in der
    mit PyInstaller gepackten EXE (dort liegt alles unter sys._MEIPASS)."""
    base = getattr(sys, "_MEIPASS", None)
    if base is None:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)


def fmt_time(seconds: float) -> str:
    """Sekunden -> "m:ss" bzw. "h:mm:ss"."""
    if seconds is None or seconds < 0:
        seconds = 0
    s = int(round(seconds))
    h, rest = divmod(s, 3600)
    m, sec = divmod(rest, 60)
    if h:
        return f"{h}:{m:02d}:{sec:02d}"
    return f"{m}:{sec:02d}"


def fmt_srt_time(seconds: float) -> str:
    """Sekunden -> SRT-Zeitstempel "HH:MM:SS,mmm"."""
    if seconds is None or seconds < 0:
        seconds = 0
    ms = int(round(seconds * 1000))
    h, rest = divmod(ms, 3_600_000)
    m, rest = divmod(rest, 60_000)
    s, ms = divmod(rest, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
