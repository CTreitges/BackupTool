from __future__ import annotations

import ctypes
import logging
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import pystray
from PIL import Image, ImageDraw

from config import PROGRAMDATA_DIR, load_config
from ipc import read_status, get_service_state, start_service, stop_service, restart_service
from logger import LOG_PATH

log = logging.getLogger(__name__)

ASSETS_DIR = Path(__file__).parent / "assets"


def _service_exe() -> Path:
    """Return path to BackupToolService.exe next to the running executable."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent / "BackupToolService.exe"
    return Path(__file__).parent / "service_entry.py"


def _elevate_service(action: str) -> None:
    """Run BackupToolService.exe <action> with UAC elevation."""
    svc = _service_exe()
    if not svc.exists():
        log.error("Service executable not found: %s", svc)
        return
    if getattr(sys, "frozen", False):
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", str(svc), action, None, 1
        )
    else:
        # Dev mode: use Python to run service_entry.py
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable,
            f'"{svc}" {action}', None, 1
        )


def _make_circle_icon(color: tuple[int, int, int]) -> Image.Image:
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    margin = 4
    draw.ellipse([margin, margin, size - margin, size - margin], fill=color)
    return img


def _load_icon(name: str, fallback_color: tuple[int, int, int]) -> Image.Image:
    path = ASSETS_DIR / name
    if path.exists():
        return Image.open(path).convert("RGBA")
    return _make_circle_icon(fallback_color)


_ICON_RUNNING = None
_ICON_STOPPED = None
_ICON_ERROR = None


def _get_icons() -> tuple[Image.Image, Image.Image, Image.Image]:
    global _ICON_RUNNING, _ICON_STOPPED, _ICON_ERROR
    if _ICON_RUNNING is None:
        _ICON_RUNNING = _load_icon("icon_active.png", (0, 180, 0))
        _ICON_STOPPED = _load_icon("icon_paused.png", (120, 120, 120))
        _ICON_ERROR = _load_icon("icon_error.png", (200, 0, 0))
    return _ICON_RUNNING, _ICON_STOPPED, _ICON_ERROR


class TrayApp:
    def __init__(self) -> None:
        icon_running, _, _ = _get_icons()
        self._icon = pystray.Icon(
            "BackupTool",
            icon_running,
            "BackupTool",
            menu=self._build_menu(),
        )
        self._stop_event = threading.Event()
        self._poll_thread = threading.Thread(target=self._poll_loop, daemon=True, name="tray-poll")
        self._engine = None
        self._engine_lock = threading.Lock()
        self._last_config_mtime = 0.0

    def run(self) -> None:
        # Auto-start embedded engine (runs under current user, has access to all drives)
        self._start_embedded_engine()
        self._poll_thread.start()
        self._icon.run()

    def _start_embedded_engine(self) -> None:
        with self._engine_lock:
            if self._engine is not None:
                return
            try:
                from config import CONFIG_PATH
                from sync_engine import SyncEngine
                config = load_config()
                self._engine = SyncEngine(config)
                self._engine.start()
                try:
                    self._last_config_mtime = CONFIG_PATH.stat().st_mtime
                except OSError:
                    pass
                log.info("Embedded SyncEngine started")
            except Exception:
                log.exception("Failed to start embedded SyncEngine")

    def _stop_embedded_engine(self) -> None:
        with self._engine_lock:
            if self._engine is None:
                return
            try:
                self._engine.stop()
                log.info("Embedded SyncEngine stopped")
            except Exception:
                log.exception("Failed to stop embedded SyncEngine")
            self._engine = None

    def _restart_embedded_engine(self) -> None:
        self._stop_embedded_engine()
        self._start_embedded_engine()

    def _is_engine_running(self) -> bool:
        with self._engine_lock:
            return self._engine is not None

    def _build_menu(self) -> pystray.Menu:
        return pystray.Menu(
            pystray.MenuItem(
                "Sync Running",
                None,
                enabled=False,
                visible=lambda item: self._is_engine_running(),
            ),
            pystray.MenuItem(
                "Start Sync",
                lambda: self._start_embedded_engine(),
                visible=lambda item: not self._is_engine_running(),
            ),
            pystray.MenuItem(
                "Stop Sync",
                lambda: self._stop_embedded_engine(),
                visible=lambda item: self._is_engine_running(),
            ),
            pystray.MenuItem(
                "Restart Sync",
                lambda: self._restart_embedded_engine(),
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Settings...", self._open_settings),
            pystray.MenuItem("Open Log", self._open_log),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", self._quit),
        )

    def _open_settings(self) -> None:
        from settings_gui import SettingsWindow
        t = threading.Thread(target=SettingsWindow().run, daemon=True, name="settings-gui")
        t.start()

    def _open_log(self) -> None:
        try:
            os.startfile(str(LOG_PATH))
        except Exception as e:
            log.error("Cannot open log: %s", e)

    def _quit(self) -> None:
        self._stop_event.set()
        self._stop_embedded_engine()
        self._icon.stop()

    def _poll_loop(self) -> None:
        while not self._stop_event.is_set():
            self._stop_event.wait(timeout=5)
            try:
                self._update_icon()
                self._check_config_reload()
            except Exception:
                log.exception("Error in tray poll loop")

    def _check_config_reload(self) -> None:
        """Reload config only if the file actually changed."""
        from config import CONFIG_PATH
        try:
            mtime = CONFIG_PATH.stat().st_mtime
        except OSError:
            return
        if mtime == self._last_config_mtime:
            return
        self._last_config_mtime = mtime
        with self._engine_lock:
            if self._engine is None:
                return
            try:
                new_config = load_config()
                self._engine.reload_config(new_config)
            except Exception:
                pass

    def _update_icon(self) -> None:
        icon_running, icon_stopped, icon_error = _get_icons()
        status = read_status()

        errors = status.get("errors", [])
        engine_running = self._is_engine_running()

        if errors:
            img = icon_error
            tooltip = f"BackupTool – ERROR ({len(errors)} error(s))"
        elif engine_running:
            img = icon_running
            tooltip = "BackupTool – Running"
        else:
            img = icon_stopped
            tooltip = "BackupTool – Stopped"

        self._icon.icon = img
        self._icon.title = tooltip
