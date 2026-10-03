@echo off
cd /d "%~dp0"
if exist "apps.exe" (
  start "" "apps.exe"
  exit /b 0
)
call "%~dp0OSM-TPF2-Studio.bat"
