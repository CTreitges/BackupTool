from __future__ import annotations

import logging
import queue
import shutil
import threading
import time
from pathlib import Path

from config import Config, FolderPair, PROGRAMDATA_DIR
from ipc import write_status
from recycle_bin import RecycleBin
from watcher import FolderWatcher, SyncEvent

log = logging.getLogger(__name__)


class SyncEngine:
    def __init__(self, config: Config) -> None:
        self._config = config
        self._lock = threading.Lock()
        self._event_queue: queue.Queue[SyncEvent] = queue.Queue()
        self._watcher = FolderWatcher(self._event_queue)
        self._stop_event = threading.Event()
        self._status: dict = {
            "state": "starting",
            "last_full_scan": None,
            "last_purge": None,
            "errors": [],
        }
        self._status_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        self._watcher.update_pairs(self._config.folder_pairs)
        self._worker_thread = threading.Thread(target=self._worker, daemon=True, name="sync-worker")
        self._scheduler_thread = threading.Thread(target=self._scheduler, daemon=True, name="sync-scheduler")
        self._worker_thread.start()
        self._scheduler_thread.start()
        self._set_state("running")
        log.info("SyncEngine started")

    def stop(self) -> None:
        self._stop_event.set()
        self._event_queue.put(SyncEvent(type="_stop", source_path="", pair=None))  # type: ignore[arg-type]
        self._watcher.stop()
        self._worker_thread.join(timeout=10)
        self._scheduler_thread.join(timeout=10)
        self._set_state("stopped")
        log.info("SyncEngine stopped")

    def reload_config(self, new_config: Config) -> None:
        with self._lock:
            self._config = new_config
        self._watcher.update_pairs(new_config.folder_pairs)
        log.info("Config reloaded – scheduling immediate full scan")
        threading.Thread(target=self._full_scan, daemon=True, name="reload-scan").start()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _set_state(self, state: str) -> None:
        with self._status_lock:
            self._status["state"] = state
        self._flush_status()

    def _add_error(self, msg: str) -> None:
        with self._status_lock:
            errors = self._status.setdefault("errors", [])
            errors.append(msg)
            # Keep only the last 50 errors
            if len(errors) > 50:
                self._status["errors"] = errors[-50:]
        self._flush_status()

    def _clear_errors(self) -> None:
        with self._status_lock:
            self._status["errors"] = []

    def _flush_status(self) -> None:
        with self._status_lock:
            data = dict(self._status)
        try:
            write_status(data)
        except Exception:
            log.exception("Failed to write status.json")

    def _recycle_bin(self, pair: FolderPair) -> RecycleBin:
        with self._lock:
            cfg = self._config
        bin_root = Path(pair.destination) / cfg.recycle_bin_subdir
        return RecycleBin(cfg, bin_root)

    def _dest_path(self, source_path: str, pair: FolderPair) -> Path:
        try:
            rel = Path(source_path).relative_to(pair.source)
        except ValueError:
            # Fallback: use just the filename if relative_to fails
            rel = Path(Path(source_path).name)
            log.warning("Path %s is not relative to %s, using filename only", source_path, pair.source)
        return Path(pair.destination) / rel

    # ------------------------------------------------------------------
    # Worker
    # ------------------------------------------------------------------

    def _worker(self) -> None:
        while not self._stop_event.is_set():
            try:
                event: SyncEvent = self._event_queue.get(timeout=1)
            except queue.Empty:
                continue
            if event.type == "_stop":
                break
            try:
                if event.type == "upsert":
                    self._handle_upsert(event)
                elif event.type == "delete":
                    self._handle_delete(event)
            except Exception as exc:
                log.exception("Error handling event %s", event)
                self._add_error(f"Event {event.type} failed: {exc}")

    def _handle_upsert(self, event: SyncEvent) -> None:
        src = Path(event.source_path)
        if not src.exists() or not src.is_file():
            return
        dest = self._dest_path(event.source_path, event.pair)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            src_stat = src.stat()
            dst_stat = dest.stat()
            if (
                abs(src_stat.st_mtime - dst_stat.st_mtime) < 1
                and src_stat.st_size == dst_stat.st_size
            ):
                return  # Already in sync
        shutil.copy2(str(src), str(dest))
        log.debug("Copied %s → %s", src, dest)

    def _handle_delete(self, event: SyncEvent) -> None:
        dest = self._dest_path(event.source_path, event.pair)
        if not dest.exists():
            return
        rb = self._recycle_bin(event.pair)
        rb.move_to_bin(dest, event.source_path, event.pair.id)

    # ------------------------------------------------------------------
    # Full scan
    # ------------------------------------------------------------------

    def _full_scan(self) -> None:
        with self._lock:
            pairs = list(self._config.folder_pairs)
            recycle_subdir = self._config.recycle_bin_subdir

        log.info("Starting full scan")
        self._clear_errors()
        for pair in pairs:
            if not pair.enabled:
                continue
            try:
                self._scan_pair(pair, recycle_subdir)
            except Exception as exc:
                log.exception("Full scan failed for pair %s", pair.id)
                self._add_error(f"Full scan failed for pair {pair.id}: {exc}")

        import datetime
        with self._status_lock:
            self._status["last_full_scan"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        self._flush_status()
        log.info("Full scan complete")

    def _scan_pair(self, pair: FolderPair, recycle_subdir: str) -> None:
        src_root = Path(pair.source)
        dst_root = Path(pair.destination)

        if not src_root.exists():
            log.warning("Source not found: %s", src_root)
            return

        # Build relative path sets
        src_rel: set[str] = set()
        for p in src_root.rglob("*"):
            if p.is_file():
                src_rel.add(str(p.relative_to(src_root)))

        dst_rel: set[str] = set()
        if dst_root.exists():
            for p in dst_root.rglob("*"):
                if p.is_file():
                    rel = str(p.relative_to(dst_root))
                    parts = Path(rel).parts
                    if parts[0] == recycle_subdir:
                        continue
                    if rel.endswith(".meta.json"):
                        continue
                    dst_rel.add(rel)

        # Upsert missing/outdated files
        for rel in src_rel:
            src_file = src_root / rel
            dst_file = dst_root / rel
            if not dst_file.exists():
                dst_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(src_file), str(dst_file))
                log.debug("Full-scan copy: %s", rel)
            else:
                src_stat = src_file.stat()
                dst_stat = dst_file.stat()
                if abs(src_stat.st_mtime - dst_stat.st_mtime) >= 1 or src_stat.st_size != dst_stat.st_size:
                    shutil.copy2(str(src_file), str(dst_file))
                    log.debug("Full-scan update: %s", rel)

        # Move orphans to recycle bin
        rb = self._recycle_bin(pair)
        orphans = dst_rel - src_rel
        for rel in orphans:
            dst_file = dst_root / rel
            if dst_file.exists():
                rb.move_to_bin(dst_file, str(src_root / rel), pair.id)

    # ------------------------------------------------------------------
    # Scheduler
    # ------------------------------------------------------------------

    def _scheduler(self) -> None:
        last_scan = 0.0
        last_purge = 0.0

        # Run initial full scan shortly after start
        time.sleep(5)
        if not self._stop_event.is_set():
            self._full_scan()
            last_scan = time.monotonic()

        while not self._stop_event.is_set():
            now = time.monotonic()

            with self._lock:
                scan_interval = self._config.scan_interval_minutes * 60

            if now - last_scan >= scan_interval:
                self._full_scan()
                last_scan = now

            if now - last_purge >= 3600:
                self._purge()
                last_purge = now

            self._stop_event.wait(timeout=30)

    def _purge(self) -> None:
        with self._lock:
            pairs = list(self._config.folder_pairs)
            recycle_subdir = self._config.recycle_bin_subdir
            cfg = self._config

        log.info("Running recycle bin purge")
        seen_bins: set[str] = set()
        for pair in pairs:
            bin_root = Path(pair.destination) / recycle_subdir
            key = str(bin_root)
            if key in seen_bins:
                continue
            seen_bins.add(key)
            rb = RecycleBin(cfg, bin_root)
            rb.purge_expired()

        import datetime
        with self._status_lock:
            self._status["last_purge"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        self._flush_status()
