"""System Media Transport Controls (SMTC) – Windows-Medienintegration.

Nutzt einen unsichtbaren WinRT-MediaPlayer nur als SMTC-Anker (der Ton kommt
weiterhin aus Qt). Damit erscheint lyrix im Windows-Medien-Flyout und
auf dem Sperrbildschirm mit Titel, Cover und Play/Pause/Weiter/Zurück.

Fällt bei fehlenden winrt-Paketen lautlos aus – die App läuft ohne weiter.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal


class SmtcBridge(QObject):
    play_pause_requested = Signal()
    next_requested = Signal()
    previous_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.available = False
        try:
            from winrt.windows.media import (MediaPlaybackStatus,
                                             MediaPlaybackType,
                                             SystemMediaTransportControlsButton)
            from winrt.windows.media.playback import MediaPlayer

            self._Btn = SystemMediaTransportControlsButton
            self._Status = MediaPlaybackStatus
            self._Type = MediaPlaybackType

            self._mp = MediaPlayer()
            self._mp.command_manager.is_enabled = False
            smtc = self._mp.system_media_transport_controls
            smtc.is_enabled = True
            smtc.is_play_enabled = True
            smtc.is_pause_enabled = True
            smtc.is_next_enabled = True
            smtc.is_previous_enabled = True
            self._smtc = smtc
            self._token = smtc.add_button_pressed(self._on_button)
            self.available = True
        except Exception:
            self._smtc = None

    # Läuft auf einem WinRT-Thread; Qt-Signale sind cross-thread-sicher
    # (automatisch queued), also nur emittieren, nichts anfassen.
    def _on_button(self, _sender, args):
        try:
            b = args.button
            if b in (self._Btn.PLAY, self._Btn.PAUSE):
                self.play_pause_requested.emit()
            elif b == self._Btn.NEXT:
                self.next_requested.emit()
            elif b == self._Btn.PREVIOUS:
                self.previous_requested.emit()
        except Exception:
            pass

    def update_metadata(self, title: str, artist: str = "lyrix",
                        thumb_path: str | None = None):
        if not self.available:
            return
        try:
            du = self._smtc.display_updater
            du.type = self._Type.MUSIC
            du.music_properties.title = title
            du.music_properties.artist = artist
            if thumb_path:
                from winrt.windows.foundation import Uri
                from winrt.windows.storage.streams import RandomAccessStreamReference
                uri = Uri("file:///" + thumb_path.replace("\\", "/"))
                du.thumbnail = RandomAccessStreamReference.create_from_uri(uri)
            du.update()
        except Exception:
            pass

    def set_playing(self, playing: bool):
        if not self.available:
            return
        try:
            self._smtc.playback_status = (self._Status.PLAYING if playing
                                          else self._Status.PAUSED)
        except Exception:
            pass
