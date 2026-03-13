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

from config import PROGRAMDATA_DIR
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

    def run(self) -> None:
        self._poll_thread.start()
        self._icon.run()

    def _build_menu(self) -> pystray.Menu:
        return pystray.Menu(
            pystray.MenuItem(
                "Install Service",
                lambda: _elevate_service("install"),
                visible=lambda item: get_service_state() == "not_installed",
            ),
            pystray.MenuItem(
                "Start Service",
                lambda: self._svc_action(start_service),
                visible=lambda item: get_service_state() != "not_installed",
            ),
            pystray.MenuItem(
                "Stop Service",
                lambda: self._svc_action(stop_service),
                visible=lambda item: get_service_state() != "not_installed",
            ),
            pystray.MenuItem(
                "Restart Service",
                lambda: self._svc_action(restart_service),
                visible=lambda item: get_service_state() != "not_installed",
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Settings…", self._open_settings),
            pystray.MenuItem("Open Log", self._open_log),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", self._quit),
        )

    def _svc_action(self, fn) -> None:
        try:
            fn()
        except Exception as e:
            log.error("Service action failed: %s", e)

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
        self._icon.stop()

    def _poll_loop(self) -> None:
        while not self._stop_event.is_set():
            self._stop_event.wait(timeout=5)
            try:
                self._update_icon()
            except Exception:
                log.exception("Error in tray poll loop")

    def _update_icon(self) -> None:
        icon_running, icon_stopped, icon_error = _get_icons()
        state = get_service_state()
        status = read_status()

        errors = status.get("errors", [])

        if errors:
            img = icon_error
            tooltip = f"BackupTool – ERROR ({len(errors)} error(s))"
        elif state == "running":
            img = icon_running
            tooltip = "BackupTool – Running"
        else:
            img = icon_stopped
            tooltip = f"BackupTool – {state.replace('_', ' ').title()}"

        self._icon.icon = img
        self._icon.title = tooltip
