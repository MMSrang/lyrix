"""Dunkles Farbschema und globales Stylesheet (Spotify-inspiriert).

Wichtig: Normale QWidgets sind transparent, damit der Cover-Art-Hintergrund
(BackdropWidget) durchscheint. Panels, die deckend sein sollen, bekommen
explizite (teiltransparente) Hintergründe.

build_qss() (nach QApplication-Erzeugung aufrufen!) liefert das fertige
Stylesheet: Es rendert das Chevron für QComboBox::down-arrow als kleines
PNG – QSS kann keine Vektorpfeile zeichnen, und der CSS-Dreieck-Trick über
Border-Kanten wird von Qt als Kasten gerendert (sah aus wie ein Strich).
"""

import os
import tempfile

ACCENT = "#1DB954"
BG = "#121212"
BG_ELEVATED = "#181818"


def _combo_arrow_rule() -> str:
    """QSS-Regelinhalt für den Combo-Pfeil (PNG einmalig erzeugen)."""
    path = os.path.join(tempfile.gettempdir(), "lyrix_combo_arrow.png")
    try:
        if not os.path.exists(path):
            from . import icons
            icons.chevron_down("#b3b3b3", 12).pixmap(12, 12).save(path, "PNG")
        return f'image: url("{path.replace(chr(92), "/")}"); ' \
               f"width: 12px; height: 12px; margin-right: 10px;"
    except Exception:
        return "image: none;"


def build_qss() -> str:
    return GLOBAL_QSS.replace("/*@COMBO_ARROW@*/", _combo_arrow_rule())

