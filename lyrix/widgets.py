"""Wiederverwendbare UI-Bausteine: eigene Titelleiste (Fluent-Stil),
klickbarer Fortschritts-Slider, Lautstärkeregler mit Stummschaltung,
Always-on-Top-Mini-Player und einklappbarer Einstellungs-Bereich."""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QPushButton, QSlider,
                               QStyle, QStyleOptionSlider, QToolButton,
                               QVBoxLayout, QWidget)

from . import icons
from .i18n import tr


# --------------------------------------------------------------- Titelleiste
class TitleBar(QWidget):
    """Eigene Titelleiste für das Hauptfenster (ohne nativen Rahmen)."""

    HEIGHT = 40
    mini_requested = Signal()

    def __init__(self, window, title: str = "", parent=None):
        super().__init__(parent)
        self._window = window
        self.setFixedHeight(self.HEIGHT)
        self.setObjectName("titleBar")

        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 0, 0, 0)
        lay.setSpacing(8)

        self.icon_label = QLabel()
        self.icon_label.setFixedSize(18, 18)
        self.icon_label.setScaledContents(True)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("titleBarText")
        lay.addWidget(self.icon_label)
        lay.addWidget(self.title_label)
        lay.addStretch(1)

        def make_btn(icon, obj_name, tip, slot):
            b = QPushButton()
            b.setObjectName(obj_name)
            b.setIcon(icon)
            b.setIconSize(QSize(16, 16))
            b.setFixedSize(46, self.HEIGHT)
            b.setToolTip(tip)
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            b.clicked.connect(slot)
            lay.addWidget(b)
            return b

        self.mini_btn = make_btn(icons.mini_player(), "captionButton",
                                 tr("mini_tip"), self.mini_requested.emit)
        self.min_btn = make_btn(icons.win_minimize(), "captionButton", "",
                                window.showMinimized)
        self.max_btn = make_btn(icons.win_maximize(), "captionButton", "",
                                self._toggle_max)
        self.close_btn = make_btn(icons.win_close(), "captionCloseButton", "",
                                  window.close)

    def set_icon(self, pixmap: QPixmap):
        self.icon_label.setPixmap(pixmap)

    def set_title(self, text: str):
        self.title_label.setText(text)

    def _toggle_max(self):
        if self._window.isMaximized():
            self._window.showNormal()
        else:
            self._window.showMaximized()

    def update_max_icon(self):
        if self._window.isMaximized():
            self.max_btn.setIcon(icons.win_restore())
        else:
            self.max_btn.setIcon(icons.win_maximize())

    def set_max_hover(self, hovered: bool):
        """Hover-Zustand des Maximieren-Buttons von außen setzen: Der Button
        liegt im Nicht-Client-Bereich (Snap-Layouts), Qt bekommt dort keine
        Maus-Events – die Optik wird deshalb aus WM_NCMOUSEMOVE gespeist."""
        if self.max_btn.property("ncHover") == hovered:
            return
        self.max_btn.setProperty("ncHover", hovered)
        self.max_btn.style().unpolish(self.max_btn)
        self.max_btn.style().polish(self.max_btn)

    def caption_buttons(self):
        return (self.mini_btn, self.min_btn, self.max_btn, self.close_btn)


# ------------------------------------------------------------- Klick-Slider
class ClickSlider(QSlider):
    """Slider, der bei Klick direkt zur Klickposition springt."""

    clicked_value = Signal(int)

    def __init__(self, orientation=Qt.Orientation.Horizontal, parent=None):
        super().__init__(orientation, parent)

    def _value_for_pos(self, pos) -> int:
        opt = QStyleOptionSlider()
        self.initStyleOption(opt)
        groove = self.style().subControlRect(
            QStyle.ComplexControl.CC_Slider, opt,
            QStyle.SubControl.SC_SliderGroove, self)
        handle = self.style().subControlRect(
            QStyle.ComplexControl.CC_Slider, opt,
            QStyle.SubControl.SC_SliderHandle, self)
        if self.orientation() == Qt.Orientation.Horizontal:
            span = groove.width() - handle.width()
            offset = pos.x() - groove.x() - handle.width() // 2
        else:
            span = groove.height() - handle.height()
            offset = pos.y() - groove.y() - handle.height() // 2
        return QStyle.sliderValueFromPosition(
            self.minimum(), self.maximum(), offset, max(1, span),
            opt.upsideDown)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.maximum() > 0:
            value = self._value_for_pos(event.position().toPoint())
            self.setValue(value)
            self.clicked_value.emit(value)
        super().mousePressEvent(event)


