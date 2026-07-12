"""Zerlegt Whisper-Segmente anhand der Wort-Zeitstempel in kurze,
Lyrics-taugliche Zeilen (Satzenden, Pausen, Maximallänge)."""

from __future__ import annotations

_SENTENCE_END = (".", "!", "?", "…", ":", ";", "。", "？", "！")


def split_words_into_lines(words, max_words: int = 12, max_chars: int = 58,
                           max_gap: float = 1.2) -> list[dict]:
    """words: faster-whisper Word-Objekte (Attribute start, end, word).

    Rückgabe: Liste von Zeilen-Dicts
    {"start", "end", "text", "words": [{"start", "end", "text"}, ...]}
    """
    ws = [{"start": float(w.start), "end": float(w.end), "text": w.word}
          for w in words if w.word and w.word.strip()]
    lines: list[dict] = []
    cur: list[dict] = []

    def flush():
        if not cur:
            return
        cur[0] = dict(cur[0], text=cur[0]["text"].lstrip())
        text = "".join(w["text"] for w in cur).strip()
        if text:
            lines.append({
                "start": cur[0]["start"],
                "end": cur[-1]["end"],
                "text": text,
                "words": list(cur),
            })
        cur.clear()

    for w in ws:
        if cur and w["start"] - cur[-1]["end"] > max_gap:
            flush()
        cur.append(w)
        stripped = w["text"].strip()
        n_chars = sum(len(x["text"]) for x in cur)
        if ((stripped.endswith(_SENTENCE_END) and len(cur) >= 3)
                or len(cur) >= max_words
                or n_chars >= max_chars):
            flush()
    flush()
    return lines
