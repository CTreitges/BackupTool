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
        if "--headless" in sys.argv:
            # Headless mode: run SyncEngine without GUI (for servers)
            from config import load_config, CONFIG_PATH
            from logger import setup_logger
            from sync_engine import SyncEngine
            import signal
            import time

            config = load_config()
            setup_logger("backuptool.headless", config)

            import logging
            log = logging.getLogger("backuptool.headless")
            log.info("Starting BackupTool in headless mode")

            engine = SyncEngine(config)
            engine.start()

            import threading
            stop_event = threading.Event()

            def _stop(sig, frame):
                stop_event.set()

            signal.signal(signal.SIGINT, _stop)
            signal.signal(signal.SIGTERM, _stop)

            last_mtime = 0.0
            try:
                last_mtime = CONFIG_PATH.stat().st_mtime
            except OSError:
                pass

            while not stop_event.is_set():
                time.sleep(5)
                # Check for config changes
                try:
                    mtime = CONFIG_PATH.stat().st_mtime
                    if mtime != last_mtime:
                        last_mtime = mtime
                        new_config = load_config()
                        engine.reload_config(new_config)
                        log.info("Config reloaded")
                except OSError:
                    pass

            engine.stop()
            log.info("Headless mode stopped")
        else:
            from config import load_config
            from logger import setup_logger
            from tray_app import TrayApp

            config = load_config()
            setup_logger("backuptool.tray", config)
            TrayApp().run()
    except Exception as exc:
        _crash_log(exc)
        sys.exit(1)
