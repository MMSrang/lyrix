"""Optionale Online-Cover-Suche (iTunes Search API, standardmäßig AUS).

Sucht anhand von Metadaten (Interpret/Titel) oder des bereinigten Dateinamens
nach einem Album-Cover und cached das Ergebnis unter
%LOCALAPPDATA%\\Lyrix\\covers. Es werden keine Audiodaten übertragen –
nur der Suchbegriff.
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

_SEARCH_URL = ("https://itunes.apple.com/search?term={term}"
               "&media=music&entity=song&limit=3")

# Typischer YouTube-/Rip-Müll in Titeln und Dateinamen
_NOISE_WORDS = (
    r"official", r"video", r"audio", r"music", r"lyrics?", r"lyric",
    r"visualizer", r"remaster(?:ed)?", r"hd", r"4k", r"hq", r"live",
    r"mv", r"m/v", r"topic", r"full", r"version", r"clip", r"officiel",
    r"videoclip", r"premiere",
)


def _strip_noise(text: str) -> str:
    # Klammer-Inhalte komplett entfernen: "(U.S. Official Video)", "[HD]" …
    text = re.sub(r"[\(\[\{][^\)\]\}]*[\)\]\}]", " ", text)
    # Kanal-Namen wie "FalcoVEVO", "XyzVEVO"
    text = re.sub(r"\b\w*vevo\b", " ", text, flags=re.IGNORECASE)
    # Einzelne Füllwörter
    for word in _NOISE_WORDS:
        text = re.sub(rf"\b{word}\b", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"[_|•·]+", " ", text)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip(" -–—.").strip()


def clean_artist_title(path: str, artist: str = "",
                       title: str = "") -> tuple[str, str]:
    """Bestmögliches (Interpret, Titel)-Paar aus Metadaten oder Dateinamen.

    Liefert ("", "Suchbegriff") wenn keine saubere Trennung möglich ist.
    """
    artist = _strip_noise(artist or "")
    title = _strip_noise(title or "")
    if artist and title:
        return artist, title

    stem = os.path.splitext(os.path.basename(path))[0]
    stem = re.sub(r"^\s*\d{1,3}\s*[.–-]\s*", "", stem)  # Tracknummer vorne
    stem = _strip_noise(stem)
    # "Interpret - Titel [- Restmüll]" -> an Bindestrichen trennen
    parts = [p.strip() for p in re.split(r"\s[-–—]\s", stem) if p.strip()]
    if title and not artist:
        return (parts[0], title) if parts else ("", title)
    if len(parts) >= 2:
        return parts[0], parts[1]
    return "", stem


def build_query(path: str, artist: str = "", title: str = "") -> str:
    a, t = clean_artist_title(path, artist, title)
    return f"{a} {t}".strip()


def cache_dir() -> str:
    path = os.path.join(packs.data_dir(), "covers")
    os.makedirs(path, exist_ok=True)
    return path


class CoverSearchThread(QThread):
    """Liefert den Pfad einer Cover-Bilddatei (Cache oder iTunes)."""

    found = Signal(str)      # Pfad zur Bilddatei
    not_found = Signal()

    def __init__(self, audio_path: str, artist: str = "", title: str = "",
                 parent=None):
        super().__init__(parent)
        self._path = audio_path
        self._artist = artist
        self._title = title

    def run(self):
        try:
            query = build_query(self._path, self._artist, self._title)
            if len(query) < 3:
                self.not_found.emit()
                return
            key = hashlib.sha1(query.lower().encode("utf-8")).hexdigest()[:20]
            cached = os.path.join(cache_dir(), key + ".jpg")
            if os.path.exists(cached):
                self.found.emit(cached)
                return
            ctx = ssl.create_default_context()
            url = _SEARCH_URL.format(term=urllib.parse.quote(query))
            req = urllib.request.Request(url, headers={"User-Agent": "Lyrix"})
            with urllib.request.urlopen(req, context=ctx, timeout=15) as fh:
                data = json.load(fh)
            art = ""
            for result in data.get("results") or []:
                art = result.get("artworkUrl100") or ""
                if art:
                    break
            if not art:
                self.not_found.emit()
                return
            art = art.replace("100x100", "600x600")
            req = urllib.request.Request(art, headers={"User-Agent": "Lyrix"})
            with urllib.request.urlopen(req, context=ctx, timeout=20) as fh:
                blob = fh.read()
            with open(cached, "wb") as out:
                out.write(blob)
            self.found.emit(cached)
        except Exception:
            self.not_found.emit()
