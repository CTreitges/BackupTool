from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from config import PROGRAMDATA_DIR

STATUS_PATH = PROGRAMDATA_DIR / "status.json"
SERVICE_NAME = "BackupToolSvc"


# ------------------------------------------------------------------
# status.json helpers
# ------------------------------------------------------------------

def read_status() -> dict[str, Any]:
    if not STATUS_PATH.exists():
        return {}
    try:
        return json.loads(STATUS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def write_status(data: dict[str, Any]) -> None:
    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATUS_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, STATUS_PATH)


# ------------------------------------------------------------------
# Service control helpers (require pywin32 + admin rights)
# ------------------------------------------------------------------

def get_service_state() -> str:
    try:
        import win32serviceutil
        import pywintypes
        try:
            status = win32serviceutil.QueryServiceStatus(SERVICE_NAME)
            state_map = {
                1: "stopped",
                2: "start_pending",
                3: "stop_pending",
                4: "running",
                5: "continue_pending",
                6: "pause_pending",
                7: "paused",
            }
            return state_map.get(status[1], "unknown")
        except pywintypes.error:
            return "not_installed"
    except ImportError:
        return "unavailable"


def start_service() -> None:
    import win32serviceutil
    win32serviceutil.StartService(SERVICE_NAME)


def stop_service() -> None:
    import win32serviceutil
    win32serviceutil.StopService(SERVICE_NAME)


def restart_service() -> None:
    import win32serviceutil
    win32serviceutil.RestartService(SERVICE_NAME)
