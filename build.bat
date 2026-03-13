@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"

echo.
echo ============================================================
echo   BackupTool Build Script
echo ============================================================
echo.

:: ── Check venv ───────────────────────────────────────────────────────────────
if not exist ".venv\Scripts\python.exe" (
    echo ERROR: .venv not found.
    echo Run:  python -m venv .venv  ^&^&  .venv\Scripts\pip install -r requirements.txt
    pause & exit /b 1
)
set PYTHON=.venv\Scripts\python.exe
set PIP=.venv\Scripts\pip.exe

:: ── Install / update PyInstaller ─────────────────────────────────────────────
echo [1/4] Installing PyInstaller...
%PIP% install --quiet --upgrade pyinstaller pyinstaller-hooks-contrib
if errorlevel 1 ( echo FAILED & pause & exit /b 1 )
echo       OK

:: ── Run PyInstaller ───────────────────────────────────────────────────────────
echo.
echo [2/4] Building executables with PyInstaller...
%PYTHON% -m PyInstaller BackupTool.spec --noconfirm --clean
if errorlevel 1 ( echo FAILED & pause & exit /b 1 )
echo       OK  ^(dist\BackupTool\^)

:: ── Copy Python DLLs next to .exe (fixes "fail to load Python DLL") ──────────
echo.
echo [2b] Copying Python DLLs next to executables...
for %%f in (.venv\Scripts\python3*.dll) do (
    copy /Y "%%f" "dist\BackupTool\" >nul
    echo       Copied: %%~nxf
)

:: ── Check for Inno Setup ─────────────────────────────────────────────────────
echo.
echo [3/4] Looking for Inno Setup...
set ISCC=
for %%p in (
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
    "C:\Program Files\Inno Setup 6\ISCC.exe"
) do (
    if exist %%p set ISCC=%%~p
)

if "%ISCC%"=="" (
    echo       Inno Setup not found – skipping installer creation.
    echo       Install from: https://jrsoftware.org/isdl.php
    echo       Then re-run this script to build BackupToolSetup.exe
    goto :done
)
echo       Found: %ISCC%

:: ── Build installer .exe ──────────────────────────────────────────────────────
echo.
echo [4/5] Building installer with Inno Setup...
"%ISCC%" setup.iss
if errorlevel 1 ( echo FAILED & pause & exit /b 1 )
echo       OK

:done
echo.
echo ============================================================
echo   Build complete!
echo.
if exist "dist\BackupToolSetup.exe" (
    echo   Installer : dist\BackupToolSetup.exe
) else (
    echo   Executables: dist\BackupTool\
    echo   ^(Install Inno Setup and re-run to get BackupToolSetup.exe^)
)
echo ============================================================
echo.
pause
