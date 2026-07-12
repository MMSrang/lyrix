"""Mit QPainter gezeichnete, gestochen scharfe UI-Icons (kein Icon-Font nötig)."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (QColor, QFont, QIcon, QPainter, QPainterPath,
                           QPen, QPixmap, QPolygonF)

_DPR = 2.0


def _make(size: int, color: str, draw) -> QIcon:
    pm = QPixmap(int(size * _DPR), int(size * _DPR))
    pm.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.scale(_DPR, _DPR)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(color))
    draw(painter, float(size))
    painter.end()
    pm.setDevicePixelRatio(_DPR)
    return QIcon(pm)


def play(color: str = "#000000", size: int = 24) -> QIcon:
    def d(p, s):
        p.drawPolygon(QPolygonF([QPointF(s * .34, s * .22),
                                 QPointF(s * .34, s * .78),
                                 QPointF(s * .82, s * .50)]))
    return _make(size, color, d)


def pause(color: str = "#000000", size: int = 24) -> QIcon:
    def d(p, s):
        p.drawRoundedRect(QRectF(s * .30, s * .24, s * .13, s * .52), s * .03, s * .03)
        p.drawRoundedRect(QRectF(s * .57, s * .24, s * .13, s * .52), s * .03, s * .03)
    return _make(size, color, d)


def skip_back(color: str = "#e8e8e8", size: int = 24) -> QIcon:
    def d(p, s):
        p.drawRoundedRect(QRectF(s * .24, s * .28, s * .08, s * .44), s * .02, s * .02)
        p.drawPolygon(QPolygonF([QPointF(s * .76, s * .28),
                                 QPointF(s * .76, s * .72),
                                 QPointF(s * .38, s * .50)]))
    return _make(size, color, d)


def skip_forward(color: str = "#e8e8e8", size: int = 24) -> QIcon:
    def d(p, s):
        p.drawRoundedRect(QRectF(s * .68, s * .28, s * .08, s * .44), s * .02, s * .02)
        p.drawPolygon(QPolygonF([QPointF(s * .24, s * .28),
                                 QPointF(s * .24, s * .72),
                                 QPointF(s * .62, s * .50)]))
    return _make(size, color, d)


def folder(color: str = "#e8e8e8", size: int = 24) -> QIcon:
    def d(p, s):
        path = QPainterPath()
        path.addRoundedRect(QRectF(s * .14, s * .30, s * .72, s * .44), s * .06, s * .06)
        tab = QPainterPath()
        tab.addRoundedRect(QRectF(s * .14, s * .22, s * .30, s * .18), s * .05, s * .05)
        p.drawPath(path.united(tab))
    return _make(size, color, d)


def gear(color: str = "#e8e8e8", size: int = 24) -> QIcon:
    def d(p, s):
        c = s / 2
        p.save()
        p.translate(c, c)
        for i in range(8):
            p.save()
            p.rotate(i * 45)
            p.drawRoundedRect(QRectF(-s * .055, -s * .40, s * .11, s * .16),
                              s * .03, s * .03)
            p.restore()
        path = QPainterPath()
        path.addEllipse(QPointF(0, 0), s * .27, s * .27)
        path.addEllipse(QPointF(0, 0), s * .115, s * .115)
        p.drawPath(path)
        p.restore()
    return _make(size, color, d)


def export(color: str = "#e8e8e8", size: int = 24) -> QIcon:
    def d(p, s):
        # Pfeil nach unten in eine Ablage
        p.drawRect(QRectF(s * .455, s * .18, s * .09, s * .34))
        p.drawPolygon(QPolygonF([QPointF(s * .30, s * .48),
                                 QPointF(s * .70, s * .48),
                                 QPointF(s * .50, s * .68)]))
        pen = QPen(p.brush().color(), s * .085, Qt.PenStyle.SolidLine,
                   Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        path = QPainterPath(QPointF(s * .18, s * .62))
        path.lineTo(s * .18, s * .78)
        path.lineTo(s * .82, s * .78)
        path.lineTo(s * .82, s * .62)
        p.drawPath(path)
    return _make(size, color, d)


def note(color: str = "#6f6f6f", size: int = 64) -> QIcon:
    def d(p, s):
        p.drawEllipse(QRectF(s * .22, s * .62, s * .22, s * .16))
        p.drawEllipse(QRectF(s * .58, s * .54, s * .22, s * .16))
        pen = QPen(p.brush().color(), s * .055)
        p.setPen(pen)
        p.drawLine(QPointF(s * .42, s * .68), QPointF(s * .42, s * .24))
        p.drawLine(QPointF(s * .78, s * .60), QPointF(s * .78, s * .18))
        p.drawLine(QPointF(s * .42, s * .24), QPointF(s * .78, s * .18))
        p.drawLine(QPointF(s * .42, s * .31), QPointF(s * .78, s * .25))
    return _make(size, color, d)


def volume(color: str = "#e8e8e8", size: int = 24, level: float = 1.0,
           muted: bool = False) -> QIcon:
    def d(p, s):
        # Lautsprecher-Korpus
        body = QPainterPath()
        body.moveTo(s * .16, s * .38)
        body.lineTo(s * .30, s * .38)
        body.lineTo(s * .46, s * .24)
        body.lineTo(s * .46, s * .76)
        body.lineTo(s * .30, s * .62)
        body.lineTo(s * .16, s * .62)
        body.closeSubpath()
        p.drawPath(body)
        pen = QPen(p.brush().color(), s * .07, Qt.PenStyle.SolidLine,
                   Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        if muted:
            p.drawLine(QPointF(s * .58, s * .38), QPointF(s * .82, s * .62))
            p.drawLine(QPointF(s * .82, s * .38), QPointF(s * .58, s * .62))
        else:
            if level > 0.05:
                p.drawArc(QRectF(s * .40, s * .34, s * .30, s * .32),
                          -60 * 16, 120 * 16)
            if level > 0.55:
                p.drawArc(QRectF(s * .40, s * .22, s * .52, s * .56),
                          -55 * 16, 110 * 16)
    return _make(size, color, d)


def loop(color: str = "#e8e8e8", size: int = 24) -> QIcon:
    def d(p, s):
        pen = QPen(p.brush().color(), s * .085, Qt.PenStyle.SolidLine,
                   Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        rect = QRectF(s * .20, s * .26, s * .60, s * .48)
        p.drawArc(rect, 30 * 16, 150 * 16)
        p.drawArc(rect, 210 * 16, 150 * 16)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(color))
        p.drawPolygon(QPolygonF([QPointF(s * .74, s * .16),
                                 QPointF(s * .74, s * .40),
                                 QPointF(s * .92, s * .28)]))
        p.drawPolygon(QPolygonF([QPointF(s * .26, s * .60),
                                 QPointF(s * .26, s * .84),
                                 QPointF(s * .08, s * .72)]))
    return _make(size, color, d)


def _seek10(color: str, size: int, forward: bool) -> QIcon:
    """Kreispfeil mit „10“ in der Mitte (YouTube-Stil): 10 Sekunden
    zurück (Pfeil links, gegen den Uhrzeigersinn) bzw. vor (gespiegelt)."""
    def d(p, s):
        pen = QPen(p.brush().color(), s * .075, Qt.PenStyle.SolidLine,
                   Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        rect = QRectF(s * .15, s * .15, s * .70, s * .70)
        # Lücke oben; Winkel in 1/16 Grad, 0° = 3 Uhr, positiv = gegen UZS
        if forward:
            p.drawArc(rect, 60 * 16, 300 * 16)     # endet bei 60° (oben rechts)
        else:
            p.drawArc(rect, 120 * 16, -300 * 16)   # endet bei 120° (oben links)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(color))
        # Pfeilspitze am oberen Arc-Ende, tangential zur Drehrichtung
        import math
        angle = 60.0 if forward else 120.0
        r = s * .35
        cx, cy = s * .5, s * .5
        px = cx + r * math.cos(math.radians(angle))
        py = cy - r * math.sin(math.radians(angle))
        a = s * .16
        if forward:
            p.drawPolygon(QPolygonF([QPointF(px - a * .5, py - a),
                                     QPointF(px - a * .5, py + a * .4),
                                     QPointF(px + a, py - a * .2)]))
        else:
            p.drawPolygon(QPolygonF([QPointF(px + a * .5, py - a),
                                     QPointF(px + a * .5, py + a * .4),
                                     QPointF(px - a, py - a * .2)]))
        # „10“ mittig
        font = QFont("Segoe UI")
        font.setPixelSize(int(s * .34))
        font.setBold(True)
        p.setFont(font)
        p.setPen(QColor(color))
        p.drawText(QRectF(0, 0, s, s), Qt.AlignmentFlag.AlignCenter, "10")
    return _make(size, color, d)


def replay10(color: str = "#e8e8e8", size: int = 24) -> QIcon:
    return _seek10(color, size, forward=False)


def forward10(color: str = "#e8e8e8", size: int = 24) -> QIcon:
    return _seek10(color, size, forward=True)


def offset(color: str = "#e8e8e8", size: int = 24) -> QIcon:
    """Horizontaler Doppelpfeil: Songtext zeitlich verschieben (Sync-Versatz)."""
    def d(p, s):
        pen = QPen(p.brush().color(), s * .075, Qt.PenStyle.SolidLine,
                   Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.drawLine(QPointF(s * .26, s * .50), QPointF(s * .74, s * .50))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(color))
        p.drawPolygon(QPolygonF([QPointF(s * .30, s * .34),
                                 QPointF(s * .30, s * .66),
                                 QPointF(s * .10, s * .50)]))
        p.drawPolygon(QPolygonF([QPointF(s * .70, s * .34),
                                 QPointF(s * .70, s * .66),
                                 QPointF(s * .90, s * .50)]))
    return _make(size, color, d)


def chevron_down(color: str = "#e8e8e8", size: int = 24) -> QIcon:
    """Deutlich erkennbarer Aufklapp-Pfeil (für den Zuletzt-benutzt-Knopf)."""
    def d(p, s):
        pen = QPen(p.brush().color(), s * .10, Qt.PenStyle.SolidLine,
                   Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        path = QPainterPath(QPointF(s * .26, s * .38))
        path.lineTo(s * .50, s * .64)
        path.lineTo(s * .74, s * .38)
        p.drawPath(path)
    return _make(size, color, d)


def mini_player(color: str = "#e8e8e8", size: int = 24) -> QIcon:
    def d(p, s):
        pen = QPen(p.brush().color(), s * .07)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(QRectF(s * .14, s * .18, s * .58, s * .46), s * .05, s * .05)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(color))
        p.drawRoundedRect(QRectF(s * .48, s * .52, s * .40, s * .32), s * .05, s * .05)
    return _make(size, color, d)


def info(color: str = "#e8e8e8", size: int = 24) -> QIcon:
    def d(p, s):
        pen = QPen(p.brush().color(), s * .07)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QRectF(s * .18, s * .18, s * .64, s * .64))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(color))
        p.drawEllipse(QRectF(s * .46, s * .30, s * .09, s * .09))
        p.drawRoundedRect(QRectF(s * .46, s * .45, s * .09, s * .26), s * .03, s * .03)
    return _make(size, color, d)


def win_minimize(color: str = "#d8d8d8", size: int = 24) -> QIcon:
    def d(p, s):
        pen = QPen(p.brush().color(), s * .055)
        p.setPen(pen)
        p.drawLine(QPointF(s * .30, s * .52), QPointF(s * .70, s * .52))
    return _make(size, color, d)


def win_maximize(color: str = "#d8d8d8", size: int = 24) -> QIcon:
    def d(p, s):
        pen = QPen(p.brush().color(), s * .055)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(QRectF(s * .32, s * .32, s * .38, s * .38), s * .04, s * .04)
    return _make(size, color, d)


def win_restore(color: str = "#d8d8d8", size: int = 24) -> QIcon:
    def d(p, s):
        pen = QPen(p.brush().color(), s * .055)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(QRectF(s * .30, s * .38, s * .34, s * .34), s * .04, s * .04)
        path = QPainterPath()
        path.moveTo(s * .40, s * .38)
        path.lineTo(s * .40, s * .30)
        path.lineTo(s * .72, s * .30)
        path.lineTo(s * .72, s * .62)
        path.lineTo(s * .64, s * .62)
        p.drawPath(path)
    return _make(size, color, d)


def win_close(color: str = "#d8d8d8", size: int = 24) -> QIcon:
    def d(p, s):
        pen = QPen(p.brush().color(), s * .055, Qt.PenStyle.SolidLine,
                   Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.drawLine(QPointF(s * .32, s * .32), QPointF(s * .68, s * .68))
        p.drawLine(QPointF(s * .68, s * .32), QPointF(s * .32, s * .68))
    return _make(size, color, d)
