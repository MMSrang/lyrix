"""Hauptfenster: eigener Fensterrahmen mit nativem Verhalten (Snap, Resize,
Drag-Restore), Cover-Art-Backdrop, Lyrics-Ansicht, Wiederholen/Lautstärke/
Tempo, Mini-Player, Geräusch-Tags, Sprechertrennung, Online-Songtexte,
SMTC- und Taskleisten-Integration.

Fenstertechnik: KEIN Qt-FramelessWindowHint. Stattdessen behält das Fenster
die nativen Stile (WS_THICKFRAME, WS_CAPTION, WS_MAXIMIZEBOX) und WM_NCCALCSIZE
wird abgefangen, sodass der Client-Bereich das ganze Fenster füllt. Damit
funktionieren Maximieren (randlos korrekt), Kanten-Resize, Aero-Snap und
Titelleisten-Drag-Restore wie bei normalen Windows-Fenstern.
"""

from __future__ import annotations

import ctypes
import hashlib
import os
import tempfile
from ctypes import wintypes
from functools import partial

from PySide6.QtCore import QPoint, QRectF, QSettings, QSize, Qt, QTimer, QUrl
from PySide6.QtGui import (QColor, QCursor, QImage, QKeySequence,
                           QLinearGradient, QPainter, QPainterPath, QPixmap,
                           QShortcut)
from PySide6.QtMultimedia import QAudioOutput, QMediaMetaData, QMediaPlayer
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QFileDialog,
                               QFormLayout, QGridLayout, QHBoxLayout, QLabel,
                               QMainWindow, QMenu, QMessageBox, QProgressBar,
                               QPushButton, QStackedLayout, QVBoxLayout,
                               QWidget)

from . import APP_NAME, ORG_NAME, diarizer, exporter, icons, packs, soundtags
from .covers import CoverSearchThread
from .diarizer import DiarizerThread
from .i18n import tr
from .lyrics_online import LyricsSearchThread
from .lyricsview import LyricsView
from .settingsdialog import SettingsDialog
from .smtc import SmtcBridge
from .soundtags import SoundTagThread
from .thumbbar import TaskbarMiniPlayer, apply_window_chrome
from .transcriber import TranscriberThread
from .util import fmt_time, resource_path
from .widgets import ClickSlider, MiniPlayer, TitleBar, VolumeControl

AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".oga", ".opus",
              ".wma", ".webm", ".mp4", ".m4v", ".mkv", ".mov", ".amr", ".aiff",
              ".aif", ".mka", ".3gp"}

_EXT_PATTERN = ("*.mp3 *.wav *.m4a *.aac *.flac *.ogg *.oga *.opus *.wma "
                "*.webm *.mp4 *.m4v *.mkv *.mov *.amr *.aiff *.aif *.mka *.3gp")

SPEED_STEPS = [0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0]

# ------------------------- Win32-Konstanten für den eigenen Fensterrahmen
WM_NCCALCSIZE = 0x0083
WM_NCHITTEST = 0x0084
WM_NCMOUSEMOVE = 0x00A0
WM_NCLBUTTONDOWN = 0x00A1
WM_NCLBUTTONUP = 0x00A2
WM_NCLBUTTONDBLCLK = 0x00A3
WM_MOUSEMOVE = 0x0200
WM_NCMOUSELEAVE = 0x02A2
HTCLIENT, HTCAPTION, HTMAXBUTTON = 1, 2, 9
HTLEFT, HTRIGHT, HTTOP = 10, 11, 12
HTTOPLEFT, HTTOPRIGHT, HTBOTTOM = 13, 14, 15
HTBOTTOMLEFT, HTBOTTOMRIGHT = 16, 17
_RESIZE_MARGIN = 6

GWL_STYLE = -16
WS_MAXIMIZEBOX = 0x00010000
WS_MINIMIZEBOX = 0x00020000
WS_THICKFRAME = 0x00040000
WS_CAPTION = 0x00C00000
SWP_FLAGS = 0x0002 | 0x0001 | 0x0004 | 0x0020 | 0x0010  # NOMOVE|NOSIZE|NOZORDER|FRAMECHANGED|NOACTIVATE
SM_CXSIZEFRAME = 32
SM_CXPADDEDBORDER = 92


