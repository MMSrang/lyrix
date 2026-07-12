"""Optionaler Online-Songtext-Abgleich für erkannte Musik (LRCLIB).

LRCLIB (lrclib.net) ist ein offener, kostenloser Lyrics-Dienst ohne
API-Schlüssel. Bevorzugt werden zeitsynchronisierte Texte (LRC-Format) –
die ersetzen dann die Whisper-Transkription des Gesangs, die bei Musik
oft ungenau ist. Ohne Treffer bleibt Whisper der Fallback.

Nutzt denselben Datenschutz-Schalter wie die Cover-Suche (standardmäßig
AUS); übertragen werden nur Interpret/Titel bzw. der bereinigte Dateiname.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import ssl
import urllib.parse
import urllib.request

from PySide6.QtCore import QThread, Signal

from . import packs
from .covers import clean_artist_title

_GET_URL = ("https://lrclib.net/api/get?artist_name={artist}"
            "&track_name={title}")
_SEARCH_URL = "https://lrclib.net/api/search?q={query}"

_LRC_LINE = re.compile(r"\[(\d+):(\d+(?:\.\d+)?)\](.*)")


def cache_dir() -> str:
    path = os.path.join(packs.data_dir(), "lyrics")
    os.makedirs(path, exist_ok=True)
    return path


def parse_lrc(lrc: str, duration: float = 0.0) -> list[dict]:
    """LRC-Text -> Zeilen-Dicts wie vom Transcriber ({start,end,text,words})."""
    entries: list[tuple[float, str]] = []
    for raw_line in lrc.splitlines():
        match = _LRC_LINE.match(raw_line.strip())
        if not match:
            continue
        start = int(match.group(1)) * 60 + float(match.group(2))
        text = match.group(3).strip()
        if text:
            entries.append((start, text))
    entries.sort(key=lambda e: e[0])
    lines = []
    for i, (start, text) in enumerate(entries):
        if i + 1 < len(entries):
            end = entries[i + 1][0]
        else:
            end = max(start + 4.0, duration or start + 4.0)
        lines.append({"start": start, "end": end, "text": text, "words": []})
    return lines


def _fetch_json(url: str):
    ctx = ssl.create_default_context()
    req = urllib.request.Request(
        url, headers={"User-Agent": "Lyrix (https://github.com/lyrix-app)"})
    with urllib.request.urlopen(req, context=ctx, timeout=15) as fh:
        return json.load(fh)


class LyricsSearchThread(QThread):
    """Sucht zeitsynchronisierte Songtexte; liefert fertige Zeilen-Dicts."""

    found = Signal(list, str)   # Zeilen, "Interpret – Titel"
    not_found = Signal()

    def __init__(self, audio_path: str, artist: str = "", title: str = "",
                 duration: float = 0.0, parent=None):
        super().__init__(parent)
        self._path = audio_path
        self._artist = artist
        self._title = title
        self._duration = duration

    def run(self):
        try:
            artist, title = clean_artist_title(self._path, self._artist,
                                               self._title)
            if not title:
                self.not_found.emit()
                return
            key_src = f"{artist}|{title}".lower()
            key = hashlib.sha1(key_src.encode("utf-8")).hexdigest()[:20]
            cached = os.path.join(cache_dir(), key + ".lrc")
            synced = ""
            display = f"{artist} – {title}" if artist else title
            if os.path.exists(cached):
                with open(cached, encoding="utf-8") as fh:
                    synced = fh.read()
            else:
                record = self._lookup(artist, title)
                if record:
                    synced = record.get("syncedLyrics") or ""
                    r_artist = record.get("artistName") or artist
                    r_title = record.get("trackName") or title
                    display = f"{r_artist} – {r_title}"
                if synced:
                    with open(cached, "w", encoding="utf-8") as fh:
                        fh.write(synced)
            if not synced:
                self.not_found.emit()
                return
            lines = parse_lrc(synced, self._duration)
            if len(lines) >= 4:
                self.found.emit(lines, display)
            else:
                self.not_found.emit()
        except Exception:
            self.not_found.emit()

    def _lookup(self, artist: str, title: str) -> dict | None:
        if artist:
            try:
                record = _fetch_json(_GET_URL.format(
                    artist=urllib.parse.quote(artist),
                    title=urllib.parse.quote(title)))
                if record.get("syncedLyrics"):
                    return record
            except Exception:
                pass  # 404 bei fehlendem Treffer -> Suche versuchen
        query = urllib.parse.quote(f"{artist} {title}".strip())
        try:
            results = _fetch_json(_SEARCH_URL.format(query=query))
        except Exception:
            return None
        for record in results or []:
            if record.get("syncedLyrics"):
                return record
        return None
