from __future__ import annotations

import json
import logging
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

from config import Config

log = logging.getLogger(__name__)


class RecycleBin:
    def __init__(self, config: Config, bin_root: Path) -> None:
        self._config = config
        self._bin_root = bin_root

    def _unique_name(self, base_name: str) -> str:
        candidate = base_name
        counter = 1
        while (self._bin_root / candidate).exists() or (self._bin_root / (candidate + ".meta.json")).exists():
            stem = Path(base_name).stem
            suffix = Path(base_name).suffix
            candidate = f"{stem}_{counter:03d}{suffix}"
            counter += 1
        return candidate

    def move_to_bin(self, source_file: Path, original_path: str, pair_id: str) -> None:
        self._bin_root.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")
        base_name = f"{ts}_{source_file.name}"
        unique_name = self._unique_name(base_name)

        dest = self._bin_root / unique_name
        try:
            shutil.move(str(source_file), str(dest))
        except Exception:
            log.exception("Failed to move %s to recycle bin", source_file)
            return

        meta = {
            "original_path": original_path,
            "deleted_at": datetime.now(timezone.utc).isoformat(),
            "source_pair_id": pair_id,
        }
        meta_path = self._bin_root / (unique_name + ".meta.json")
        tmp = meta_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, meta_path)

        log.info("Moved %s → recycle bin as %s", source_file, unique_name)

    def purge_expired(self) -> None:
        if not self._bin_root.exists():
            return
        now = datetime.now(timezone.utc)
        for meta_file in self._bin_root.glob("*.meta.json"):
            try:
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
                deleted_at = datetime.fromisoformat(meta["deleted_at"])
                age_days = (now - deleted_at).days
                if age_days >= self._config.retention_days:
                    data_file = self._bin_root / meta_file.name.removesuffix(".meta.json")
                    if data_file.exists():
                        data_file.unlink()
                        log.info("Purged expired file: %s", data_file.name)
                    meta_file.unlink()
                    log.info("Purged metadata: %s", meta_file.name)
            except Exception:
                log.exception("Error purging %s", meta_file)
