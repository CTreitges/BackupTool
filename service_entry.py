"""
PyInstaller entry point for BackupToolService.exe
"""
from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path

# Write to a log file immediately – before any other imports
_LOG = Path(os.environ.get("PROGRAMDATA", "C:/ProgramData")) / "BackupTool" / "service_boot.log"


def _boot_log(msg: str) -> None:
    try:
        _LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(_LOG, "a", encoding="utf-8") as f:
            import datetime
            f.write(f"[{datetime.datetime.now().isoformat()}] {msg}\n")
    except Exception:
        pass


_boot_log(f"service_entry started  argv={sys.argv}  frozen={getattr(sys, 'frozen', False)}")

try:
    import servicemanager
    import win32serviceutil
    _boot_log("pywin32 imports OK")
except Exception as e:
    _boot_log(f"pywin32 import FAILED: {e}\n{traceback.format_exc()}")
    sys.exit(1)

try:
    from service import BackupToolService
    _boot_log("service.BackupToolService import OK")
except Exception as e:
    _boot_log(f"service import FAILED: {e}\n{traceback.format_exc()}")
    sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) == 1:
        # Called by Windows SCM – start the service dispatcher
        try:
            _boot_log("Starting SCM dispatcher")
            servicemanager.Initialize()
            servicemanager.PrepareToHostSingle(BackupToolService)
            servicemanager.StartServiceCtrlDispatcher()
            _boot_log("Dispatcher exited normally")
        except Exception as e:
            _boot_log(f"Dispatcher FAILED: {e}\n{traceback.format_exc()}")
            sys.exit(1)
    else:
        # Called manually: install / remove / start / stop
        # Default to auto-start when installing
        if sys.argv[1].lower() == "install" and "--startup" not in " ".join(sys.argv):
            sys.argv.insert(2, "--startup")
            sys.argv.insert(3, "auto")
        try:
            _boot_log(f"HandleCommandLine: {sys.argv[1:]}")
            win32serviceutil.HandleCommandLine(BackupToolService)
            _boot_log("HandleCommandLine done")
        except Exception as e:
            _boot_log(f"HandleCommandLine FAILED: {e}\n{traceback.format_exc()}")
            sys.exit(1)
