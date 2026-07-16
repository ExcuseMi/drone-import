from __future__ import annotations

import subprocess
from pathlib import Path


def compress_background(src: Path, session_name: str) -> None:
    """
    Start CRF-28 H.264 compression in a background process.

    Uses systemd-run when available (survives parent service exit).
    Falls back to a detached subprocess for interactive/non-systemd use.
    Output is always logged to the systemd journal under the 'drone-compress' identifier.
    """
    final = src
    tmp = src.parent / f".{session_name}.tmp"

    cmd = (
        f"echo 'start: {session_name}' | systemd-cat -t drone-compress 2>/dev/null; "
        f"ffmpeg -hide_banner -loglevel error -y "
        f"-i {_q(final)} "
        f"-c:v libx264 -crf 28 -preset medium -pix_fmt yuv420p -an -f mp4 {_q(tmp)} "
        f"&& mv {_q(tmp)} {_q(final)} "
        f"&& echo \"done: $(du -h {_q(final)} | cut -f1)\" | systemd-cat -t drone-compress 2>/dev/null "
        f"|| {{ echo 'FAILED: {session_name}' | systemd-cat -t drone-compress 2>/dev/null; rm -f {_q(tmp)}; }}"
    )

    unit = f"drone-compress-{session_name.replace(' ', '-')}"
    result = subprocess.run(
        ["systemd-run", "--no-block", f"--unit={unit}", f"--description=Compress {session_name}",
         "bash", "-c", cmd],
        capture_output=True,
    )

    if result.returncode != 0:
        # Detached subprocess — survives this process exiting (start_new_session creates a new process group)
        subprocess.Popen(
            ["bash", "-c", cmd],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )


def _q(p: Path) -> str:
    return f"'{p}'"
