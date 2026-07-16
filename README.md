# drone-import

Plug in an SD card — footage gets copied, backed up, merged into one file per session, and compressed in the background. Supports HDZero BoxPro (FAT32) and DJI cameras (exFAT). Optional Jellyfin library scan after import.

## What it does

1. **Detects** — udev triggers on USB insertion
2. **Identifies** — mounts and checks DCIM folder structure (HDZero vs DJI)
3. **Copies** — clips to a temp session folder, originals to a backup directory
4. **Skips** — clips shorter than `min_duration`, already-imported clips (checked against backup)
5. **Trims** — optionally removes the first N seconds from each clip
6. **Merges** — all clips for a session into one file: `YYYY-MM-DD HHh Device Name.mp4`
7. **Compresses** — CRF 28 H.264 in the background (doesn't block the SD card)
8. **Scans** — triggers a Jellyfin library refresh (optional)
9. **Cleans** — clears footage from SD card and unmounts

## Requirements

- Linux with systemd and udev
- `ffmpeg` and `ffprobe`
- Python 3.10+
- `exfatprogs` or `exfat-fuse` for DJI cards: `sudo apt install exfatprogs`

## Install

```bash
git clone https://github.com/youruser/drone-import
cd drone-import
sudo ./install.sh
```

The installer asks for your footage destination, backup path, and optional Jellyfin settings. It sets up udev, systemd, config, and the Python package.

## Config

After install, config lives at `~/.config/drone-import/config.yaml`:

```yaml
dest: /mnt/media/home_movies/Drone
backup_root: /mnt/media/originals
min_duration: 10        # skip clips shorter than this (seconds)
clip_start_skip: 0      # trim from start of each clip (seconds)

jellyfin_url: http://localhost:8096
jellyfin_api_key: ""
jellyfin_library_id: ""
```

Device profiles are in `~/.config/drone-import/devices/`. Edit `clip_start_skip` per device if needed.

## Adding a new camera

Create `~/.config/drone-import/devices/mycamera.yaml`:

```yaml
name: My Camera
mount: /mnt/drone-import
dcim_glob: DCIM/CAMERA_*
file_ext: mp4
date_regex: '^CAM_(\d{4})(\d{2})(\d{2})(\d{2})'
mtime_fallback: false
clip_start_skip: 0
```

The `date_regex` must have four capture groups: year, month, day, hour.  
Set `mtime_fallback: true` if filenames don't include a date.

Then plug in the card — the autoinsert script will try each known filesystem type and check for the DCIM glob match.

## Manual use

```bash
drone-import run hdzero            # import from configured mount
drone-import run dji --dry-run     # preview without doing anything
drone-import compress video.mp4    # compress a specific file in background
drone-import scan                  # trigger Jellyfin scan
drone-import list-devices          # show configured devices

merge-clips                        # merge clips in current directory
merge-clips /path/to/folder        # merge clips in a specific folder
merge-clips -n                     # dry run — show groups without merging
```

## Logs

```bash
journalctl -u 'drone-import@*' -f   # import pipeline
journalctl -t drone-compress -f      # background compression
```

## Output structure

```
Drone/
  2026-07-16/
    2026-07-16 19h HDZero BoxPro.mp4
    2026-07-16 19h DJI O4 Lite.mp4
  2026-07-17/
    ...
```

Multiple sessions on the same day (different hours or cameras) go in the same date folder as separate files.

## Uninstall

```bash
sudo ./uninstall.sh
```

User config in `~/.config/drone-import/` is left in place.
