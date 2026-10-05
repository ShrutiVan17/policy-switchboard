@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -m switchboard.launch
) else (
  python -m switchboard.launch
)
pause
