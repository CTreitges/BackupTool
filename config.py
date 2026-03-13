from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

PROGRAMDATA_DIR = Path(os.environ.get("PROGRAMDATA", "C:/ProgramData")) / "BackupTool"
CONFIG_PATH = PROGRAMDATA_DIR / "config.json"


@dataclass
class FolderPair:
    source: str
    destination: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    enabled: bool = True


@dataclass
class Config:
    folder_pairs: list[FolderPair] = field(default_factory=list)
    retention_days: int = 30
    scan_interval_minutes: int = 30
    recycle_bin_subdir: str = "__RecycleBin__"
    log_level: str = "INFO"


def _config_to_dict(config: Config) -> dict[str, Any]:
    d = asdict(config)
    return d


def _dict_to_config(d: dict[str, Any]) -> Config:
    pairs = [FolderPair(**p) for p in d.get("folder_pairs", [])]
    return Config(
        folder_pairs=pairs,
        retention_days=d.get("retention_days", 30),
        scan_interval_minutes=d.get("scan_interval_minutes", 30),
        recycle_bin_subdir=d.get("recycle_bin_subdir", "__RecycleBin__"),
        log_level=d.get("log_level", "INFO"),
    )


def load_config(path: Path = CONFIG_PATH) -> Config:
    if not path.exists():
        return Config()
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    return _dict_to_config(d)


def save_config(config: Config, path: Path = CONFIG_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(_config_to_dict(config), indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def validate_config(config: Config) -> list[str]:
    errors: list[str] = []
    if config.retention_days < 1:
        errors.append("retention_days must be >= 1")
    if config.scan_interval_minutes < 1:
        errors.append("scan_interval_minutes must be >= 1")
    if not config.recycle_bin_subdir:
        errors.append("recycle_bin_subdir must not be empty")
    for i, pair in enumerate(config.folder_pairs):
        if not pair.source:
            errors.append(f"Pair {i}: source path is empty")
        if not pair.destination:
            errors.append(f"Pair {i}: destination path is empty")
    return errors
