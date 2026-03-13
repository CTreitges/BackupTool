from __future__ import annotations

import logging
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

from config import Config

log = logging.getLogger(__name__)

# Filename format in recycle bin:
#   YYYY-MM-DD_HHMMSS__originalname.ext
# The double underscore separates timestamp from original filename.
_SEPARATOR = "__"
_TS_FORMAT = "%Y-%m-%d_%H%M%S"
_TS_LEN = 17  # len("2026-03-13_143022")


class RecycleBin:
    def __init__(self, config: Config, bin_root: Path) -> None:
        self._config = config
        self._bin_root = bin_root

    def _unique_name(self, target_dir: Path, base_name: str) -> str:
        candidate = base_name
        counter = 1
        while (target_dir / candidate).exists():
            stem = Path(base_name).stem
            suffix = Path(base_name).suffix
            candidate = f"{stem}_{counter:03d}{suffix}"
            counter += 1
        return candidate

    def move_to_bin(self, source_file: Path, original_path: str, pair_id: str,
                    rel_dir: str = "") -> None:
        """Move a file to the recycle bin, preserving subfolder structure.

        rel_dir: relative directory path within the sync root (e.g. "sub1/sub2").
                 The file will be placed in __RecycleBin__/sub1/sub2/timestamp__file.ext
        """
        target_dir = self._bin_root / rel_dir if rel_dir else self._bin_root
        target_dir.mkdir(parents=True, exist_ok=True)

        ts = datetime.now(timezone.utc).strftime(_TS_FORMAT)
        base_name = f"{ts}{_SEPARATOR}{source_file.name}"
        unique_name = self._unique_name(target_dir, base_name)

        dest = target_dir / unique_name
        try:
            shutil.move(str(source_file), str(dest))
        except Exception:
            log.exception("Failed to move %s to recycle bin", source_file)
            return

        log.info("Moved %s -> recycle bin as %s", source_file, dest.relative_to(self._bin_root))

    def purge_expired(self) -> None:
        if not self._bin_root.exists():
            return
        now = datetime.now(timezone.utc)
        # Walk all subdirectories
        for f in self._bin_root.rglob("*"):
            if not f.is_file():
                continue
            # Clean up old .meta.json files from previous format
            if f.name.endswith(".meta.json"):
                f.unlink()
                log.info("Cleaned up old metadata: %s", f.name)
                continue
            try:
                ts_str = f.name[:_TS_LEN]
                deleted_at = datetime.strptime(ts_str, _TS_FORMAT).replace(tzinfo=timezone.utc)
                age_days = (now - deleted_at).days
                if age_days >= self._config.retention_days:
                    f.unlink()
                    log.info("Purged expired file: %s", f.name)
            except (ValueError, IndexError):
                continue

        # Clean up empty subdirectories
        for d in sorted(self._bin_root.rglob("*"), reverse=True):
            if d.is_dir():
                try:
                    d.rmdir()  # only succeeds if empty
                except OSError:
                    pass
