"""BackupTool – entry point.

Usage:
    python main.py install    Install and configure the Windows service
    python main.py uninstall  Remove the Windows service
    python main.py start      Start the service
    python main.py stop       Stop the service
    python main.py debug      Run SyncEngine in foreground (no service needed)
    python main.py tray       Launch the system-tray app
"""
from __future__ import annotations

import sys


def cmd_install() -> None:
    import os
    import getpass
    import win32serviceutil
    import win32service

    from config import PROGRAMDATA_DIR, save_config, load_config, CONFIG_PATH
    from service import BackupToolService

    # Create runtime directory
    PROGRAMDATA_DIR.mkdir(parents=True, exist_ok=True)

    # Write default config if absent
    if not CONFIG_PATH.exists():
        save_config(load_config())
        print(f"Default config written to {CONFIG_PATH}")

    # Ask for service account
    print("\nService account setup")
    print("  Leave blank to use LocalSystem (may not access UNC paths)")
    username = input("  Service account username (domain\\user): ").strip() or None
    password = None
    if username:
        password = getpass.getpass("  Password: ")

    # Install service
    try:
        win32serviceutil.InstallService(
            pythonClassString=f"{BackupToolService.__module__}.{BackupToolService.__name__}",
            serviceName=BackupToolService._svc_name_,
            displayName=BackupToolService._svc_display_name_,
            description=BackupToolService._svc_description_,
            startType=win32service.SERVICE_AUTO_START,
            userName=username,
            password=password,
        )
        print("Service installed successfully.")
    except Exception as e:
        print(f"Service install failed: {e}")
        return

    # Write project directory into PythonPath so pythonservice.exe can find modules
    _write_python_path()

    # Registry autostart for tray app
    _write_autostart()
    print("Tray app autostart registered.")


def _write_python_path() -> None:
    from win32.lib import regutil
    from pathlib import Path as _Path
    project_dir = str(_Path(__file__).resolve().parent)
    try:
        regutil.RegisterNamedPath("BackupTool", project_dir)
        print(f"PythonPath registered: {project_dir}")
    except Exception as e:
        print(f"Warning: could not register PythonPath: {e}")


def _write_autostart() -> None:
    import winreg
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    exe = sys.executable
    script = str(__file__)
    value = f'"{exe}" "{script}" tray'
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as k:
            winreg.SetValueEx(k, "BackupTool", 0, winreg.REG_SZ, value)
    except Exception as e:
        print(f"Warning: could not write autostart registry key: {e}")


def cmd_uninstall() -> None:
    import win32serviceutil
    import winreg

    from service import BackupToolService

    try:
        win32serviceutil.RemoveService(BackupToolService._svc_name_)
        print("Service removed.")
    except Exception as e:
        print(f"Could not remove service: {e}")

    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as k:
            winreg.DeleteValue(k, "BackupTool")
        print("Autostart entry removed.")
    except FileNotFoundError:
        pass
    except Exception as e:
        print(f"Warning: could not remove autostart entry: {e}")


def cmd_start() -> None:
    from ipc import start_service
    try:
        start_service()
        print("Service started.")
    except Exception as e:
        print(f"Failed to start service: {e}")


def cmd_stop() -> None:
    from ipc import stop_service
    try:
        stop_service()
        print("Service stopped.")
    except Exception as e:
        print(f"Failed to stop service: {e}")


def cmd_debug() -> None:
    import logging
    import signal

    from config import load_config
    from logger import setup_logger
    from sync_engine import SyncEngine

    config = load_config()
    logger = setup_logger("backuptool", config)

    # Also log to stdout at DEBUG level in debug mode
    logging.getLogger().setLevel(logging.DEBUG)

    engine = SyncEngine(config)
    engine.start()
    print("SyncEngine running in debug mode. Press Ctrl+C to stop.")

    def _stop(sig, frame):
        print("\nStopping…")
        engine.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    import time
    while True:
        time.sleep(1)


def cmd_tray() -> None:
    from logger import setup_logger
    from config import load_config

    config = load_config()
    setup_logger("backuptool.tray", config)

    from tray_app import TrayApp
    TrayApp().run()


def cmd_headless() -> None:
    """Run SyncEngine without GUI (headless mode for servers)."""
    import logging
    import signal
    import time

    from config import load_config, CONFIG_PATH
    from logger import setup_logger
    from sync_engine import SyncEngine

    config = load_config()
    setup_logger("backuptool.headless", config)

    log = logging.getLogger("backuptool.headless")
    log.info("Starting BackupTool in headless mode")
    print("BackupTool running in headless mode. Press Ctrl+C to stop.")

    engine = SyncEngine(config)
    engine.start()

    stop_requested = False

    def _stop(sig, frame):
        nonlocal stop_requested
        print("\nStopping...")
        stop_requested = True

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    last_mtime = 0.0
    try:
        last_mtime = CONFIG_PATH.stat().st_mtime
    except OSError:
        pass

    while not stop_requested:
        time.sleep(5)
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


def cmd_service() -> None:
    """Called by the Windows service manager."""
    from service import run_service
    run_service()


_COMMANDS = {
    "install": cmd_install,
    "uninstall": cmd_uninstall,
    "start": cmd_start,
    "stop": cmd_stop,
    "debug": cmd_debug,
    "tray": cmd_tray,
    "headless": cmd_headless,
    "service": cmd_service,
}

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1].lower()
    if cmd not in _COMMANDS:
        print(f"Unknown command: {cmd}")
        print(f"Available: {', '.join(_COMMANDS)}")
        sys.exit(1)

    _COMMANDS[cmd]()
