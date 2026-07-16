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
    """Start compression in the background, adapting to the runtime environment."""
    if _in_docker():
        _docker_compress(src, session_name)
    else:
        _native_compress(src, session_name)


def _in_docker() -> bool:
    return Path("/.dockerenv").exists()


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


def _native_compress(src: Path, session_name: str) -> None:
    """systemd-run when available (survives service exit), falls back to detached subprocess."""
    tmp = src.parent / f".{session_name}.tmp"
    cmd = (
        f"echo 'start: {session_name}' | systemd-cat -t drone-compress 2>/dev/null; "
        f"ffmpeg -hide_banner -loglevel error -y -i {_q(src)} "
        f"-c:v libx264 -crf 28 -preset medium -pix_fmt yuv420p -an -f mp4 {_q(tmp)} "
        f"&& mv {_q(tmp)} {_q(src)} "
        f"&& echo \"done: $(du -h {_q(src)} | cut -f1)\" | systemd-cat -t drone-compress 2>/dev/null "
        f"|| {{ echo 'FAILED: {session_name}' | systemd-cat -t drone-compress 2>/dev/null; rm -f {_q(tmp)}; }}"
    )
    unit = f"drone-compress-{session_name.replace(' ', '-')}"
    result = subprocess.run(
        ["systemd-run", "--no-block", f"--unit={unit}", f"--description=Compress {session_name}",
         "bash", "-c", cmd],
        capture_output=True,
    )
    if result.returncode != 0:
        subprocess.Popen(
            ["bash", "-c", cmd],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )


def _q(p: Path) -> str:
    return f"'{p}'"
