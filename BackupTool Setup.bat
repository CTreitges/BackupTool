@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo ERROR: .venv not found. Please run: python -m venv .venv
    pause
    exit /b 1
)
.venv\Scripts\python.exe installer_gui.py
