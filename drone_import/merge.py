from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path


def merge_clips(clips: list[Path], output: Path) -> None:
    """Merge clips using ffmpeg concat demuxer (stream copy, no audio, no re-encode)."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        concat_file = Path(f.name)
        for clip in clips:
            f.write(f"file '{clip}'\n")

    try:
        subprocess.run(
            [
                "ffmpeg", "-hide_banner", "-loglevel", "error",
                "-f", "concat", "-safe", "0",
                "-i", str(concat_file),
                "-c", "copy", "-an",
                str(output),
            ],
            check=True,
        )
    finally:
        concat_file.unlink(missing_ok=True)
