"""Taskleisten-Miniplayer: Zurück/Play-Pause/Weiter-Buttons im Hover-Vorschau-
fenster des Taskleisten-Icons (ITaskbarList3-ThumbBar) plus Fortschritts-
anzeige auf dem Taskleisten-Icon selbst.

Reine COM-Anbindung über comtypes mit manuell deklarierten Interfaces –
kein Typelib-Codegen, funktioniert daher auch in der PyInstaller-EXE.
"""

from __future__ import annotations

import ctypes
import os
from ctypes import wintypes

from PySide6.QtCore import QObject, Signal

from .util import resource_path

BTN_PREV, BTN_PLAYPAUSE, BTN_NEXT = 1001, 1002, 1003

WM_COMMAND = 0x0111
THBN_CLICKED = 0x1800

_THB_ICON = 0x2
_THB_TOOLTIP = 0x4
_THB_FLAGS = 0x8
_THBF_ENABLED = 0

# SetProgressState-Flags
TBPF_NOPROGRESS = 0x0
TBPF_INDETERMINATE = 0x1
TBPF_NORMAL = 0x2


class THUMBBUTTON(ctypes.Structure):
    _fields_ = [
        ("dwMask", wintypes.UINT),
        ("iId", wintypes.UINT),
        ("iBitmap", wintypes.UINT),
        ("hIcon", wintypes.HICON),
        ("szTip", ctypes.c_wchar * 260),
        ("dwFlags", wintypes.UINT),
    ]


def _interfaces():
    from comtypes import COMMETHOD, GUID, HRESULT, IUnknown

    class ITaskbarList(IUnknown):
        _iid_ = GUID("{56FDF342-FD6D-11D0-958A-006097C9A090}")
        _methods_ = [
            COMMETHOD([], HRESULT, "HrInit"),
            COMMETHOD([], HRESULT, "AddTab", (["in"], wintypes.HWND, "hwnd")),
            COMMETHOD([], HRESULT, "DeleteTab", (["in"], wintypes.HWND, "hwnd")),
            COMMETHOD([], HRESULT, "ActivateTab", (["in"], wintypes.HWND, "hwnd")),
            COMMETHOD([], HRESULT, "SetActiveAlt", (["in"], wintypes.HWND, "hwnd")),
        ]

    class ITaskbarList2(ITaskbarList):
        _iid_ = GUID("{602D4995-B13A-429B-A66E-1935E44F4317}")
        _methods_ = [
            COMMETHOD([], HRESULT, "MarkFullscreenWindow",
                      (["in"], wintypes.HWND, "hwnd"),
                      (["in"], wintypes.BOOL, "fFullscreen")),
        ]

    class ITaskbarList3(ITaskbarList2):
        _iid_ = GUID("{EA1AFB91-9E28-4B86-90E9-9E9F8A5EEFAF}")
        _methods_ = [
            COMMETHOD([], HRESULT, "SetProgressValue",
                      (["in"], wintypes.HWND, "hwnd"),
                      (["in"], ctypes.c_ulonglong, "completed"),
                      (["in"], ctypes.c_ulonglong, "total")),
            COMMETHOD([], HRESULT, "SetProgressState",
                      (["in"], wintypes.HWND, "hwnd"),
                      (["in"], ctypes.c_int, "tbpFlags")),
            COMMETHOD([], HRESULT, "RegisterTab",
                      (["in"], wintypes.HWND, "hwndTab"),
                      (["in"], wintypes.HWND, "hwndMDI")),
            COMMETHOD([], HRESULT, "UnregisterTab",
                      (["in"], wintypes.HWND, "hwndTab")),
            COMMETHOD([], HRESULT, "SetTabOrder",
                      (["in"], wintypes.HWND, "hwndTab"),
                      (["in"], wintypes.HWND, "hwndInsertBefore")),
            COMMETHOD([], HRESULT, "SetTabActive",
                      (["in"], wintypes.HWND, "hwndTab"),
                      (["in"], wintypes.HWND, "hwndMDI"),
                      (["in"], wintypes.DWORD, "dwReserved")),
            COMMETHOD([], HRESULT, "ThumbBarAddButtons",
                      (["in"], wintypes.HWND, "hwnd"),
                      (["in"], wintypes.UINT, "cButtons"),
                      (["in"], ctypes.POINTER(THUMBBUTTON), "pButton")),
            COMMETHOD([], HRESULT, "ThumbBarUpdateButtons",
                      (["in"], wintypes.HWND, "hwnd"),
                      (["in"], wintypes.UINT, "cButtons"),
                      (["in"], ctypes.POINTER(THUMBBUTTON), "pButton")),
            COMMETHOD([], HRESULT, "ThumbBarSetImageList",
                      (["in"], wintypes.HWND, "hwnd"),
                      (["in"], ctypes.c_void_p, "himl")),
            COMMETHOD([], HRESULT, "SetOverlayIcon",
                      (["in"], wintypes.HWND, "hwnd"),
                      (["in"], wintypes.HICON, "hIcon"),
                      (["in"], wintypes.LPCWSTR, "pszDescription")),
            COMMETHOD([], HRESULT, "SetThumbnailTooltip",
                      (["in"], wintypes.HWND, "hwnd"),
                      (["in"], wintypes.LPCWSTR, "pszTip")),
            COMMETHOD([], HRESULT, "SetThumbnailClip",
                      (["in"], wintypes.HWND, "hwnd"),
                      (["in"], ctypes.c_void_p, "prcClip")),
        ]

    return ITaskbarList3