class BackdropWidget(QWidget):
    """Zeichnet das (weichgezeichnete) Cover als Fensterhintergrund."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._blur: QPixmap | None = None

    def set_cover(self, image: QImage | None):
        if image is None or image.isNull():
            self._blur = None
        else:
            small = image.scaled(24, 24,
                                 Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                 Qt.TransformationMode.SmoothTransformation)
            self._blur = QPixmap.fromImage(small)
        self.update()

    def paintEvent(self, _event):
        from . import theme
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(theme.BG))
        if self._blur is not None:
            src = self._blur.rect()
            scale = max(self.width() / src.width(), self.height() / src.height())
            w, h = src.width() * scale, src.height() * scale
            x, y = (self.width() - w) / 2, (self.height() - h) / 2
            p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            p.setOpacity(0.45)
            p.drawPixmap(QRectF(x, y, w, h), self._blur, QRectF(src))
            p.setOpacity(1.0)
        grad = QLinearGradient(0, 0, 0, self.height())
        grad.setColorAt(0.0, QColor(0, 0, 0, 90))
        grad.setColorAt(0.55, QColor(0, 0, 0, 130))
        grad.setColorAt(1.0, QColor(6, 6, 6, 215))
        p.fillRect(self.rect(), grad)


def _rounded_cover(image: QImage | None, size: int = 48, radius: int = 8) -> QPixmap:
    dpr = 2
    pm = QPixmap(size * dpr, size * dpr)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    path = QPainterPath()
    path.addRoundedRect(QRectF(0, 0, size * dpr, size * dpr),
                        radius * dpr, radius * dpr)
    p.setClipPath(path)
    if image is not None and not image.isNull():
        scaled = image.scaled(size * dpr, size * dpr,
                              Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                              Qt.TransformationMode.SmoothTransformation)
        p.drawImage(int((size * dpr - scaled.width()) / 2),
                    int((size * dpr - scaled.height()) / 2), scaled)
    else:
        p.fillRect(pm.rect(), QColor("#242424"))
        icon_pm = icons.note("#6f6f6f", size).pixmap(size, size)
        p.drawPixmap(int(size * dpr * 0.15), int(size * dpr * 0.15),
                     int(size * dpr * 0.7), int(size * dpr * 0.7), icon_pm)
    p.end()
    pm.setDevicePixelRatio(dpr)
    return pm


class MainWindow(QMainWindow):
    def __init__(self, path: str | None = None):
        super().__init__()
        # Zustands-Attribute ZUERST: nativeEvent() kann schon während der
        # Fenster-Erzeugung feuern, bevor __init__ durchgelaufen ist.
        self._gen = 0
        self._transcriber: TranscriberThread | None = None
        self._diarizer: DiarizerThread | None = None
        self._tagger: SoundTagThread | None = None
        self._cover_thread: CoverSearchThread | None = None
        self._lyrics_thread: LyricsSearchThread | None = None
        self._diar_started = False
        self._path: str | None = None
        self._token_hint_shown = False
        self._ai_hint_shown = False
        self._chrome_applied = False
        self._thumbbar: TaskbarMiniPlayer | None = None
        self._cover_png: str | None = None
        self._cover_image: QImage | None = None
        self._repeat = False               # Punkt 5: einfacher Repeat-Toggle
        self._official_lyrics = False      # LRCLIB-Songtext hat übernommen
        self._official_line_dicts: list[dict] | None = None
        self._align_active = False         # Punkt 13: Whisper läuft still mit
        self._whisper_lines: list[dict] = []
        self._lyrics_offset_ms = 0         # Punkt 12: manueller Sync-Versatz
        self._mini: MiniPlayer | None = None
        self.titlebar: TitleBar | None = None

        self.settings = QSettings(ORG_NAME, APP_NAME)
        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(520, 640)
        self.resize(620, 840)
        geo = self.settings.value("geometry")
        if geo is not None:
            self.restoreGeometry(geo)
        self.setAcceptDrops(True)

        self._build_ui()
        self._build_player()
        self._build_shortcuts()
        self._build_media_integration()

        if path:
            QTimer.singleShot(50, lambda: self.open_path(path))
        if (str(self.settings.value("gpu_pack_wanted", "false")).lower() == "true"
                and not packs.gpu_runtime_installed()):
            self.settings.setValue("gpu_pack_wanted", "false")
            QTimer.singleShot(400, self.show_settings)

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        self.backdrop = BackdropWidget()
        root = QVBoxLayout(self.backdrop)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.titlebar = TitleBar(self, APP_NAME)
        icon_file = resource_path(os.path.join("assets", "icon.ico"))
        if os.path.exists(icon_file):
            self.titlebar.set_icon(QPixmap(icon_file))
        self.titlebar.mini_requested.connect(self.toggle_mini_player)
        root.addWidget(self.titlebar)

        # Kopfzeile (Sprechertrennung wohnt jetzt in den Einstellungen)
        header = QWidget()
        header.setObjectName("headerPanel")
        head_lay = QHBoxLayout(header)
        head_lay.setContentsMargins(10, 6, 10, 6)
        head_lay.setSpacing(6)
        self.open_btn = QPushButton(" " + tr("open"))
        self.open_btn.setIcon(icons.folder())
        self.open_btn.clicked.connect(self.open_dialog)
        self.recent_btn = QPushButton()
        self.recent_btn.setIcon(icons.chevron_down())
        self.recent_btn.setIconSize(QSize(14, 14))
        self.recent_btn.setFixedWidth(30)
        self.recent_btn.setToolTip(tr("recent_menu"))
        self.recent_btn.clicked.connect(self._show_recent_menu)
        self.settings_btn = QPushButton()
        self.settings_btn.setProperty("iconBtn", True)
        self.settings_btn.setIcon(icons.gear())
        self.settings_btn.setToolTip(tr("settings_tip"))
        self.settings_btn.clicked.connect(self.show_settings)
        head_lay.addWidget(self.open_btn)
        head_lay.addWidget(self.recent_btn)
        head_lay.addStretch(1)
        head_lay.addWidget(self.settings_btn)
        root.addWidget(header)

        # Fortschrittsband
        self.progress_strip = QProgressBar()
        self.progress_strip.setRange(0, 1000)
        self.progress_strip.setTextVisible(False)
        self.progress_strip.hide()
        root.addWidget(self.progress_strip)

        # Mitte
        self.lyrics = LyricsView()
        self.lyrics.seek_requested.connect(self._seek_seconds)

        self.placeholder = QLabel(tr("placeholder"))
        self.placeholder.setObjectName("placeholder")
        self.placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)

        loading = QWidget()
        load_lay = QVBoxLayout(loading)
        load_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        load_lay.setSpacing(14)
        self.loading_title = QLabel("")
        self.loading_title.setObjectName("loadingTitle")
        self.loading_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.loading_bar = QProgressBar()
        self.loading_bar.setRange(0, 0)
        self.loading_bar.setFixedWidth(260)
        self.loading_bar.setTextVisible(False)
        self.loading_hint = QLabel(tr("first_download_hint"))
        self.loading_hint.setObjectName("loadingHint")
        self.loading_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        load_lay.addWidget(self.loading_title)
        load_lay.addWidget(self.loading_bar, 0, Qt.AlignmentFlag.AlignHCenter)
        load_lay.addWidget(self.loading_hint)
        self._loading_page = loading

        stack_holder = QWidget()
        self._stack = QStackedLayout(stack_holder)
        self._stack.addWidget(self.placeholder)
        self._stack.addWidget(loading)
        self._stack.addWidget(self.lyrics)
        root.addWidget(stack_holder, 1)

        # Fußzeile (Punkt 6: eine klare Reihenfolge, einheitliche Größen)
        footer = QWidget()
        footer.setObjectName("footerPanel")
        foot_lay = QVBoxLayout(footer)
        foot_lay.setContentsMargins(14, 8, 14, 10)
        foot_lay.setSpacing(4)

        slider_row = QHBoxLayout()
        slider_row.setSpacing(10)
        self.pos_label = QLabel("0:00")
        self.pos_label.setObjectName("timeLabel")
        self.slider = ClickSlider()
        self.slider.setRange(0, 0)
        self.slider.sliderMoved.connect(self._on_slider_moved)
        self.slider.clicked_value.connect(self._on_slider_moved)
        self.slider.sliderReleased.connect(
            lambda: self._on_slider_moved(self.slider.value()))
        self.dur_label = QLabel("0:00")
        self.dur_label.setObjectName("timeLabel")
        slider_row.addWidget(self.pos_label)
        slider_row.addWidget(self.slider, 1)
        slider_row.addWidget(self.dur_label)
        foot_lay.addLayout(slider_row)

        controls = QGridLayout()
        controls.setContentsMargins(0, 0, 0, 0)

        def icon_button(icon, tip, slot):
            b = QPushButton()
            b.setProperty("iconBtn", True)
            b.setIcon(icon)
            b.setIconSize(QSize(18, 18))
            b.setToolTip(tip)
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            b.clicked.connect(slot)
            return b

        left_box = QHBoxLayout()
        left_box.setSpacing(10)
        self.cover_label = QLabel()
        self.cover_label.setFixedSize(48, 48)
        self.cover_label.setPixmap(_rounded_cover(None))
        self.cover_label.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.cover_label.customContextMenuRequested.connect(
            lambda _pos: self.show_properties())
        title_box = QVBoxLayout()
        title_box.setSpacing(1)
        self.track_title = QLabel(tr("no_file"))
        self.track_title.setObjectName("trackTitle")
        self.track_title.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.track_title.customContextMenuRequested.connect(
            lambda _pos: self.show_properties())
        self.track_status = QLabel(tr("ready"))
        self.track_status.setObjectName("trackStatus")
        title_box.addWidget(self.track_title)
        title_box.addWidget(self.track_status)
        left_box.addWidget(self.cover_label)
        left_box.addLayout(title_box)
        left_holder = QWidget()
        left_holder.setLayout(left_box)

        center_box = QHBoxLayout()
        center_box.setSpacing(8)
        # Anordnung (Punkte 6+7): Loop und Geschwindigkeit als äußeres,
        # symmetrisches Paar; innen 10-s-Sprünge, Titel-Navigation, Play.
        # Loop | 10s zurück | Titel zurück | Play | Titel vor | 10s vor | Tempo
        self.repeat_btn = icon_button(icons.loop(), tr("repeat_tip_off"),
                                      self._toggle_repeat)
        self.back10_btn = icon_button(icons.replay10(), tr("back10_tip"),
                                      lambda: self._seek_relative(-10_000))
        # Punkt 7: |◄/►| springen zum vorherigen/nächsten Titel aus der
        # Zuletzt-verwendet-Liste; die 10-s-Sprünge liegen zusätzlich auf ←/→.
        self.prev_btn = icon_button(icons.skip_back(), tr("prev_track_tip"),
                                    self.play_previous_track)
        self.play_btn = QPushButton()
        self.play_btn.setObjectName("playButton")
        self.play_btn.setIcon(icons.play())
        self.play_btn.setIconSize(QSize(22, 22))
        self.play_btn.setEnabled(False)
        self.play_btn.clicked.connect(self.toggle_play)
        self.next_btn = icon_button(icons.skip_forward(), tr("next_track_tip"),
                                    self.play_next_track)
        self.fwd10_btn = icon_button(icons.forward10(), tr("fwd10_tip"),
                                     lambda: self._seek_relative(10_000))
        self.speed_btn = QPushButton("1.0×")
        self.speed_btn.setObjectName("speedButton")
        self.speed_btn.setToolTip(tr("speed_tip"))
        self.speed_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.speed_btn.setFixedWidth(46)
        self.speed_btn.clicked.connect(self._show_speed_menu)
        center_box.addWidget(self.repeat_btn)
        center_box.addWidget(self.back10_btn)
        center_box.addWidget(self.prev_btn)
        center_box.addWidget(self.play_btn)
        center_box.addWidget(self.next_btn)
        center_box.addWidget(self.fwd10_btn)
        center_box.addWidget(self.speed_btn)
        center_holder = QWidget()
        center_holder.setLayout(center_box)

        right_box = QHBoxLayout()
        right_box.setSpacing(6)
        # Punkt 12: Sync-Versatz für Online-Songtexte (nur dann sichtbar)
        self.sync_btn = icon_button(icons.offset(), tr("lyrics_offset_tip"),
                                    self._show_offset_popup)
        self.sync_btn.setVisible(False)
        self.volume_ctrl = VolumeControl()
        self.volume_ctrl.volume_changed.connect(self._on_volume)
        self.export_btn = icon_button(icons.export(), tr("export_tip"),
                                      self.export_transcript)
        self.export_btn.setEnabled(False)
        right_box.addWidget(self.sync_btn)
        right_box.addWidget(self.volume_ctrl)
        right_box.addWidget(self.export_btn)
        right_holder = QWidget()
        right_holder.setLayout(right_box)

        controls.addWidget(left_holder, 0, 0, Qt.AlignmentFlag.AlignLeft)
        controls.addWidget(center_holder, 0, 1, Qt.AlignmentFlag.AlignCenter)
        controls.addWidget(right_holder, 0, 2, Qt.AlignmentFlag.AlignRight)
        controls.setColumnStretch(0, 1)
        controls.setColumnStretch(1, 0)
        controls.setColumnStretch(2, 1)
        foot_lay.addLayout(controls)
        root.addWidget(footer)

        self.setCentralWidget(self.backdrop)

        # Statuszeile
        self.status_label = QLabel(tr("ready"))
        self.tags_label = QLabel("")
        self.diar_label = QLabel("")
        self.model_label = QLabel("")
        sb = self.statusBar()
        sb.setSizeGripEnabled(True)
        sb.addWidget(self.status_label, 1)
        sb.addPermanentWidget(self.tags_label)
        sb.addPermanentWidget(self.diar_label)
        sb.addPermanentWidget(self.model_label)

    def _build_player(self):
        self.audio_out = QAudioOutput()
        self.player = QMediaPlayer()
        self.player.setAudioOutput(self.audio_out)
        self.player.durationChanged.connect(self._on_duration)
        self.player.playbackStateChanged.connect(self._on_play_state)
        self.player.mediaStatusChanged.connect(self._on_media_status)
        self.player.errorOccurred.connect(self._on_player_error)
        volume = float(self.settings.value("volume", 1.0))
        muted = str(self.settings.value("muted", "false")).lower() == "true"
        self.volume_ctrl.set_state(volume, muted)
        self.audio_out.setVolume(self.volume_ctrl.effective_volume())
        rate = float(self.settings.value("playback_rate", 1.0))
        self._set_rate(rate if rate in SPEED_STEPS else 1.0)
        # Punkt 9: Der 100-ms-Takt läuft NUR während der Wiedergabe
        # (start/stop in _on_play_state), nicht dauerhaft im Leerlauf.
        self._tick = QTimer(self)
        self._tick.setInterval(100)
        self._tick.timeout.connect(self._on_tick)

    def _build_shortcuts(self):
        QShortcut(QKeySequence(Qt.Key.Key_Space), self, self.toggle_play)
        QShortcut(QKeySequence(Qt.Key.Key_Right), self,
                  lambda: self._seek_relative(10_000))
        QShortcut(QKeySequence(Qt.Key.Key_Left), self,
                  lambda: self._seek_relative(-10_000))
        QShortcut(QKeySequence.StandardKey.Open, self, self.open_dialog)
        QShortcut(QKeySequence("Ctrl+I"), self, self.show_properties)

    def _build_media_integration(self):
        self.smtc = SmtcBridge(self)
        if self.smtc.available:
            self.smtc.play_pause_requested.connect(self.toggle_play)
            self.smtc.next_requested.connect(self.play_next_track)
            self.smtc.previous_requested.connect(self.play_previous_track)

    # ------------------------------------------------------- Fenster-Chrome
    def showEvent(self, event):
        super().showEvent(event)
        if not self._chrome_applied:
            self._chrome_applied = True
            self._install_native_frame()
            apply_window_chrome(self)
            self._thumbbar = TaskbarMiniPlayer(int(self.winId()), self)
            self._thumbbar.previous_clicked.connect(self.play_previous_track)
            self._thumbbar.play_pause_clicked.connect(self.toggle_play)
            self._thumbbar.next_clicked.connect(self.play_next_track)

    def _install_native_frame(self):
        """Native Fensterstile setzen: Rahmenverhalten (Resize, Snap,
        Maximieren, Drag-Restore) bleibt Windows überlassen; die sichtbare
        Titelleiste verschwindet über WM_NCCALCSIZE in nativeEvent."""
        try:
            hwnd = int(self.winId())
            user32 = ctypes.windll.user32
            style = user32.GetWindowLongPtrW(hwnd, GWL_STYLE)
            style |= (WS_THICKFRAME | WS_CAPTION | WS_MAXIMIZEBOX
                      | WS_MINIMIZEBOX)
            user32.SetWindowLongPtrW(hwnd, GWL_STYLE, style)
            user32.SetWindowPos(hwnd, None, 0, 0, 0, 0, SWP_FLAGS)
        except Exception:
            pass

    def changeEvent(self, event):
        super().changeEvent(event)
        if (event.type() == event.Type.WindowStateChange
                and self.titlebar is not None):
            self.titlebar.update_max_icon()

    def _is_zoomed_native(self, hwnd: int) -> bool:
        """Maximiert-Zustand direkt von Windows abfragen.

        Qt aktualisiert isMaximized() erst NACH WM_SIZE – bei nativen Gesten
        (Titelleisten-Doppelklick, Drag-Restore, Aero-Snap) kommt
        WM_NCCALCSIZE aber schon während des Übergangs. Mit dem Qt-Zustand
        wird dann das Maximiert-Padding falsch angewendet: beim Drag-Restore
        blieb ein Rand mit nativem (blauem) Rahmen stehen, beim nativen
        Maximieren ragte das Fenster über den Bildschirm hinaus (oben
        abgeschnitten, Taskleiste verdeckt). IsZoomed liefert immer den
        Zustand, für den Windows gerade den Rahmen berechnet.

        WICHTIG: hwnd kommt aus der MSG-Struktur – hier NIEMALS winId()
        aufrufen: WM_NCCALCSIZE feuert schon während der Fenster-Erzeugung,
        winId() im WndProc löst dann eine Re-Entranz aus (0xC000041D)."""
        try:
            return bool(ctypes.windll.user32.IsZoomed(hwnd))
        except Exception:
            return self.isMaximized()

    def _hit_test(self, hwnd: int) -> int:
        if self.titlebar is None:
            return HTCLIENT
        pos = self.mapFromGlobal(QCursor.pos())
        w, h = self.width(), self.height()
        if not (0 <= pos.x() <= w and 0 <= pos.y() <= h):
            return HTCLIENT
        if not self._is_zoomed_native(hwnd):
            m = _RESIZE_MARGIN
            top, bottom = pos.y() <= m, pos.y() >= h - m
            left, right = pos.x() <= m, pos.x() >= w - m
            if top and left:
                return HTTOPLEFT
            if top and right:
                return HTTOPRIGHT
            if bottom and left:
                return HTBOTTOMLEFT
            if bottom and right:
                return HTBOTTOMRIGHT
            if top:
                return HTTOP
            if bottom:
                return HTBOTTOM
            if left:
                return HTLEFT
            if right:
                return HTRIGHT
        if pos.y() < TitleBar.HEIGHT:
            for btn in self.titlebar.caption_buttons():
                mapped = btn.mapTo(self, QPoint(0, 0))
                if (mapped.x() <= pos.x() <= mapped.x() + btn.width()
                        and mapped.y() <= pos.y() <= mapped.y() + btn.height()):
                    if btn is self.titlebar.max_btn:
                        return HTMAXBUTTON  # Snap-Layouts (Windows 11)
                    return HTCLIENT
            return HTCAPTION
        return HTCLIENT

    def nativeEvent(self, event_type, message):
        if event_type == b"windows_generic_MSG":
            try:
                msg = wintypes.MSG.from_address(int(message))
            except Exception:
                return super().nativeEvent(event_type, message)

            if msg.message == WM_NCCALCSIZE and msg.wParam:
                # Client-Bereich = ganzes Fenster (eigene Titelleiste).
                # Maximiert ragt das Fenster um die Rahmenbreite über den
                # Bildschirm hinaus -> Rechteck entsprechend einrücken,
                # sonst bleiben Ränder abgeschnitten (Punkt 1).
                # WICHTIG: nativen Zustand (IsZoomed) abfragen, nicht Qts
                # isMaximized() – das hinkt bei nativen Gesten hinterher
                # (Punkte 5/14/15: blauer Rand, Taskleiste verdeckt).
                if self._is_zoomed_native(msg.hWnd):
                    try:
                        rect = wintypes.RECT.from_address(msg.lParam)
                        user32 = ctypes.windll.user32
                        pad = (user32.GetSystemMetrics(SM_CXSIZEFRAME)
                               + user32.GetSystemMetrics(SM_CXPADDEDBORDER))
                        rect.left += pad
                        rect.top += pad
                        rect.right -= pad
                        rect.bottom -= pad
                    except Exception:
                        pass
                return True, 0

            if msg.message == WM_NCHITTEST:
                code = self._hit_test(msg.hWnd)
                if code != HTCLIENT:
                    if self.titlebar is not None:
                        self.titlebar.set_max_hover(code == HTMAXBUTTON)
                    return True, code
                if self.titlebar is not None:
                    self.titlebar.set_max_hover(False)

            elif msg.message == WM_NCMOUSEMOVE:
                if self.titlebar is not None:
                    self.titlebar.set_max_hover(msg.wParam == HTMAXBUTTON)

            elif msg.message in (WM_NCMOUSELEAVE, WM_MOUSEMOVE):
                if self.titlebar is not None:
                    self.titlebar.set_max_hover(False)

            elif (msg.message == WM_NCLBUTTONDBLCLK
                    and msg.wParam == HTCAPTION
                    and self.titlebar is not None):
                # Titelleisten-Doppelklick: exakt denselben Weg gehen wie der
                # Maximieren-Button (showMaximized/showNormal über Qt) statt
                # der nativen SC_MAXIMIZE-Verarbeitung – so verhalten sich
                # Geste und Button garantiert identisch (Punkte 14/15).
                self.titlebar._toggle_max()
                return True, 0

            elif (msg.message == WM_NCLBUTTONDOWN
                    and msg.wParam == HTMAXBUTTON):
                return True, 0  # Standard-Verarbeitung unterdrücken

            elif (msg.message == WM_NCLBUTTONUP
                    and msg.wParam == HTMAXBUTTON
                    and self.titlebar is not None):
                self.titlebar.set_max_hover(False)
                self.titlebar._toggle_max()
                return True, 0

            thumbbar = getattr(self, "_thumbbar", None)
            if thumbbar is not None:
                try:
                    if thumbbar.handle_native_message(msg):
                        return True, 0
                except Exception:
                    pass
        return super().nativeEvent(event_type, message)

    # ------------------------------------------------------------- Öffnen
    def open_dialog(self):
        start_dir = str(self.settings.value("last_dir", os.path.expanduser("~")))
        file_filter = (f"{tr('filter_audio')} ({_EXT_PATTERN});;"
                       f"{tr('filter_all')} (*)")
        path, _ = QFileDialog.getOpenFileName(self, tr("open_dialog_title"),
                                              start_dir, file_filter)
        if path:
            self.open_path(path)

    def _speakers_enabled(self) -> bool:
        return str(self.settings.value("speakers_enabled", "false")).lower() == "true"

    def open_path(self, path: str, from_nav: bool = False):
        path = os.path.abspath(path)
        if not os.path.isfile(path):
            QMessageBox.warning(self, APP_NAME, tr("file_missing", path=path))
            return
        self.settings.setValue("last_dir", os.path.dirname(path))
        self._add_recent(path, keep_order=from_nav)

        self._gen += 1
        gen = self._gen
        for t in (self._transcriber, self._tagger, self._diarizer):
            if t is not None and t.isRunning():
                t.cancel()
        self._diar_started = False
        self._diarizer = None
        self._cover_png = None
        self._cover_image = None
        self._official_lyrics = False
        self._official_line_dicts = None
        self._align_active = False
        self._whisper_lines = []
        self._lyrics_offset_ms = 0
        self.sync_btn.setVisible(False)

        self._path = path
        base = os.path.basename(path)
        self.setWindowTitle(f"{APP_NAME} — {base}")
        self.titlebar.set_title(f"{APP_NAME} — {base}")
        self.track_title.setText(base)
        self.track_status.setText(tr("preparing"))
        self.lyrics.clear()
        self.backdrop.set_cover(None)
        self.cover_label.setPixmap(_rounded_cover(None))
        self.export_btn.setEnabled(False)
        self.tags_label.setText("")
        self.diar_label.setText("")
        self.model_label.setText("")

        # Wiedergabe (Kern-Funktion, läuft immer)
        self.player.stop()
        self.player.setSource(QUrl.fromLocalFile(path))
        self.play_btn.setEnabled(True)
        self.player.play()
        self.smtc.update_metadata(base)
        if self._mini is not None and self._mini.isVisible():
            self._mini.set_title(base)

        # Modulare Verfügbarkeit: jede KI-Komponente kann einzeln fehlen
        # oder in den Einstellungen deaktiviert sein (Punkt 10)
        has_transcription = (packs.transcription_available()
                             and self._pack_enabled("whisper_enabled"))
        has_sounds = (packs.sounds_available() and soundtags.model_available()
                      and self._pack_enabled("sounds_enabled"))

        if not (has_transcription or has_sounds):
            self._stack.setCurrentWidget(self.placeholder)
            self.progress_strip.hide()
            self.status_label.setText(tr("ai_missing_title"))
            self.track_status.setText(tr("ready"))
            if not self._ai_hint_shown:
                self._ai_hint_shown = True
                answer = QMessageBox.question(
                    self, tr("ai_missing_title"), tr("ai_missing_text"))
                if answer == QMessageBox.StandardButton.Yes:
                    self.show_settings()
            return

        if has_transcription:
            self._stack.setCurrentWidget(self._loading_page)
            self.loading_title.setText(tr("hw_analyzing"))
            self.progress_strip.setRange(0, 0)
            self.progress_strip.show()
            if self._thumbbar is not None:
                self._thumbbar.set_progress(None, indeterminate=True)

            model_override = str(self.settings.value("model_override", "auto"))
            device_override = str(self.settings.value("device_override", "auto"))
            t = TranscriberThread(path, model_override, device_override, self)
            t.status.connect(partial(self._guarded, gen, self._on_transcribe_status))
            t.model_info.connect(partial(self._guarded, gen, self.model_label.setText))
            t.line_ready.connect(partial(self._guarded, gen, self._on_line))
            t.progress.connect(partial(self._guarded, gen, self._on_progress))
            t.finished_ok.connect(partial(self._guarded, gen, self._on_transcribe_done))
            t.failed.connect(partial(self._guarded, gen, self._on_transcribe_failed))
            self._transcriber = t
            t.start()
        else:
            self._stack.setCurrentWidget(self.placeholder)
            self.progress_strip.hide()

        if has_sounds:
            tagger = SoundTagThread(path, self)
            tagger.status.connect(partial(self._guarded, gen, self.tags_label.setText))
            tagger.tag_ready.connect(partial(self._guarded, gen, self._on_tag))
            tagger.done.connect(partial(self._guarded, gen, self._on_tags_done))
            tagger.failed.connect(partial(self._guarded, gen, self._on_tags_failed))
            self._tagger = tagger
            tagger.start()

        self.lyrics.set_show_speakers(self._speakers_enabled())
        if self._speakers_enabled() and has_transcription:
            self._start_diarization()

    def _guarded(self, gen: int, slot, *args):
        """Verwirft Signale von Threads einer früher geöffneten Datei."""
        if gen == self._gen:
            slot(*args)

    # -------------------------------------------------------- Zuletzt benutzt
    def _recent_enabled(self) -> bool:
        return str(self.settings.value("recent_enabled", "true")).lower() == "true"

    def _add_recent(self, path: str, keep_order: bool = False):
        if not self._recent_enabled():
            return
        entries = self._recent_entries(existing_only=False)
        if keep_order and path in entries:
            return  # Titel-Navigation (Punkt 7): Reihenfolge nicht verändern
        entries = [e for e in entries if e != path]
        entries.insert(0, path)
        self.settings.setValue("recent_files", entries[:12])

    def _recent_entries(self, existing_only: bool = True) -> list[str]:
        entries = self.settings.value("recent_files", []) or []
        if isinstance(entries, str):
            entries = [entries]
        if existing_only:
            entries = [e for e in entries if os.path.isfile(e)]
        return entries

    # Punkt 7: |◄/►| navigieren durch die Zuletzt-verwendet-Liste. Die Liste
    # ist neueste-zuerst sortiert: „vorheriger Titel“ = der davor gespielte
    # (ein Eintrag weiter unten), „nächster Titel“ = ein Eintrag weiter oben.
    def play_previous_track(self):
        self._play_neighbor(+1)

    def play_next_track(self):
        self._play_neighbor(-1)

    def _play_neighbor(self, step: int):
        entries = self._recent_entries()
        if not entries:
            return
        if self._path in entries:
            idx = entries.index(self._path) + step
        else:
            idx = 0  # ohne aktuellen Titel: neuesten Eintrag spielen
        if 0 <= idx < len(entries):
            self.open_path(entries[idx], from_nav=True)

    def _show_recent_menu(self):
        menu = QMenu(self)
        entries = self._recent_entries()
        if not self._recent_enabled() or not entries:
            action = menu.addAction(tr("recent_menu"))
            action.setEnabled(False)
        else:
            for entry in entries[:12]:
                action = menu.addAction(os.path.basename(entry))
                action.triggered.connect(partial(self.open_path, entry))
            menu.addSeparator()
            clear = menu.addAction(tr("recent_clear"))
            clear.triggered.connect(
                lambda: self.settings.setValue("recent_files", []))
        menu.exec(self.recent_btn.mapToGlobal(
            QPoint(0, self.recent_btn.height())))

    # ------------------------------------------------- Transkript-Signale
    def _on_transcribe_status(self, text: str):
        if self._official_lyrics:
            return
        self.status_label.setText(text)
        self.loading_title.setText(text)

    def _on_line(self, seg: dict):
        if self._official_lyrics:
            if self._align_active:
                # Punkt 13: Whisper-Zeilen still sammeln (nicht anzeigen) –
                # sie liefern die Zeitstempel fürs Forced Alignment.
                self._whisper_lines.append(seg)
            return
        self.lyrics.add_line(seg)
        self._show_lyrics_page()
        if not self.export_btn.isEnabled():
            self.export_btn.setEnabled(True)

    def _show_lyrics_page(self):
        if self._stack.currentWidget() is not self.lyrics:
            self._stack.setCurrentWidget(self.lyrics)

    def _on_progress(self, frac: float):
        if self._official_lyrics:
            return
        if self.progress_strip.maximum() == 0:
            self.progress_strip.setRange(0, 1000)
        self.progress_strip.setValue(int(frac * 1000))
        self.track_status.setText(tr("transcribe_pct", pct=f"{frac * 100:.0f}"))
        if self._thumbbar is not None:
            self._thumbbar.set_progress(frac)

    def _on_transcribe_done(self, language: str):
        if self._official_lyrics:
            if self._align_active:
                self._align_active = False
                self._apply_alignment()
            return
        self.progress_strip.hide()
        if self._thumbbar is not None:
            self._thumbbar.set_progress(None)
        lang_part = f" · {language}" if language else ""
        n = sum(1 for l in self.lyrics.lines if not l.seg.get("is_tag"))
        self.status_label.setText(tr("transcript_done", n=n, lang=lang_part))
        self.track_status.setText(tr("transcript_done_short", lang=lang_part))
        if not self.lyrics.lines:
            self._stack.setCurrentWidget(self.placeholder)
        self._prune_overlapping_tags()

    def _on_transcribe_failed(self, message: str):
        if self._official_lyrics:
            self._align_active = False
            return
        self.progress_strip.hide()
        if self._thumbbar is not None:
            self._thumbbar.set_progress(None)
        self.status_label.setText(tr("transcript_failed"))
        self.track_status.setText(tr("transcript_failed"))
        if not self.lyrics.lines:
            self._stack.setCurrentWidget(self.placeholder)
        QMessageBox.critical(self, APP_NAME,
                             tr("transcript_failed_msg", msg=message))

    # ---------------------------------------------------- Geräusch-Tags
    def _on_tag(self, event: dict):
        if self._official_lyrics:
            return
        seg = dict(event, is_tag=True, words=[])
        self.lyrics.add_line(seg)
        self._show_lyrics_page()

    def _on_tags_done(self, events: list):
        if self._official_lyrics:
            return
        n = len(events)
        self.tags_label.setText(tr("tags_count", n=n) if n else "")
        if self._transcriber is not None and not self._transcriber.isRunning():
            self._prune_overlapping_tags()

    def _on_tags_failed(self, message: str):
        if self._official_lyrics:
            return
        self.tags_label.setText(tr("tags_failed"))
        self.status_label.setText(f"{tr('tags_failed')}: {message}")

    def _prune_overlapping_tags(self):
        speech = [(float(l.seg["start"]), float(l.seg["end"]))
                  for l in self.lyrics.lines if not l.seg.get("is_tag")]
        if not speech:
            return

        def covered(seg):
            length = max(0.01, seg["end"] - seg["start"])
            overlap = sum(min(seg["end"], e) - max(seg["start"], s)
                          for s, e in speech
                          if e > seg["start"] and s < seg["end"])
            return overlap / length > 0.5

        removed = self.lyrics.remove_tag_lines(covered)
        if removed:
            remaining = sum(1 for l in self.lyrics.lines if l.seg.get("is_tag"))
            self.tags_label.setText(
                tr("tags_count", n=remaining) if remaining else "")

    # ------------------------------------------------------ Sprechertrennung
    def apply_speaker_setting(self):
        """Nach Änderungen im Einstellungsdialog live anwenden."""
        enabled = self._speakers_enabled()
        self.lyrics.set_show_speakers(enabled)
        if (enabled and self._path and not self._diar_started
                and not self._official_lyrics and packs.speakers_available()):
            self._start_diarization()

    def _start_diarization(self):
        if (self._diar_started or not self._path
                or not packs.speakers_available()):
            return
        token = str(self.settings.value("hf_token", "")).strip()
        if not diarizer.bundled_models_available() and not token:
            self.diar_label.setText(tr("diar_failed"))
            return
        gen = self._gen
        self._diar_started = True
        d = DiarizerThread(self._path, token, self)
        d.status.connect(partial(self._guarded, gen, self.diar_label.setText))
        d.done.connect(partial(self._guarded, gen, self._on_turns))
        d.failed.connect(partial(self._guarded, gen, self._on_diar_failed))
        self._diarizer = d
        d.start()

    def _on_turns(self, turns: list):
        if self._official_lyrics:
            return
        self.lyrics.set_turns(turns)
        self.diar_label.setText(tr("diar_count", n=self.lyrics.speaker_count()))

    def _on_diar_failed(self, message: str):
        self._diar_started = False
        if self._official_lyrics:
            return
        self.diar_label.setText(tr("diar_failed"))
        QMessageBox.warning(self, APP_NAME, f"{tr('diar_failed')}:\n\n{message}")

    # ------------------------------------------------------------- Player
    def toggle_play(self):
        if not self._path:
            self.open_dialog()
            return
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def _on_play_state(self, state):
        playing = state == QMediaPlayer.PlaybackState.PlayingState
        self.play_btn.setIcon(icons.pause() if playing else icons.play())
        self.smtc.set_playing(playing)
        if self._thumbbar is not None:
            self._thumbbar.set_playing(playing)
        if self._mini is not None:
            self._mini.set_playing(playing)
        # Punkt 9: Takt nur bei laufender Wiedergabe
        if playing:
            self._tick.start()
        else:
            self._tick.stop()
            self._sync_position_ui()

    def _on_duration(self, ms: int):
        self.slider.setRange(0, int(ms))
        self.dur_label.setText(fmt_time(ms / 1000))

    def _on_media_status(self, status):
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            if self._repeat:
                self.player.setPosition(0)
                self.player.play()
            return
        if status != QMediaPlayer.MediaStatus.LoadedMedia:
            return
        md = self.player.metaData()
        artist = str(md.value(QMediaMetaData.Key.AlbumArtist)
                     or md.value(QMediaMetaData.Key.ContributingArtist) or "")
        title = str(md.value(QMediaMetaData.Key.Title) or "")
        online = (str(self.settings.value("cover_search_enabled", "false"))
                  .lower() == "true")

        image = None
        for key in (QMediaMetaData.Key.ThumbnailImage,
                    QMediaMetaData.Key.CoverArtImage):
            value = md.value(key)
            if isinstance(value, QImage) and not value.isNull():
                image = value
                break
        if image is not None:
            self._apply_cover(image)
        elif online and self._path:
            gen = self._gen
            ct = CoverSearchThread(self._path, artist, title, self)
            ct.found.connect(partial(self._guarded, gen, self._on_cover_found))
            self._cover_thread = ct
            ct.start()

        # Punkt 11: offizielle Songtexte für erkannte Musik (gleicher
        # Schalter; funktioniert auch ohne installierte KI-Pakete)
        if online and self._path:
            gen = self._gen
            lt = LyricsSearchThread(self._path, artist, title,
                                    self.player.duration() / 1000.0, self)
            lt.found.connect(partial(self._guarded, gen, self._on_lyrics_found))
            self._lyrics_thread = lt
            lt.start()

    def _on_cover_found(self, image_path: str):
        image = QImage(image_path)
        if not image.isNull():
            self._apply_cover(image)

    def _on_lyrics_found(self, lines: list, track: str):
        """Offizieller synchronisierter Songtext ersetzt die KI-Transkription."""
        self._official_lyrics = True
        self._official_line_dicts = [dict(line) for line in lines]
        self._lyrics_offset_ms = self._load_lyrics_offset()

        # Punkt 13: Läuft Whisper noch, weiterlaufen lassen und die bereits
        # angezeigten KI-Zeilen als Timing-Quelle übernehmen; der offizielle
        # Text wird nach Abschluss mit den Whisper-Zeitstempeln synchronisiert.
        self._whisper_lines = [dict(l.seg) for l in self.lyrics.lines
                               if not l.seg.get("is_tag")]
        transcriber_running = (self._transcriber is not None
                               and self._transcriber.isRunning())
        want_align = (self._pack_enabled("align_enabled")
                      and packs.transcription_available()
                      and self._pack_enabled("whisper_enabled"))
        self._align_active = transcriber_running and want_align
        if transcriber_running and not want_align:
            self._transcriber.cancel()
        if self._tagger is not None and self._tagger.isRunning():
            self._tagger.cancel()

        self.lyrics.clear()
        self.lyrics.set_show_speakers(False)
        for line in lines:
            self.lyrics.add_line(line)
        self._show_lyrics_page()
        self.progress_strip.hide()
        if self._thumbbar is not None:
            self._thumbbar.set_progress(None)
        self.export_btn.setEnabled(True)
        self.sync_btn.setVisible(True)
        self.tags_label.setText("")
        self.diar_label.setText("")
        self.status_label.setText(tr("lyrics_online_ok", track=track))
        self.track_status.setText(tr("lyrics_online_ok", track=track))
        if self._align_active:
            self.status_label.setText(tr("align_running"))
        elif want_align and self._whisper_lines:
            self._apply_alignment()  # Whisper war schon fertig
        self._sync_position_ui()

    def _apply_alignment(self):
        """Punkt 13: Zeilen-Timings des offiziellen Songtexts durch präzise
        Whisper-Wort-Zeitstempel ersetzen (Forced Alignment)."""
        from .align import align_lines
        if not (self._official_lyrics and self._official_line_dicts
                and self._whisper_lines):
            return
        aligned, quality = align_lines(self._official_line_dicts,
                                       self._whisper_lines)
        if aligned is None:
            self.status_label.setText(tr("align_low_quality"))
            return
        self.lyrics.clear()
        for line in aligned:
            self.lyrics.add_line(line)
        self.status_label.setText(
            tr("align_done", pct=f"{quality * 100:.0f}"))
        self._sync_position_ui()

    def _apply_cover(self, image: QImage):
        self._cover_image = image
        self.backdrop.set_cover(image)
        self.cover_label.setPixmap(_rounded_cover(image))
        if self._mini is not None:
            self._mini.set_cover(_rounded_cover(image, 64, 10))
        path = os.path.join(tempfile.gettempdir(), "lyrix_cover.png")
        if image.save(path, "PNG"):
            self._cover_png = path
        self.smtc.update_metadata(os.path.basename(self._path or ""),
                                  thumb_path=self._cover_png)

    def _sync_position_ui(self):
        """Slider/Zeit/Lyrics einmalig aktualisieren (z. B. nach Seek im
        pausierten Zustand, während der Takt-Timer steht)."""
        pos = int(self.player.position())
        if not self.slider.isSliderDown():
            self.slider.setValue(pos)
        self.pos_label.setText(fmt_time(pos / 1000))
        t = pos / 1000
        if self._official_lyrics and self._lyrics_offset_ms:
            # Punkt 12: positiver Versatz = Songtext erscheint später
            t -= self._lyrics_offset_ms / 1000.0
        self.lyrics.set_time(t)

    def _on_tick(self):
        self._sync_position_ui()
        if self._mini is not None and self._mini.isVisible():
            idx = self.lyrics._current
            if 0 <= idx < len(self.lyrics.lines):
                self._mini.set_line(self.lyrics.lines[idx].seg["text"])

    def _on_slider_moved(self, value: int):
        self.player.setPosition(int(value))
        self.lyrics.resume_autoscroll()
        self._sync_position_ui()

    def _seek_seconds(self, seconds: float):
        self.player.setPosition(int(seconds * 1000))
        if self.player.playbackState() != QMediaPlayer.PlaybackState.PlayingState:
            self.player.play()
        self.lyrics.resume_autoscroll()

    def _seek_relative(self, delta_ms: int):
        self.player.setPosition(max(0, int(self.player.position()) + delta_ms))
        self.lyrics.resume_autoscroll()
        self._sync_position_ui()

    def _on_player_error(self, _error, message: str):
        if message:
            self.status_label.setText(tr("playback_error", msg=message))

    # ----------------------------------------------------- Lautstärke/Tempo
    def _on_volume(self, volume: float):
        self.audio_out.setVolume(volume)
        self.settings.setValue("volume", self.volume_ctrl._volume)
        self.settings.setValue(
            "muted", "true" if self.volume_ctrl.is_muted() else "false")

    def _set_rate(self, rate: float):
        self.player.setPlaybackRate(rate)
        self.speed_btn.setText(f"{rate:g}×")
        self.settings.setValue("playback_rate", rate)

    def _show_speed_menu(self):
        menu = QMenu(self)
        current = self.player.playbackRate()
        for rate in SPEED_STEPS:
            action = menu.addAction(f"{rate:g}×")
            action.setCheckable(True)
            action.setChecked(abs(rate - current) < 0.01)
            action.triggered.connect(partial(self._set_rate, rate))
        menu.exec(self.speed_btn.mapToGlobal(
            QPoint(0, -menu.sizeHint().height() - 4)))

    # ------------------------------------------- Songtext-Versatz (Punkt 12)
    def _offset_key(self) -> str:
        digest = hashlib.sha1((self._path or "").lower()
                              .encode("utf-8")).hexdigest()[:16]
        return f"lyrics_offset/{digest}"

    def _load_lyrics_offset(self) -> int:
        try:
            return int(self.settings.value(self._offset_key(), 0))
        except (TypeError, ValueError):
            return 0

    def _set_lyrics_offset(self, ms: int):
        self._lyrics_offset_ms = int(ms)
        if ms:
            self.settings.setValue(self._offset_key(), int(ms))
        else:
            self.settings.remove(self._offset_key())  # neutral -> aufräumen
        self._sync_position_ui()
        self.lyrics.refresh_all()

    def _show_offset_popup(self):
        """Kleiner Regler über dem Sync-Knopf: Songtext ±2 s verschieben."""
        popup = QWidget(self, Qt.WindowType.Popup)
        popup.setObjectName("offsetPopup")
        popup.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        lay = QVBoxLayout(popup)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(8)

        title = QLabel(tr("lyrics_offset_label"))
        title.setObjectName("offsetTitle")
        value = QLabel("")
        value.setObjectName("offsetValue")
        slider = ClickSlider()
        slider.setRange(-2000, 2000)
        slider.setSingleStep(50)
        slider.setPageStep(250)
        slider.setValue(self._lyrics_offset_ms)
        slider.setFixedWidth(260)
        hint = QLabel(tr("lyrics_offset_hint"))
        hint.setObjectName("offsetHint")
        reset = QPushButton(tr("offset_reset"))
        reset.setObjectName("offsetReset")

        def show_value(ms: int):
            sign = "+" if ms > 0 else ""
            value.setText(f"{sign}{ms / 1000:.2f} s")

        def on_change(ms: int):
            show_value(ms)
            self._set_lyrics_offset(ms)

        slider.valueChanged.connect(on_change)
        reset.clicked.connect(lambda: slider.setValue(0))
        show_value(self._lyrics_offset_ms)

        head = QHBoxLayout()
        head.addWidget(title, 1)
        head.addWidget(value)
        lay.addLayout(head)
        lay.addWidget(slider)
        foot = QHBoxLayout()
        foot.addWidget(hint, 1)
        foot.addWidget(reset)
        lay.addLayout(foot)

        popup.adjustSize()
        anchor = self.sync_btn.mapToGlobal(QPoint(
            self.sync_btn.width() // 2 - popup.width() // 2,
            -popup.height() - 10))
        popup.move(anchor)
        popup.show()

    # ------------------------------------------------------------ Repeat
    def _toggle_repeat(self):
        from . import theme
        self._repeat = not self._repeat
        color = theme.ACCENT if self._repeat else "#e8e8e8"
        self.repeat_btn.setIcon(icons.loop(color))
        self.repeat_btn.setToolTip(tr("repeat_tip_on") if self._repeat
                                   else tr("repeat_tip_off"))

    # -------------------------------------------------------- Mini-Player
    def toggle_mini_player(self):
        if self._mini is None:
            self._mini = MiniPlayer()
            self._mini.play_pause.connect(self.toggle_play)
            self._mini.restore_requested.connect(self._restore_from_mini)
        if self._mini.isVisible():
            self._restore_from_mini()
            return
        self._mini.set_title(os.path.basename(self._path or APP_NAME))
        self._mini.set_cover(_rounded_cover(self._cover_image, 64, 10))
        self._mini.set_playing(self.player.playbackState()
                               == QMediaPlayer.PlaybackState.PlayingState)
        pos = self.settings.value("mini_pos")
        if pos is not None:
            self._mini.move(pos)
        else:
            screen = self.screen().availableGeometry()
            self._mini.move(screen.right() - self._mini.width() - 24,
                            screen.top() + 24)
        self._mini.show()
        self.hide()

    def _restore_from_mini(self):
        if self._mini is not None and self._mini.isVisible():
            self.settings.setValue("mini_pos", self._mini.pos())
            self._mini.hide()
        self.show()
        self.raise_()
        self.activateWindow()

    # ------------------------------------------------------ Eigenschaften
    def show_properties(self):
        if not self._path:
            return
        dialog = QDialog(self)
        dialog.setWindowTitle(tr("props_title"))
        dialog.setMinimumWidth(460)
        lay = QVBoxLayout(dialog)
        form = QFormLayout()
        form.setVerticalSpacing(8)

        md = self.player.metaData()
        try:
            size_bytes = os.path.getsize(self._path)
            size_text = (f"{size_bytes / (1 << 20):.1f} MB"
                         if size_bytes >= 1 << 20
                         else f"{size_bytes / 1024:.0f} KB")
        except OSError:
            size_text = "—"
        duration = self.player.duration()
        bitrate = md.value(QMediaMetaData.Key.AudioBitRate)
        codec = md.value(QMediaMetaData.Key.AudioCodec)
        file_fmt = md.value(QMediaMetaData.Key.FileFormat)

        rows = [
            (tr("props_name"), os.path.basename(self._path)),
            (tr("props_path"), os.path.dirname(self._path)),
            (tr("props_format"), str(file_fmt) if file_fmt else
             os.path.splitext(self._path)[1].lstrip(".").upper()),
            (tr("props_size"), size_text),
            (tr("props_duration"), fmt_time(duration / 1000) if duration else "—"),
            (tr("props_bitrate"),
             f"{int(bitrate) // 1000} kbit/s" if bitrate else "—"),
            (tr("props_codec"), str(codec) if codec else "—"),
        ]
        for label, value in rows:
            value_label = QLabel(str(value))
            value_label.setWordWrap(True)
            value_label.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse)
            form.addRow(label + ":", value_label)
        lay.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dialog.reject)
        buttons.clicked.connect(lambda _btn: dialog.accept())
        lay.addWidget(buttons)
        dialog.exec()

    # ------------------------------------------------------------- Export
    def export_transcript(self):
        rows = self.lyrics.export_rows()
        if not rows:
            return
        base = os.path.splitext(self._path or "transcript")[0]
        file_filter = (f"{tr('export_txt')} (*.txt);;"
                       f"{tr('export_srt')} (*.srt)")
        path, chosen = QFileDialog.getSaveFileName(
            self, tr("export_title"), base + ".txt", file_filter)
        if not path:
            return
        if "srt" in chosen or path.lower().endswith(".srt"):
            content = exporter.to_srt(rows)
        else:
            content = exporter.to_txt(rows)
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(content)
            self.status_label.setText(tr("exported", name=os.path.basename(path)))
        except OSError as exc:
            QMessageBox.critical(self, APP_NAME, tr("export_failed", msg=exc))

    # -------------------------------------------------------- Sonstiges
    def show_settings(self):
        SettingsDialog(self.settings, self).exec()
        self.apply_pack_settings()

    def _pack_enabled(self, key: str, default: str = "true") -> bool:
        return str(self.settings.value(key, default)).lower() == "true"

    def apply_pack_settings(self):
        """Nach dem Einstellungsdialog (Punkte 10/11): deaktivierte oder
        deinstallierte Komponenten wirklich stilllegen – laufende Threads
        abbrechen, Referenzen lösen und belegten Speicher freigeben, statt
        nur den Schalter umzulegen."""
        whisper_on = (packs.transcription_available()
                      and self._pack_enabled("whisper_enabled"))
        sounds_on = (packs.sounds_available() and soundtags.model_available()
                     and self._pack_enabled("sounds_enabled"))
        speakers_on = (packs.speakers_available()
                       and self._speakers_enabled())

        if not whisper_on and self._transcriber is not None:
            if self._transcriber.isRunning():
                self._transcriber.cancel()
            self._transcriber = None
            self._align_active = False
            self.progress_strip.hide()
            if self._thumbbar is not None:
                self._thumbbar.set_progress(None)
        if not sounds_on and self._tagger is not None:
            if self._tagger.isRunning():
                self._tagger.cancel()
            self._tagger = None
        if not speakers_on and self._diarizer is not None:
            if self._diarizer.isRunning():
                self._diarizer.cancel()
            self._diarizer = None
            self._diar_started = False

        self.apply_speaker_setting()
        packs.release_memory()

    def dragEnterEvent(self, event):
        urls = event.mimeData().urls() if event.mimeData().hasUrls() else []
        if urls and urls[0].isLocalFile():
            ext = os.path.splitext(urls[0].toLocalFile())[1].lower()
            if ext in AUDIO_EXTS:
                event.acceptProposedAction()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls and urls[0].isLocalFile():
            self.open_path(urls[0].toLocalFile())

    def closeEvent(self, event):
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.sync()
        if self._mini is not None:
            self._mini.close()
        for t in (self._transcriber, self._tagger):
            if t is not None and t.isRunning():
                t.cancel()
        self.player.stop()
        self.hide()
        event.accept()
        # Whisper/pyannote/PANNs-Threads lassen sich nicht sauber unterbrechen –
        # der Prozess wird bewusst hart beendet, damit das Fenster nicht
        # minutenlang auf laufende Modelle warten muss.
        os._exit(0)
