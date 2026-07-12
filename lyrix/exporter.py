"""Export des Transkripts als Textdatei oder SRT-Untertitel."""

from __future__ import annotations

from .util import fmt_srt_time, fmt_time


def to_txt(rows: list[dict]) -> str:
    out = []
    for r in rows:
        prefix = f"{r['speaker']}: " if r.get("speaker") else ""
        out.append(f"[{fmt_time(r['start'])}] {prefix}{r['text']}")
    return "\n".join(out) + "\n"


def to_srt(rows: list[dict]) -> str:
    out = []
    for i, r in enumerate(rows, start=1):
        prefix = f"{r['speaker']}: " if r.get("speaker") else ""
        out.append(str(i))
        out.append(f"{fmt_srt_time(r['start'])} --> {fmt_srt_time(r['end'])}")
        out.append(f"{prefix}{r['text']}")
        out.append("")
    return "\n".join(out) + "\n"
