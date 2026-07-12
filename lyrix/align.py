"""Forced Alignment: offizieller Songtext (LRCLIB) + Whisper-Zeitstempel.

Community-LRC-Zeitstempel schwanken in der Qualität. Whisper liefert dagegen
präzise Wort-Zeitstempel aus der konkreten Audiodatei – aber einen oft
fehlerhaften Text (Gesang). Dieses Modul verbindet beides: Der offizielle
Text bleibt, seine Zeilen bekommen die per KI gemessenen Zeiten (Punkt 13).

Verfahren: globales Sequenz-Alignment (Needleman-Wunsch) zwischen den
normalisierten Wörtern des Songtexts und den Whisper-Wörtern. Zeilen mit
genügend sicher zugeordneten Wörtern erhalten deren Start/Ende; die übrigen
werden über eine stückweise lineare Zeit-Abbildung aus den LRC-Zeiten der
verankerten Nachbarzeilen interpoliert.
"""

from __future__ import annotations

_GAP = -0.45          # Lückenstrafe im Alignment
_MIN_WORD_SIM = 0.55  # ab dieser Ähnlichkeit gilt ein Wortpaar als Anker
_MIN_QUALITY = 0.35   # globaler Mindestanteil verankerter Songtext-Wörter


def _norm(word: str) -> str:
    return "".join(ch for ch in word.lower() if ch.isalnum())


def _similarity(a: str, b: str) -> float:
    """Schnelle Wort-Ähnlichkeit (bewusst ohne difflib im inneren Loop)."""
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    if len(a) >= 3 and len(b) >= 3:
        if a.startswith(b) or b.startswith(a):
            return 0.8
        if a[:3] == b[:3]:
            return 0.6
    return 0.0


def _lyric_words(lines: list[dict]) -> list[tuple[int, str]]:
    """[(Zeilenindex, normalisiertes Wort), …] in Textreihenfolge."""
    out: list[tuple[int, str]] = []
    for idx, line in enumerate(lines):
        for token in str(line.get("text", "")).split():
            norm = _norm(token)
            if norm:
                out.append((idx, norm))
    return out


def _whisper_words(whisper_lines: list[dict]) -> list[tuple[float, float, str]]:
    """[(start, ende, normalisiertes Wort), …] aus den Whisper-Zeilen.

    Zeilen ohne Wort-Zeitstempel werden gleichmäßig auf ihre Dauer verteilt."""
    out: list[tuple[float, float, str]] = []
    for line in whisper_lines:
        words = line.get("words") or []
        if words:
            for w in words:
                norm = _norm(str(w.get("text", "")))
                if norm:
                    out.append((float(w["start"]), float(w["end"]), norm))
            continue
        tokens = [t for t in str(line.get("text", "")).split() if _norm(t)]
        if not tokens:
            continue
        start, end = float(line["start"]), float(line["end"])
        step = max(0.01, (end - start) / len(tokens))
        for i, token in enumerate(tokens):
            out.append((start + i * step, start + (i + 1) * step,
                        _norm(token)))
    out.sort(key=lambda w: w[0])
    return out