# ------------------------------------------------------------ Lautstärke
class VolumeControl(QWidget):
    """Lautsprecher-Icon + Schieberegler nebeneinander (wie in der
    Windows-Medienwiedergabe). Klick auf das Icon schaltet stumm/laut,
    das Symbol wechselt entsprechend."""

    volume_changed = Signal(float)   # effektive Lautstärke 0.0 .. 1.0

    def __init__(self, parent=None):
        super().__init__(parent)
        self._volume = 1.0
        self._muted = False

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)

        self.icon_btn = QPushButton()
        self.icon_btn.setProperty("iconBtn", True)
        self.icon_btn.setIconSize(QSize(18, 18))
        self.icon_btn.setToolTip(tr("volume_tip"))
        self.icon_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.icon_btn.clicked.connect(self.toggle_mute)

        # ClickSlider: Klick auf die Leiste setzt die Lautstärke direkt
        # dorthin (Punkt 6) – gleiches Verhalten wie die Wiedergabeleiste.
        self.slider = ClickSlider()
        self.slider.setObjectName("volumeSlider")
        self.slider.setRange(0, 100)
        self.slider.setValue(100)
        self.slider.setFixedWidth(86)
        self.slider.valueChanged.connect(self._on_slider)

        lay.addWidget(self.icon_btn)
        lay.addWidget(self.slider)
        self._refresh_icon()

    # ------------------------------------------------------------------
    def set_state(self, volume: float, muted: bool):
        self._volume = max(0.0, min(1.0, volume))
        self._muted = muted
        self.slider.blockSignals(True)
        self.slider.setValue(round(self._volume * 100))
        self.slider.blockSignals(False)
        self._refresh_icon()

    def effective_volume(self) -> float:
        return 0.0 if self._muted else self._volume

    def is_muted(self) -> bool:
        return self._muted

    def toggle_mute(self):
        self._muted = not self._muted
        self._refresh_icon()
        self.volume_changed.emit(self.effective_volume())

    def _on_slider(self, value: int):
        self._volume = value / 100.0
        if self._muted and value > 0:
            self._muted = False   # Regler bewegen hebt Stummschaltung auf
        self._refresh_icon()
        self.volume_changed.emit(self.effective_volume())

    def _refresh_icon(self):
        muted = self._muted or self._volume <= 0.001
        self.icon_btn.setIcon(icons.volume(level=self._volume, muted=muted))


# -------------------------------------------------------------- Mini-Player
class MiniPlayer(QWidget):
    """Kompakter Always-on-Top-Player: Cover, Play/Pause, aktuelle Zeile."""

    play_pause = Signal()
    restore_requested = Signal()

    def __init__(self):
        super().__init__(None, Qt.WindowType.Tool |
                         Qt.WindowType.FramelessWindowHint |
                         Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(380, 96)
        self._drag_offset: QPoint | None = None

        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 14, 10, 14)
        lay.setSpacing(12)

        self.cover_label = QLabel()
        self.cover_label.setFixedSize(64, 64)
        lay.addWidget(self.cover_label)

        mid = QVBoxLayout()
        mid.setSpacing(2)
        self.title_label = QLabel("")
        self.title_label.setObjectName("miniTitle")
        self.line_label = QLabel("")
        self.line_label.setObjectName("miniLine")
        self.line_label.setWordWrap(True)
        mid.addWidget(self.title_label)
        mid.addWidget(self.line_label, 1)
        lay.addLayout(mid, 1)

        right = QVBoxLayout()
        right.setSpacing(4)
        top_row = QHBoxLayout()
        self.restore_btn = QToolButton()
        self.restore_btn.setIcon(icons.win_restore())
        self.restore_btn.setAutoRaise(True)
        self.restore_btn.setToolTip(tr("mini_tip"))
        self.restore_btn.clicked.connect(self.restore_requested.emit)
        top_row.addStretch(1)
        top_row.addWidget(self.restore_btn)
        right.addLayout(top_row)
        self.play_btn = QPushButton()
        self.play_btn.setObjectName("miniPlayButton")
        self.play_btn.setIcon(icons.play("#000000"))
        self.play_btn.setIconSize(QSize(16, 16))
        self.play_btn.setFixedSize(36, 36)
        self.play_btn.clicked.connect(self.play_pause.emit)
        right.addWidget(self.play_btn, 0, Qt.AlignmentFlag.AlignRight)
        lay.addLayout(right)

    # ------------------------------------------------------------------
    def set_cover(self, pixmap: QPixmap):
        self.cover_label.setPixmap(pixmap)

    def set_title(self, text: str):
        metrics = self.title_label.fontMetrics()
        self.title_label.setText(metrics.elidedText(
            text, Qt.TextElideMode.ElideRight, 230))

    def set_line(self, text: str):
        self.line_label.setText(text)

    def set_playing(self, playing: bool):
        self.play_btn.setIcon(icons.pause("#000000") if playing
                              else icons.play("#000000"))

    # ------------------------------------------------------------------
    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), 14, 14)
        p.fillPath(path, QColor(24, 24, 24, 242))
        p.setPen(QColor(255, 255, 255, 26))
        p.drawPath(path)
        p.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = (event.globalPosition().toPoint()
                                 - self.frameGeometry().topLeft())

    def mouseMoveEvent(self, event):
        if self._drag_offset is not None:
            self.move(event.globalPosition().toPoint() - self._drag_offset)

    def mouseReleaseEvent(self, _event):
        self._drag_offset = None

    def mouseDoubleClickEvent(self, _event):
        self.restore_requested.emit()


# --------------------------------------------------------- Einklapp-Bereich
class CollapsibleSection(QWidget):
    """„Erweitert“-Bereich: Kopfzeile mit Pfeil, Inhalt ein-/ausklappbar."""

    def __init__(self, title: str, content: QWidget, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        self._toggle = QToolButton()
        self._toggle.setText(" " + title)
        self._toggle.setCheckable(True)
        self._toggle.setChecked(False)
        self._toggle.setObjectName("collapsibleHeader")
        self._toggle.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self._toggle.setArrowType(Qt.ArrowType.RightArrow)
        self._toggle.toggled.connect(self._on_toggled)
        self._content = content
        self._content.setVisible(False)
        lay.addWidget(self._toggle)
        lay.addWidget(self._content)

    def _on_toggled(self, checked: bool):
        self._toggle.setArrowType(Qt.ArrowType.DownArrow if checked
                                  else Qt.ArrowType.RightArrow)
        self._content.setVisible(checked)
