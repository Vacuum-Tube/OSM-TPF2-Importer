@echo off
setlocal
cd /d "%~dp0"

if not exist "studio\main.py" (
  echo OSM-TPF2 Studio files are missing.
  pause
  exit /b 1
)

where py >nul 2>&1
if %errorlevel%==0 (
  set PY=py -3
) else (
  set PY=python
)

if not exist "studio\.venv\Scripts\python.exe" (
  echo Creating virtual environment...
  %PY% -m venv studio\.venv
  if errorlevel 1 (
    echo Could not create a Python venv. Install Python 3.10+ from python.org and tick "Add to PATH".
    pause
    exit /b 1
  )
  echo Installing Studio packages...
  "studio\.venv\Scripts\python.exe" -m pip install --upgrade pip
  "studio\.venv\Scripts\python.exe" -m pip install -r "studio\requirements.txt"
  echo Installing converter packages (this can take a few minutes)...
  "studio\.venv\Scripts\python.exe" -m pip install -r "studio\requirements-converter.txt"
  if errorlevel 1 (
    echo Converter extras failed. The Studio window can still open.
  )
)

echo Starting OSM-TPF2 Studio...
"studio\.venv\Scripts\python.exe" "studio\main.py"
if errorlevel 1 pause