def _load_icon(name: str):
    path = resource_path(os.path.join("assets", name))
    if not os.path.exists(path):
        return None
    IMAGE_ICON, LR_LOADFROMFILE, LR_DEFAULTSIZE = 1, 0x10, 0x40
    handle = ctypes.windll.user32.LoadImageW(
        None, path, IMAGE_ICON, 0, 0, LR_LOADFROMFILE | LR_DEFAULTSIZE)
    return handle or None


class TaskbarMiniPlayer(QObject):
    """Muss nach Empfang der "TaskbarButtonCreated"-Fenster-Nachricht mit
    init_buttons() aktiviert werden (macht MainWindow.nativeEvent)."""

    previous_clicked = Signal()
    play_pause_clicked = Signal()
    next_clicked = Signal()

    def __init__(self, hwnd: int, parent=None):
        super().__init__(parent)
        self.available = False
        self.taskbar_created_msg = 0
        self._hwnd = hwnd
        self._buttons_added = False
        self._playing = False
        try:
            import comtypes
            self._taskbar = comtypes.CoCreateInstance(
                comtypes.GUID("{56FDF344-FD6D-11D0-958A-006097C9A090}"),
                interface=_interfaces())
            self._taskbar.HrInit()
            self.taskbar_created_msg = \
                ctypes.windll.user32.RegisterWindowMessageW("TaskbarButtonCreated")
            self._icons = {
                "prev": _load_icon("tb_prev.ico"),
                "play": _load_icon("tb_play.ico"),
                "pause": _load_icon("tb_pause.ico"),
                "next": _load_icon("tb_next.ico"),
            }
            self.available = all(self._icons.values())
        except Exception:
            self._taskbar = None

    # ------------------------------------------------------------------
    def _button_array(self):
        from .i18n import tr
        arr = (THUMBBUTTON * 3)()
        specs = [
            (BTN_PREV, self._icons["prev"], tr("prev_track_tip")),
            (BTN_PLAYPAUSE,
             self._icons["pause" if self._playing else "play"],
             tr("pause") if self._playing else tr("play")),
            (BTN_NEXT, self._icons["next"], tr("next_track_tip")),
        ]
        for i, (bid, hicon, tip) in enumerate(specs):
            arr[i].dwMask = _THB_ICON | _THB_TOOLTIP | _THB_FLAGS
            arr[i].iId = bid
            arr[i].hIcon = hicon
            arr[i].szTip = tip
            arr[i].dwFlags = _THBF_ENABLED
        return arr

    def init_buttons(self):
        if not self.available:
            return
        try:
            arr = self._button_array()
            if self._buttons_added:
                self._taskbar.ThumbBarUpdateButtons(self._hwnd, 3, arr)
            else:
                self._taskbar.ThumbBarAddButtons(self._hwnd, 3, arr)
                self._buttons_added = True
        except Exception:
            pass

    def set_playing(self, playing: bool):
        if playing == self._playing:
            return
        self._playing = playing
        if self._buttons_added:
            try:
                self._taskbar.ThumbBarUpdateButtons(self._hwnd, 3,
                                                    self._button_array())
            except Exception:
                pass

    def set_progress(self, fraction: float | None, indeterminate: bool = False):
        """Fortschritt auf dem Taskleisten-Icon (None = ausblenden)."""
        if not self.available:
            return
        try:
            if indeterminate:
                self._taskbar.SetProgressState(self._hwnd, TBPF_INDETERMINATE)
            elif fraction is None:
                self._taskbar.SetProgressState(self._hwnd, TBPF_NOPROGRESS)
            else:
                self._taskbar.SetProgressState(self._hwnd, TBPF_NORMAL)
                self._taskbar.SetProgressValue(
                    self._hwnd, int(max(0.0, min(1.0, fraction)) * 1000), 1000)
        except Exception:
            pass

    # ------------------------------------------------------------------
    def handle_native_message(self, msg) -> bool:
        """Aus MainWindow.nativeEvent aufrufen. True = Nachricht verarbeitet."""
        if msg.message == self.taskbar_created_msg and self.taskbar_created_msg:
            self._buttons_added = False
            self.init_buttons()
            return False
        if msg.message == WM_COMMAND:
            if (msg.wParam >> 16) & 0xFFFF == THBN_CLICKED:
                bid = msg.wParam & 0xFFFF
                if bid == BTN_PREV:
                    self.previous_clicked.emit()
                elif bid == BTN_PLAYPAUSE:
                    self.play_pause_clicked.emit()
                elif bid == BTN_NEXT:
                    self.next_clicked.emit()
                return True
        return False


def apply_window_chrome(widget):
    """Dunkle Titelleiste + runde Ecken (Windows 10 1809+ / Windows 11)."""
    try:
        hwnd = int(widget.winId())
        dwm = ctypes.windll.dwmapi
        for attr, value in ((20, 1), (33, 2)):  # ImmersiveDarkMode, RoundedCorners
            v = ctypes.c_int(value)
            dwm.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(v),
                                      ctypes.sizeof(v))
    except Exception:
        pass
