from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

CONFIG_DIR = Path(os.environ.get("DRONE_IMPORT_CONFIG", Path.home() / ".config" / "drone-import"))


@dataclass
class DeviceConfig:
    name: str
    mount: str
    dcim_glob: str
    file_ext: str
    date_regex: str
    mtime_fallback: bool = False
    clip_start_skip: int = 0
    backup_root: Optional[str] = None


@dataclass
class GlobalConfig:
    dest: str = "/mnt/media/home_movies/Drone"
    backup_root: str = "/mnt/media/originals"
    min_duration: int = 10
    clip_start_skip: int = 0
    session_gap_minutes: int = 30
    jellyfin_url: str = "http://localhost:8096"
    jellyfin_api_key: str = ""
    jellyfin_library_id: str = ""
    devices: dict[str, DeviceConfig] = field(default_factory=dict)


def load_config() -> GlobalConfig:
    config_file = CONFIG_DIR / "config.yaml"
    data: dict = {}
    if config_file.exists():
        with open(config_file) as f:
            data = yaml.safe_load(f) or {}

    cfg = GlobalConfig(
        dest=data.get("dest", "/mnt/media/home_movies/Drone"),
        backup_root=data.get("backup_root", "/mnt/media/originals"),
        min_duration=data.get("min_duration", 10),
        clip_start_skip=data.get("clip_start_skip", 0),
        session_gap_minutes=data.get("session_gap_minutes", 30),
        jellyfin_url=data.get("jellyfin_url", "http://localhost:8096"),
        jellyfin_api_key=data.get("jellyfin_api_key", ""),
        jellyfin_library_id=data.get("jellyfin_library_id", ""),
    )

    devices_dir = CONFIG_DIR / "devices"
    if devices_dir.exists():
        for dev_file in devices_dir.glob("*.yaml"):
            device_id = dev_file.stem
            dev_data: dict = yaml.safe_load(dev_file.read_text()) or {}
            cfg.devices[device_id] = DeviceConfig(
                name=dev_data.get("name", device_id),
                mount=dev_data.get("mount", f"/mnt/{device_id}"),
                dcim_glob=dev_data.get("dcim_glob", "DCIM"),
                file_ext=dev_data.get("file_ext", "mp4"),
                date_regex=dev_data.get("date_regex", ""),
                mtime_fallback=dev_data.get("mtime_fallback", False),
                clip_start_skip=dev_data.get("clip_start_skip", cfg.clip_start_skip),
                backup_root=dev_data.get("backup_root"),
            )

    return cfg
