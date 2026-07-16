from __future__ import annotations

import re
import shutil
import subprocess
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from .compress import compress_background
from .config import DeviceConfig, GlobalConfig
from .jellyfin import trigger_scan
from .merge import merge_clips


def run_import(
    device_id: str,
    cfg: GlobalConfig,
    mount: str | None = None,
    dry_run: bool = False,
    cleanup: bool = False,
) -> None:
    dev = cfg.devices.get(device_id)
    if not dev:
        available = ", ".join(cfg.devices) or "none"
        raise SystemExit(f"Unknown device '{device_id}'. Available: {available}")

    if mount:
        dev = _override_mount(dev, mount)

    backup_root = Path(dev.backup_root or cfg.backup_root) / device_id
    dest = Path(cfg.dest)

    print(f"Device : {dev.name}")
    print(f"Source : {dev.mount}")
    print(f"Dest   : {dest}")
    if dry_run:
        print("(dry run)")
    print()

    try:
        clips = _collect_clips(dev, cfg.min_duration)
        if not clips:
            print("No clips to import.")
            return

        sessions: dict[tuple[str, str], list[Path]] = defaultdict(list)
        for clip, date_key, hour in clips:
            sessions[(date_key, hour)].append(clip)

        imported_any = False

        for (date_key, hour), session_clips in sorted(sessions.items()):
            new_clips = [c for c in session_clips if not list(backup_root.rglob(c.name))]

            if not new_clips:
                print(f"  {date_key} {hour}h — all {len(session_clips)} clip(s) already imported, skipping")
                continue

            session_name = f"{date_key} {hour}h {dev.name}"
            date_folder = dest / date_key
            session_tmp = date_folder / f"_session_{hour}h"
            backup_dir = backup_root / session_name

            print(f"  {date_key} {hour}h — {len(new_clips)} new clip(s) → {date_folder}")

            if not dry_run:
                session_tmp.mkdir(parents=True, exist_ok=True)
                backup_dir.mkdir(parents=True, exist_ok=True)

            for clip in new_clips:
                print(f"    copy: {clip.name}")
                if not dry_run:
                    shutil.copy2(clip, session_tmp / clip.name)
                    shutil.copy2(clip, backup_dir / clip.name)

            if not dry_run:
                print(f"    backed up {len(new_clips)} file(s) to {backup_dir}")

                if dev.clip_start_skip > 0:
                    _trim_clips(session_tmp, dev.clip_start_skip)

                final = _merge_session(session_tmp, date_folder, session_name)
                if final:
                    _jellyfin_scan(cfg)
                    print("    compressing in background (CRF 28)...")
                    compress_background(final, session_name)
            else:
                print("    → merge + compress (skipped in dry run)")

            imported_any = True

        if not imported_any:
            print("Nothing new to import.")

    finally:
        if cleanup and not dry_run:
            _cleanup_sd(dev.mount)


def _collect_clips(dev: DeviceConfig, min_duration: int) -> list[tuple[Path, str, str]]:
    mount = Path(dev.mount)
    results = []

    for dcim_dir in mount.glob(dev.dcim_glob):
        if not dcim_dir.is_dir():
            continue
        for f in dcim_dir.glob(f"*.{dev.file_ext}"):
            if not f.is_file():
                continue

            date_key, hour = _extract_date(f, dev)
            if not date_key:
                print(f"  skip (unrecognised name): {f.name}")
                continue

            dur = _get_duration(f)
            if dur is None or dur < min_duration:
                print(f"  skip ({dur}s < {min_duration}s): {f.name}")
                continue

            results.append((f, date_key, hour))

    return sorted(results, key=lambda x: x[0].name)


def _extract_date(f: Path, dev: DeviceConfig) -> tuple[str, str] | tuple[None, None]:
    if dev.date_regex:
        m = re.match(dev.date_regex, f.name)
        if m:
            return f"{m.group(1)}-{m.group(2)}-{m.group(3)}", m.group(4)

    if dev.mtime_fallback:
        mtime = datetime.fromtimestamp(f.stat().st_mtime)
        print(f"  note: using mtime ({mtime:%Y-%m-%d %Hh}) for {f.name}")
        return mtime.strftime("%Y-%m-%d"), mtime.strftime("%H")

    return None, None


def _get_duration(f: Path) -> int | None:
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", str(f)],
        capture_output=True,
        text=True,
    )
    try:
        return int(float(result.stdout.strip()))
    except (ValueError, AttributeError):
        return None


def _trim_clips(session_tmp: Path, skip_seconds: int) -> None:
    print(f"    trimming first {skip_seconds}s from each clip...")
    for f in sorted(session_tmp.iterdir()):
        if not f.is_file():
            continue
        tmp = f.with_name(f.stem + "_trim" + f.suffix)
        result = subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error",
             "-ss", str(skip_seconds), "-i", str(f), "-c", "copy", str(tmp)],
            capture_output=True,
        )
        if result.returncode == 0:
            tmp.replace(f)
        else:
            tmp.unlink(missing_ok=True)


def _merge_session(session_tmp: Path, date_folder: Path, session_name: str) -> Path | None:
    clips = sorted([c for c in session_tmp.iterdir() if c.is_file()], key=lambda p: p.name)
    if not clips:
        return None

    merged_tmp = session_tmp / "_merged.mp4"
    final = date_folder / f"{session_name}.mp4"

    print(f"    merging {len(clips)} clip(s)...")
    try:
        merge_clips(clips, merged_tmp)
        merged_tmp.rename(final)
        shutil.rmtree(session_tmp)
        print(f"    → {final}")
        return final
    except subprocess.CalledProcessError:
        print("    merge FAILED", flush=True)
        shutil.rmtree(session_tmp, ignore_errors=True)
        return None


def _jellyfin_scan(cfg: GlobalConfig) -> None:
    if not cfg.jellyfin_api_key or not cfg.jellyfin_library_id:
        return
    ok = trigger_scan(cfg.jellyfin_url, cfg.jellyfin_api_key, cfg.jellyfin_library_id)
    print(f"    → Jellyfin scan {'triggered' if ok else 'failed'}")


def _cleanup_sd(mount: str) -> None:
    subprocess.run(["sudo", "drone-sd-cleanup", mount], check=False)


def _override_mount(dev: DeviceConfig, mount: str) -> DeviceConfig:
    import dataclasses
    return dataclasses.replace(dev, mount=mount)
