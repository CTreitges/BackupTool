from __future__ import annotations

import fnmatch
import logging
import queue
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from watchdog.events import FileSystemEventHandler, FileSystemEvent
from watchdog.observers import Observer

from config import FolderPair

log = logging.getLogger(__name__)

_IGNORE_PATTERNS = ["~$*", "*.tmp", "*.part", "desktop.ini", "thumbs.db"]
_DEBOUNCE_SECONDS = 0.5


def _should_ignore(path: str) -> bool:
    name = Path(path).name
    return any(fnmatch.fnmatch(name.lower(), pat.lower()) for pat in _IGNORE_PATTERNS)


@dataclass
class SyncEvent:
    type: str  # 'upsert' | 'delete'
    source_path: str
    pair: FolderPair


class SyncEventHandler(FileSystemEventHandler):
    def __init__(self, pair: FolderPair, event_queue: queue.Queue[SyncEvent]) -> None:
        super().__init__()
        self._pair = pair
        self._queue = event_queue
        self._pending: dict[str, threading.Timer] = {}
        self._lock = threading.Lock()

    def _schedule(self, event_type: str, path: str) -> None:
        if _should_ignore(path):
            return
        with self._lock:
            existing = self._pending.pop(path, None)
            if existing:
                existing.cancel()
            t = threading.Timer(_DEBOUNCE_SECONDS, self._emit, args=(event_type, path))
            self._pending[path] = t
            t.start()

    def _emit(self, event_type: str, path: str) -> None:
        with self._lock:
            self._pending.pop(path, None)
        self._queue.put(SyncEvent(type=event_type, source_path=path, pair=self._pair))

    def on_created(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._schedule("upsert", event.src_path)

    def on_modified(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._schedule("upsert", event.src_path)

    def on_deleted(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._schedule("delete", event.src_path)

    def on_moved(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._schedule("delete", event.src_path)
            self._schedule("upsert", event.dest_path)


class FolderWatcher:
    def __init__(self, event_queue: queue.Queue[SyncEvent]) -> None:
        self._queue = event_queue
        self._observer = Observer()
        self._watches: dict[str, object] = {}
        self._lock = threading.Lock()
        self._observer.start()

    def update_pairs(self, pairs: list[FolderPair]) -> None:
        enabled_sources = {p.source for p in pairs if p.enabled}

        with self._lock:
            # Remove watches for pairs no longer active
            for src in list(self._watches):
                if src not in enabled_sources:
                    self._observer.unschedule(self._watches.pop(src))
                    log.info("Stopped watching: %s", src)

            # Add watches for new pairs
            for pair in pairs:
                if not pair.enabled or pair.source in self._watches:
                    continue
                src_path = Path(pair.source)
                if not src_path.exists():
                    log.warning("Source path does not exist, skipping: %s", pair.source)
                    continue
                handler = SyncEventHandler(pair, self._queue)
                watch = self._observer.schedule(handler, str(src_path), recursive=True)
                self._watches[pair.source] = watch
                log.info("Watching: %s", pair.source)

    def stop(self) -> None:
        self._observer.stop()
        self._observer.join()
