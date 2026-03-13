from __future__ import annotations

import logging
import threading
import time

import win32serviceutil
import win32service
import win32event
import servicemanager

from config import load_config, PROGRAMDATA_DIR
from logger import setup_logger
from sync_engine import SyncEngine

SERVICE_NAME = "BackupToolSvc"
SERVICE_DISPLAY_NAME = "BackupTool Sync Service"
SERVICE_DESCRIPTION = "Synchronizes OneDrive folders to NAS with recycle bin support."


class BackupToolService(win32serviceutil.ServiceFramework):
    _svc_name_ = SERVICE_NAME
    _svc_display_name_ = SERVICE_DISPLAY_NAME
    _svc_description_ = SERVICE_DESCRIPTION

    def __init__(self, args):
        super().__init__(args)
        self._stop_event = win32event.CreateEvent(None, 0, 0, None)
        self._engine: SyncEngine | None = None
        self._config_observer = None

    def SvcDoRun(self) -> None:
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STARTED,
            (self._svc_name_, ""),
        )

        config = load_config()
        logger = setup_logger("backuptool", config)
        logger.info("Service starting")

        self._engine = SyncEngine(config)
        self._engine.start()

        # Watch config file for changes
        self._start_config_watcher(logger)

        # Wait for stop signal
        win32event.WaitForSingleObject(self._stop_event, win32event.INFINITE)

        logger.info("Service stopping")
        self._engine.stop()

    def SvcStop(self) -> None:
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        if self._config_observer is not None:
            try:
                self._config_observer.stop()
                self._config_observer.join(timeout=5)
            except Exception:
                pass
        win32event.SetEvent(self._stop_event)

    def _start_config_watcher(self, logger: logging.Logger) -> None:
        try:
            from watchdog.observers import Observer
            from watchdog.events import FileSystemEventHandler

            engine = self._engine

            class ConfigChangeHandler(FileSystemEventHandler):
                def __init__(self):
                    super().__init__()
                    self._timer: threading.Timer | None = None
                    self._lock = threading.Lock()

                def on_modified(self, event):
                    if event.is_directory:
                        return
                    from pathlib import Path
                    if Path(event.src_path).name != "config.json":
                        return
                    with self._lock:
                        if self._timer:
                            self._timer.cancel()
                        self._timer = threading.Timer(1.0, self._reload)
                        self._timer.start()

                def _reload(self):
                    try:
                        new_config = load_config()
                        engine.reload_config(new_config)
                        logger.info("Config reloaded from file change")
                    except Exception:
                        logger.exception("Failed to reload config")

            self._config_observer = Observer()
            self._config_observer.schedule(ConfigChangeHandler(), str(PROGRAMDATA_DIR), recursive=False)
            self._config_observer.daemon = True
            self._config_observer.start()
            logger.info("Config file watcher started")
        except Exception:
            logger.exception("Failed to start config file watcher")


def run_service() -> None:
    win32serviceutil.HandleCommandLine(BackupToolService)
