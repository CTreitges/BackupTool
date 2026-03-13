# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec -- builds:
  dist/BackupTool/BackupToolTray.exe   (system tray app with embedded sync engine)
"""

import sys
import glob
from pathlib import Path

ROOT = Path(SPECPATH)  # noqa: F821  (PyInstaller provides SPECPATH)

# ── Bundle python3xx.dll next to the exe (fixes "fail to load Python DLL") ───
_scripts_dir = Path(sys.executable).parent
_python_dlls = glob.glob(str(_scripts_dir / "python3*.dll"))
PYTHON_DLLS = [(dll, ".") for dll in _python_dlls]

# ── Hidden imports needed by pywin32 / pystray / watchdog ────────────────────
HIDDEN = [
    "win32timezone",
    "win32api",
    "win32con",
    "win32event",
    "pywintypes",
    "winerror",
    "pystray._win32",
    "PIL._tkinter_finder",
    "watchdog.observers.winapi",
    "watchdog.observers.read_directory_changes",
]

# ── Common data files ─────────────────────────────────────────────────────────
DATAS = [
    (str(ROOT / "assets"), "assets"),
]

# ── Analysis: Tray (includes embedded sync engine) ──────────────────────────
a_tray = Analysis(  # noqa: F821
    [str(ROOT / "tray_entry.py")],
    pathex=[str(ROOT)],
    binaries=PYTHON_DLLS,
    datas=DATAS,
    hiddenimports=HIDDEN,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["unittest"],
    noarchive=False,
)

pyz_tray = PYZ(a_tray.pure)  # noqa: F821

exe_tray = EXE(  # noqa: F821
    pyz_tray,
    a_tray.scripts,
    [],
    exclude_binaries=True,
    name="BackupToolTray",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=str(ROOT / "assets" / "icon_active.ico") if (ROOT / "assets" / "icon_active.ico").exists() else None,
)

# ── Collect into one folder ─────────────────────────────────────────────────
coll = COLLECT(  # noqa: F821
    exe_tray,
    a_tray.binaries,
    a_tray.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="BackupTool",
    contents_directory=".",   # flat layout - all DLLs next to the .exe
)