GLOBAL_QSS = f"""
* {{ font-family: "Segoe UI", sans-serif; outline: none; }}

QMainWindow {{ background: {BG}; }}
QDialog {{ background: {BG_ELEVATED}; }}
QWidget {{ background: transparent; color: #eaeaea; }}

QLabel {{ background: transparent; }}

QPushButton {{
    background: transparent; border: none; border-radius: 8px;
    padding: 8px 14px; color: #eaeaea; font-size: 14px; font-weight: 600;
}}
QPushButton:hover {{ background: rgba(255,255,255,18); }}
QPushButton:pressed {{ background: rgba(255,255,255,30); }}
QPushButton:disabled {{ color: #5c5c5c; }}

QPushButton#playButton {{
    min-width: 48px; min-height: 48px; max-width: 48px; max-height: 48px;
    border-radius: 24px; background: #ffffff; padding: 0;
}}
QPushButton#playButton:hover {{ background: {ACCENT}; }}
QPushButton#playButton:disabled {{ background: #3a3a3a; }}

QPushButton[iconBtn="true"] {{
    min-width: 36px; min-height: 36px; max-width: 36px; max-height: 36px;
    border-radius: 18px; padding: 0;
}}
QPushButton[iconBtn="true"]:hover {{ background: rgba(255,255,255,34); }}
QPushButton[iconBtn="true"]:pressed {{ background: rgba(255,255,255,52); }}
QPushButton[iconBtn="true"]:disabled {{ background: transparent; }}

QSlider {{ background: transparent; min-height: 20px; }}
QSlider::groove:horizontal {{
    height: 4px; background: rgba(255,255,255,55); border-radius: 2px;
}}
QSlider::sub-page:horizontal {{ background: {ACCENT}; border-radius: 2px; }}
QSlider::handle:horizontal {{
    width: 12px; height: 12px; margin: -4px 0;
    border-radius: 6px; background: #ffffff;
}}

QCheckBox {{ spacing: 8px; font-size: 13px; font-weight: 600; color: #c9c9c9;
             background: transparent; }}
QCheckBox::indicator {{
    width: 38px; height: 20px; border-radius: 10px; background: #4a4a4a;
}}
QCheckBox::indicator:checked {{ background: {ACCENT}; }}
QCheckBox::indicator:disabled {{ background: #2a2a2a; }}

QGroupBox {{
    border: 1px solid #2e2e2e; border-radius: 10px;
    background: rgba(255,255,255,7);
    margin-top: 14px; padding-top: 10px;
    font-size: 12px; font-weight: 700; color: #9f9f9f;
}}
QGroupBox::title {{
    subcontrol-origin: margin; subcontrol-position: top left;
    left: 12px; top: 2px; padding: 0 5px; background: transparent;
}}

/* Einstellungsdialog: Card-Look wie die Panels des Hauptfensters */
QDialog#settingsDialog {{ background: #151515; }}
QFrame#settingsCard {{
    background: rgba(255,255,255,8);
    border: 1px solid #272727; border-radius: 12px;
}}
QLabel#cardTitle {{
    color: {ACCENT}; font-size: 11px; font-weight: 800;
    background: transparent;
}}
QLabel#cardHint {{ color: #8f8f8f; font-size: 12px; background: transparent; }}
QLabel[chip="ok"] {{
    background: rgba(29,185,84,38); color: #3ddc74;
    border-radius: 9px; padding: 2px 10px;
    font-size: 11px; font-weight: 700;
}}
QLabel[chip="warn"] {{
    background: rgba(227,179,65,34); color: #e3b341;
    border-radius: 9px; padding: 2px 10px;
    font-size: 11px; font-weight: 700;
}}
QDialogButtonBox QPushButton {{
    background: #2c2c2c; border-radius: 8px; padding: 7px 22px;
    font-size: 13px; min-width: 72px;
}}
QDialogButtonBox QPushButton:hover {{ background: #3a3a3a; }}
QPushButton#primaryButton {{ background: {ACCENT}; color: #000000; }}
QPushButton#primaryButton:hover {{ background: #24d95f; }}
QFrame#settingsCard QPushButton {{
    background: rgba(255,255,255,16); border-radius: 8px;
    padding: 6px 12px; font-size: 12px;
}}
QFrame#settingsCard QPushButton:hover {{ background: rgba(255,255,255,30); }}
QFrame#settingsCard QPushButton:disabled {{
    background: rgba(255,255,255,7); color: #5c5c5c;
}}

QScrollArea {{ border: none; background: transparent; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollBar:vertical {{
    width: 10px; background: transparent; margin: 0;
}}
QScrollBar::handle:vertical {{
    background: rgba(255,255,255,60); border-radius: 5px; min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{ background: rgba(255,255,255,95); }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}

QStatusBar {{ background: rgba(8,8,8,200); color: #8f8f8f; font-size: 12px; }}
QStatusBar::item {{ border: none; }}
QStatusBar QLabel {{ background: transparent; }}

QProgressBar {{
    background: rgba(255,255,255,28); border: none; border-radius: 2px;
    min-height: 4px; max-height: 4px; text-align: center; color: transparent;
}}
QProgressBar::chunk {{ background: {ACCENT}; border-radius: 2px; }}

QLineEdit, QComboBox {{
    background: #2a2a2a; border: 1px solid #3a3a3a; border-radius: 8px;
    padding: 7px 12px; color: #eeeeee; font-size: 13px;
    selection-background-color: {ACCENT}; selection-color: #000000;
}}
QLineEdit:hover, QComboBox:hover {{
    background: #303030; border-color: #4a4a4a;
}}
QLineEdit:focus, QComboBox:focus {{ border-color: {ACCENT}; }}
QComboBox::drop-down {{
    border: none; width: 30px;
    subcontrol-origin: padding; subcontrol-position: center right;
}}
QComboBox::down-arrow {{ /*@COMBO_ARROW@*/ }}
QComboBox QAbstractItemView {{
    background: #242424; color: #eeeeee; border: 1px solid #3a3a3a;
    border-radius: 8px; padding: 4px; outline: none;
    selection-background-color: {ACCENT}; selection-color: #000000;
}}
QComboBox QAbstractItemView::item {{
    padding: 6px 10px; border-radius: 5px; min-height: 20px;
}}

QMessageBox {{ background: {BG_ELEVATED}; }}
QMessageBox QLabel {{ background: transparent; }}
QToolTip {{
    background: #262626; color: #eaeaea; border: 1px solid #3a3a3a; padding: 4px;
}}

QWidget#footerPanel {{ background: rgba(10,10,10,170); }}
QWidget#headerPanel {{ background: rgba(10,10,10,110); }}
QLabel#trackTitle {{ font-size: 14px; font-weight: 700; color: #ffffff; }}
QLabel#trackStatus {{ font-size: 11px; color: #9f9f9f; }}
QLabel#timeLabel {{ font-size: 11px; color: #b3b3b3; }}
QLabel#loadingTitle {{ font-size: 18px; font-weight: 700; color: #eaeaea; }}
QLabel#loadingHint {{ font-size: 12px; color: #8f8f8f; }}
QLabel#placeholder {{ color: #7a7a7a; font-size: 16px; font-weight: 600; }}

QWidget#titleBar {{ background: rgba(8,8,8,150); }}
QLabel#titleBarText {{ font-size: 13px; font-weight: 600; color: #d9d9d9; }}
QPushButton#captionButton, QPushButton#captionCloseButton {{
    border: none; border-radius: 0; background: transparent; padding: 0;
    min-width: 46px; max-width: 46px;
}}
QPushButton#captionButton:hover,
QPushButton#captionButton[ncHover="true"] {{ background: rgba(255,255,255,40); }}
QPushButton#captionButton:pressed {{ background: rgba(255,255,255,58); }}
QPushButton#captionCloseButton:hover {{ background: #c42b1c; }}
QPushButton#captionCloseButton:pressed {{ background: #b02418; }}

QSlider#volumeSlider::groove:horizontal {{
    height: 3px; background: rgba(255,255,255,55); border-radius: 1px;
}}
QSlider#volumeSlider::sub-page:horizontal {{
    background: #d9d9d9; border-radius: 1px;
}}
QSlider#volumeSlider::handle:horizontal {{
    width: 10px; height: 10px; margin: -4px 0;
    border-radius: 5px; background: #ffffff;
}}
QSlider#volumeSlider::handle:horizontal:hover {{ background: {ACCENT}; }}

QLabel#miniTitle {{ font-size: 12px; font-weight: 700; color: #ffffff;
                    background: transparent; }}
QLabel#miniLine {{ font-size: 12px; color: #b9b9b9; background: transparent; }}
QPushButton#miniPlayButton {{
    border-radius: 18px; background: #ffffff; padding: 0;
}}
QPushButton#miniPlayButton:hover {{ background: {ACCENT}; }}

QToolButton#collapsibleHeader {{
    border: none; background: transparent; color: #b3b3b3;
    font-weight: 700; font-size: 12px; padding: 4px;
}}
QWidget#offsetPopup {{
    background: #202020; border: 1px solid #3a3a3a; border-radius: 10px;
}}
QLabel#offsetTitle {{ font-size: 12px; font-weight: 700; color: #b3b3b3; }}
QLabel#offsetValue {{ font-size: 13px; font-weight: 700; color: #ffffff; }}
QLabel#offsetHint {{ font-size: 11px; color: #8f8f8f; }}
QPushButton#offsetReset {{
    font-size: 12px; padding: 4px 10px; background: rgba(255,255,255,16);
}}
QPushButton#offsetReset:hover {{ background: rgba(255,255,255,30); }}
QPushButton#speedButton {{
    font-size: 12px; font-weight: 700; color: #c9c9c9; min-width: 46px;
    padding: 6px 8px;
}}
QPushButton#speedButton:hover {{ background: rgba(255,255,255,18); }}
QMenu {{
    background: #202020; color: #e6e6e6; border: 1px solid #3a3a3a;
    border-radius: 8px; padding: 4px;
}}
QMenu::item {{ padding: 6px 22px; border-radius: 5px; }}
QMenu::item:selected {{ background: rgba(255,255,255,26); }}
QMenu::separator {{ height: 1px; background: #3a3a3a; margin: 4px 8px; }}
"""