def _align_pairs(lyric: list[tuple[int, str]],
                 whisper: list[tuple[float, float, str]]
                 ) -> list[tuple[int, int, float]]:
    """Needleman-Wunsch; Rückgabe: [(lyric_idx, whisper_idx, sim), …]."""
    n, m = len(lyric), len(whisper)
    if not n or not m:
        return []
    # DP-Matrix (n+1) x (m+1); bei Songlängen (~einige hundert Wörter) fein.
    score = [[0.0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        score[i][0] = score[i - 1][0] + _GAP
    for j in range(1, m + 1):
        score[0][j] = score[0][j - 1] + _GAP
    for i in range(1, n + 1):
        wa = lyric[i - 1][1]
        row, prev = score[i], score[i - 1]
        for j in range(1, m + 1):
            sim = _similarity(wa, whisper[j - 1][2])
            diag = prev[j - 1] + (sim if sim > 0 else -0.25)
            up = prev[j] + _GAP
            left = row[j - 1] + _GAP
            row[j] = max(diag, up, left)
    # Rückverfolgung
    pairs: list[tuple[int, int, float]] = []
    i, j = n, m
    while i > 0 and j > 0:
        sim = _similarity(lyric[i - 1][1], whisper[j - 1][2])
        diag = score[i - 1][j - 1] + (sim if sim > 0 else -0.25)
        if abs(score[i][j] - diag) < 1e-9:
            if sim >= _MIN_WORD_SIM:
                pairs.append((i - 1, j - 1, sim))
            i -= 1
            j -= 1
        elif abs(score[i][j] - (score[i - 1][j] + _GAP)) < 1e-9:
            i -= 1
        else:
            j -= 1
    pairs.reverse()
    return pairs


def align_lines(official: list[dict], whisper_lines: list[dict]
                ) -> tuple[list[dict] | None, float]:
    """Weist den offiziellen Zeilen Whisper-Zeiten zu.

    Rückgabe: (neue Zeilenliste, Qualität 0..1) oder (None, Qualität), wenn
    die Zuordnung zu unsicher ist (dann bleiben die LRC-Zeiten in Kraft)."""
    lyric = _lyric_words(official)
    whisper = _whisper_words(whisper_lines)
    pairs = _align_pairs(lyric, whisper)
    if not lyric:
        return None, 0.0
    quality = len(pairs) / len(lyric)
    if quality < _MIN_QUALITY:
        return None, quality

    # Anker je Zeile einsammeln
    per_line: dict[int, list[tuple[float, float]]] = {}
    for li, wj, _sim in pairs:
        line_idx = lyric[li][0]
        start, end, _ = whisper[wj]
        per_line.setdefault(line_idx, []).append((start, end))

    words_per_line: dict[int, int] = {}
    for line_idx, _w in lyric:
        words_per_line[line_idx] = words_per_line.get(line_idx, 0) + 1

    # Verankerte Zeilen: genug Wörter sicher zugeordnet
    anchored: dict[int, tuple[float, float]] = {}
    for idx, hits in per_line.items():
        need = 1 if words_per_line.get(idx, 0) <= 2 else 2
        if len(hits) < need:
            continue
        starts = sorted(h[0] for h in hits)
        ends = sorted(h[1] for h in hits)
        anchored[idx] = (starts[0], ends[-1])

    if not anchored:
        return None, quality

    # Übrige Zeilen: LRC-Zeit stückweise linear auf Whisper-Zeit abbilden
    xs = sorted(anchored)
    lrc = [float(official[i]["start"]) for i in xs]
    ali = [anchored[i][0] for i in xs]

    def map_time(t: float) -> float:
        if t <= lrc[0]:
            return t + (ali[0] - lrc[0])
        if t >= lrc[-1]:
            return t + (ali[-1] - lrc[-1])
        for k in range(1, len(lrc)):
            if t <= lrc[k]:
                span = lrc[k] - lrc[k - 1]
                frac = (t - lrc[k - 1]) / span if span > 0 else 0.0
                return ali[k - 1] + frac * (ali[k] - ali[k - 1])
        return t

    result: list[dict] = []
    for idx, line in enumerate(official):
        new = dict(line)
        if idx in anchored:
            new["start"], new["end"] = anchored[idx]
        else:
            new["start"] = map_time(float(line["start"]))
            new["end"] = map_time(float(line["end"]))
        result.append(new)

    # Monotonie erzwingen und Enden an die Folgezeile anlehnen
    for k in range(1, len(result)):
        if result[k]["start"] < result[k - 1]["start"]:
            result[k]["start"] = result[k - 1]["start"] + 0.01
    for k, line in enumerate(result):
        nxt = (result[k + 1]["start"] if k + 1 < len(result)
               else float(line["end"]))
        line["end"] = max(float(line["start"]) + 0.5,
                          min(float(line["end"]), nxt)
                          if nxt > line["start"] else float(line["end"]))
    return result, quality
