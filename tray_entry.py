"""PyInstaller entry point for BackupToolTray.exe"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

def _crash_log(exc: BaseException) -> None:
    log_path = Path(sys.executable).parent / "crash.log"
    try:
        with open(log_path, "w", encoding="utf-8") as f:
            traceback.print_exc(file=f)
    except Exception:
        pass
    # Also show a message box so the user sees the error
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(
            0,
            f"BackupTool crash:\n\n{traceback.format_exc()}",
            "BackupTool – Error",
            0x10,  # MB_ICONERROR
        )
    except Exception:
        pass

if __name__ == "__main__":
    try:
        from config import load_config
        from logger import setup_logger
        from tray_app import TrayApp

        config = load_config()
        setup_logger("backuptool.tray", config)
        TrayApp().run()
    except Exception as exc:
        _crash_log(exc)
        sys.exit(1)
