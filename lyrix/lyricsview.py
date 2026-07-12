"""Spotify-Lyrics-artige, mitlaufende Textansicht.

Jede Zeile ist ein QLabel mit Rich-Text: Die aktive Zeile ist groß und weiß,
bereits gesprochene Wörter werden weiß, das aktuelle Wort grün eingefärbt.
Die Ansicht scrollt weich mit; manuelles Scrollen pausiert das Mitlaufen kurz.
"""

from __future__ import annotations

import bisect
import html
import time

from PySide6.QtCore import (QEasingCurve, QEvent, QPoint, QPointF,
                            QPropertyAnimation, Qt, Signal)
from PySide6.QtGui import QTextDocument
from PySide6.QtWidgets import QLabel, QScrollArea, QVBoxLayout, QWidget

from . import diarizer, theme


class SegmentLine(QLabel):
    clicked = Signal(float)

    def __init__(self, seg: dict, parent=None):
        super().__init__(parent)
        self.seg = seg
        self.speaker_label: str | None = None   # rohes pyannote-Label
        self.speaker_name: str | None = None    # "Person A"
        self.speaker_color: str = theme.ACCENT
        self.show_speaker = False
        self.active = False

        self.setWordWrap(True)
        self.setTextFormat(Qt.TextFormat.RichText)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.setContentsMargins(0, 7, 0, 7)
        # Punkt 8: Nur der tatsächliche Text reagiert auf Klicks – nicht die
        # leere Fläche rechts daneben. Cursor wird deshalb dynamisch gesetzt.
        self.setMouseTracking(True)

    def _text_hit(self, pos: QPointF) -> bool:
        """True, wenn pos (Widget-Koordinaten) auf dem gerenderten Text liegt."""
        rect = self.contentsRect()
        doc = QTextDocument()
        doc.setDefaultFont(self.font())
        doc.setDocumentMargin(0)
        doc.setHtml(self.text())
        doc.setTextWidth(rect.width())
        local = QPointF(pos.x() - rect.x(), pos.y() - rect.y())
        hit = doc.documentLayout().hitTest(
            local, Qt.HitTestAccuracy.ExactHit)
        return hit >= 0

    def mouseMoveEvent(self, event):
        self.setCursor(Qt.CursorShape.PointingHandCursor
                       if self._text_hit(event.position())
                       else Qt.CursorShape.ArrowCursor)
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event):
        if (event.button() == Qt.MouseButton.LeftButton
                and self._text_hit(event.position())):
            self.clicked.emit(float(self.seg["start"]))
            event.accept()
            return
        super().mousePressEvent(event)

    def refresh(self, t: float):
        self.setText(self._html(t))

    def _html(self, t: float) -> str:
        seg = self.seg
        if seg.get("is_tag"):
            # Geräusch-/Musik-Tag: dezent, kursiv, ohne Karaoke
            if self.active:
                size, col = 16, "#d8d8d8"
            else:
                size, col = 13, "#7a7a7a" if seg["end"] > t else "#9a9a9a"
            return (f'<p style="margin:0; font-size:{size}px; font-weight:600;">'
                    f'<span style="color:{col}; font-style:italic;">'
                    f'{html.escape(seg["text"])}</span></p>')

        head = ""
        if self.show_speaker and self.speaker_name:
            head = (f'<span style="font-size:11px; font-weight:700; '
                    f'letter-spacing:1.5px; color:{self.speaker_color};">'
                    f'{html.escape(self.speaker_name.upper())}</span><br/>')

        if not self.active:
            size, weight = 16, 600
            col = "#c7c7c7" if seg["end"] <= t else "#6e6e6e"
            body = f'<span style="color:{col};">{html.escape(seg["text"])}</span>'
        else:
            size, weight = 21, 700
            words = seg.get("words") or []
            if not words:
                body = f'<span style="color:#ffffff;">{html.escape(seg["text"])}</span>'
            else:
                parts = []
                for w in words:
                    if t >= w["end"]:
                        col = "#ffffff"
                    elif w["start"] <= t:
                        col = theme.ACCENT
                    else:
                        col = "#8f8f8f"
                    parts.append(f'<span style="color:{col};">'
                                 f'{html.escape(w["text"])}</span>')
                body = "".join(parts)

        return (f'<p style="margin:0; font-size:{size}px; '
                f'font-weight:{weight}; line-height:132%;">{head}{body}</p>')


