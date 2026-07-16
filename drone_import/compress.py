from __future__ import annotations

import os
import subprocess
from pathlib import Path

# Set by drone-autoinsert when launching the container
_IMAGE = os.environ.get("DRONE_IMPORT_IMAGE", "drone-import")
_MEDIA_VOL = os.environ.get("DRONE_MEDIA_VOL", "/mnt/media")


def compress_file(src: Path) -> bool:
    """Run CRF-28 H.264 compression synchronously, replacing src in-place."""
    tmp = src.parent / f".{src.stem}.tmp"
    result = subprocess.run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(src),
        "-c:v", "libx264", "-crf", "28", "-preset", "medium",
        "-pix_fmt", "yuv420p", "-an", "-f", "mp4",
        str(tmp),
    ])
    if result.returncode == 0:
        tmp.rename(src)
        return True
    tmp.unlink(missing_ok=True)
    return False


def compress_background(src: Path, session_name: str) -> None:
    """Spawn a sibling container to compress src in the background."""
    _docker_compress(src, session_name)


def _docker_compress(src: Path, session_name: str) -> None:
    """Spawn a sibling container to compress in the background via the host Docker socket."""
    name = f"drone-compress-{session_name.replace(' ', '-')}"
    subprocess.Popen(
        [
            "docker", "run", "-d", "--rm",
            f"--name={name}",
            "-e", f"DRONE_IMPORT_IMAGE={_IMAGE}",
            "-e", f"DRONE_MEDIA_VOL={_MEDIA_VOL}",
            "-v", f"{_MEDIA_VOL}:{_MEDIA_VOL}",
            "-v", "/var/run/docker.sock:/var/run/docker.sock",
            _IMAGE,
            "compress", str(src),
        ],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def _q(p: Path) -> str:
    return f"'{p}'"
