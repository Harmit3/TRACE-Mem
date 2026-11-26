@echo off
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  echo Install Python 3.14 from python.org with the Windows launcher enabled.
  pause
  exit /b 1
)
py -3.14 -B -m trace_mem.workspace --open-browser %*
if errorlevel 1 pause
