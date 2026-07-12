@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ============================================
echo  Lyrix - Build-Skript
echo ============================================

rem Passende Python-Version suchen (torch/pyannote brauchen 3.11-3.13)
set "PYCMD="
for %%V in (3.13 3.12 3.11) do (
    if not defined PYCMD (
        py -%%V -c "print()" >nul 2>&1 && set "PYCMD=py -%%V"
    )
)
if not defined PYCMD (
    echo FEHLER: Kein Python 3.11/3.12/3.13 gefunden.
    echo Bitte von https://python.org installieren.
    exit /b 1
)
echo Verwende Python: %PYCMD%

if not exist .venv (
    echo Erstelle virtuelle Umgebung...
    %PYCMD% -m venv .venv || exit /b 1
)
call .venv\Scripts\activate.bat

echo Installiere Abhaengigkeiten (das dauert beim ersten Mal, mehrere GB)...
python -m pip install --upgrade pip wheel >nul
pip install -r requirements.txt || exit /b 1
pip install "pyinstaller>=6.10" || exit /b 1

if not exist assets\tb_play.ico (
    echo Erzeuge Programm-Icons...
    python tools\make_icon.py || exit /b 1
)

if not exist models\cnn14_16k.pt (
    echo FEHLER: models\-Ordner unvollstaendig. Benoetigt werden:
    echo   segmentation-3.0.bin, wespeaker-voxceleb-resnet34-LM.bin,
    echo   cnn14_16k.pt, audioset_labels.csv  (siehe README)
    exit /b 1
)

echo Baue EXE mit PyInstaller...
pyinstaller --noconfirm lyrix.spec || exit /b 1

echo Erzeuge Installer-Komponenten und KI-Paket...
python tools\gen_components.py || exit /b 1

echo.
echo Build fertig: dist\Lyrix\Lyrix.exe
echo.

rem Installer bauen, wenn Inno Setup vorhanden ist
set "ISCC="
where iscc >nul 2>&1 && set "ISCC=iscc"
if not defined ISCC if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not defined ISCC if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not defined ISCC if exist "%LocalAppData%\Programs\Inno Setup 6\ISCC.exe" set "ISCC=%LocalAppData%\Programs\Inno Setup 6\ISCC.exe"

if defined ISCC (
    echo Baue Installer mit Inno Setup...
    "%ISCC%" installer.iss || exit /b 1
    echo Installer liegt in: installer_out\
) else (
    echo Inno Setup nicht gefunden - Installer uebersprungen.
    echo Installation: winget install JRSoftware.InnoSetup
    echo Danach build.bat erneut ausfuehren.
)

echo Fertig.
endlocal