class LyricsView(QScrollArea):
    seek_requested = Signal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._container = QWidget()
        self._vbox = QVBoxLayout(self._container)
        self._vbox.setContentsMargins(28, 0, 28, 0)
        self._vbox.setSpacing(2)
        top_pad = QWidget()
        top_pad.setFixedHeight(200)
        bottom_pad = QWidget()
        bottom_pad.setFixedHeight(320)
        self._vbox.addWidget(top_pad)
        self._vbox.addWidget(bottom_pad)
        self.setWidget(self._container)

        self.lines: list[SegmentLine] = []
        self._starts: list[float] = []
        self._current = -1
        self._last_t = 0.0
        self._show_speakers = False
        self._turns: list | None = None
        self._names: dict[str, str] = {}
        self._user_hold_until = 0.0

        self._anim = QPropertyAnimation(self.verticalScrollBar(), b"value", self)
        self._anim.setDuration(420)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self.viewport().installEventFilter(self)
        self.verticalScrollBar().sliderPressed.connect(self._on_user_scroll)

    # ------------------------------------------------------------------
    def eventFilter(self, obj, event):
        if obj is self.viewport() and event.type() == QEvent.Type.Wheel:
            self._on_user_scroll()
        return super().eventFilter(obj, event)

    def _on_user_scroll(self):
        self._user_hold_until = time.monotonic() + 4.0

    def resume_autoscroll(self):
        self._user_hold_until = 0.0
        if 0 <= self._current < len(self.lines):
            self._scroll_to(self.lines[self._current])

    # ------------------------------------------------------------------
    def clear(self):
        for line in self.lines:
            self._vbox.removeWidget(line)
            line.deleteLater()
        self.lines.clear()
        self._starts.clear()
        self._current = -1
        self._turns = None
        self._names = {}
        self._last_t = 0.0
        self.verticalScrollBar().setValue(0)

    def add_line(self, seg: dict):
        """Fügt eine Zeile zeitlich sortiert ein (Transkript und Geräusch-Tags
        kommen aus parallelen Threads und können sich überholen)."""
        line = SegmentLine(seg)
        line.show_speaker = self._show_speakers
        if self._turns and not seg.get("is_tag"):
            self._assign_speaker(line)
        line.clicked.connect(self.seek_requested)
        start = float(seg["start"])
        pos = bisect.bisect_right(self._starts, start)
        # Layout: [0]=oberer Abstandshalter, [1..n]=Zeilen, [n+1]=unterer
        self._vbox.insertWidget(1 + pos, line)
        self.lines.insert(pos, line)
        self._starts.insert(pos, start)
        if self._current >= pos:
            self._current += 1
        line.refresh(self._last_t)

    def remove_tag_lines(self, predicate):
        """Entfernt Tag-Zeilen, für die predicate(seg) wahr ist (z. B. Tags,
        die sich nachträglich als von Sprache überlagert herausstellen)."""
        removed = 0
        for i in range(len(self.lines) - 1, -1, -1):
            line = self.lines[i]
            if not line.seg.get("is_tag") or not predicate(line.seg):
                continue
            self._vbox.removeWidget(line)
            line.deleteLater()
            del self.lines[i]
            del self._starts[i]
            if self._current == i:
                self._current = -1
            elif self._current > i:
                self._current -= 1
            removed += 1
        return removed

    # ------------------------------------------------------------------
    def set_turns(self, turns: list):
        self._turns = turns
        self._names = diarizer.display_names(turns)
        for line in self.lines:
            self._assign_speaker(line)
        self.refresh_all()

    def speaker_count(self) -> int:
        return len(self._names)

    def _assign_speaker(self, line: SegmentLine):
        label = diarizer.speaker_for_span(self._turns or [],
                                          float(line.seg["start"]),
                                          float(line.seg["end"]))
        line.speaker_label = label
        if label is not None:
            line.speaker_name = self._names.get(label)
            line.speaker_color = diarizer.speaker_color(self._names, label)
        else:
            line.speaker_name = None

    def set_show_speakers(self, show: bool):
        self._show_speakers = show
        for line in self.lines:
            line.show_speaker = show
        self.refresh_all()

    def refresh_all(self):
        for line in self.lines:
            line.refresh(self._last_t)

    # ------------------------------------------------------------------
    def set_time(self, t: float):
        if t == self._last_t:
            return  # keine Zeitänderung (pausiert) -> kein Neuzeichnen
        jumped = abs(t - self._last_t) > 2.5
        self._last_t = t
        if not self._starts:
            return
        idx = bisect.bisect_right(self._starts, t) - 1
        if idx != self._current:
            if 0 <= self._current < len(self.lines):
                old = self.lines[self._current]
                old.active = False
                old.refresh(t)
            self._current = idx
            if 0 <= idx < len(self.lines):
                self.lines[idx].active = True
                self._scroll_to(self.lines[idx])
        if jumped:
            self.refresh_all()
        elif 0 <= self._current < len(self.lines):
            self.lines[self._current].refresh(t)  # Wort-Karaoke aktualisieren

    def _scroll_to(self, line: SegmentLine):
        if time.monotonic() < self._user_hold_until:
            return
        y = line.mapTo(self._container, QPoint(0, 0)).y()
        target = y + line.height() // 2 - int(self.viewport().height() * 0.40)
        target = max(0, min(target, self.verticalScrollBar().maximum()))
        self._anim.stop()
        self._anim.setStartValue(self.verticalScrollBar().value())
        self._anim.setEndValue(target)
        self._anim.start()

    # ------------------------------------------------------------------
    def export_rows(self) -> list[dict]:
        return [{
            "start": float(l.seg["start"]),
            "end": float(l.seg["end"]),
            "text": l.seg["text"],
            "speaker": l.speaker_name,
        } for l in self.lines]
