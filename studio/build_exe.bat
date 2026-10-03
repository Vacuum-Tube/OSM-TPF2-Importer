@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Run OSM-TPF2-Studio.bat once first so the venv exists.
  pause
  exit /b 1
)
.venv\Scripts\python.exe -m pip install pyinstaller
.venv\Scripts\pyinstaller --noconfirm --windowed --name apps --distpath "%~dp0..\.." --add-data "ui;ui" main.py
echo.
echo If the build succeeded, apps.exe is in the OSM-TPF2-Importer-main folder.
echo Keep this whole folder together — the converter still lives in python\.
pause
