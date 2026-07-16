"""merge-clips: merge split drone recordings into one file per group."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from collections import defaultdict
from pathlib import Path

import click

VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".avi", ".m4v", ".mts", ".m2ts", ".ts"}


def _skeleton(name: str) -> str:
    """Strip all digit runs from a lowercased filename — files that share a
    skeleton belong to the same recording split across multiple clips."""
    return re.sub(r"\d+", "", name.lower())


def _natural_key(p: Path) -> list:
    parts = re.split(r"(\d+)", p.name)
    return [int(c) if c.isdigit() else c.lower() for c in parts]


def _build_concat_file(clips: list[Path]) -> Path:
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False)
    for clip in clips:
        f.write(f"file '{clip.resolve()}'\n")
    f.close()
    return Path(f.name)


def _merge(clips: list[Path], out: Path, no_audio: bool, reencode: bool) -> bool:
    concat = _build_concat_file(clips)
    audio = ["-an"] if no_audio else []
    try:
        if not reencode:
            cmd = [
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-f", "concat", "-safe", "0", "-i", str(concat),
                "-c", "copy", *audio, "-movflags", "+faststart",
                str(out),
            ]
        else:
            cmd = [
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-f", "concat", "-safe", "0", "-i", str(concat),
                "-c:v", "libx264", "-crf", "18", "-preset", "medium",
                "-c:a", "aac", "-b:a", "192k", *audio,
                "-movflags", "+faststart",
                str(out),
            ]
        result = subprocess.run(cmd, capture_output=True)
        return result.returncode == 0
    finally:
        concat.unlink(missing_ok=True)


def _unique_output(folder: Path, ext: str) -> Path:
    base = folder.name
    candidate = folder / f"{base}.{ext}"
    if not candidate.exists():
        return candidate
    n = 2
    while True:
        candidate = folder / f"{base}_{n}.{ext}"
        if not candidate.exists():
            return candidate
        n += 1


@click.command()
@click.argument("directory", default=".", type=click.Path(file_okay=False, path_type=Path))
@click.option("--dry-run", "-n", is_flag=True, help="Show groups without merging")
@click.option("--no-audio", is_flag=True, envvar="MERGE_NO_AUDIO",
              help="Strip audio from output (also set via MERGE_NO_AUDIO=1)")
def main(directory: Path, dry_run: bool, no_audio: bool) -> None:
    """Merge split drone recordings in DIRECTORY into one file per group.

    Files are grouped by their "skeleton" (filename with digit runs removed),
    then sorted naturally. Stream copy is tried first; on failure it re-encodes.
    Source clips are removed after a successful merge.
    """
    directory = directory.resolve()
    if not directory.is_dir():
        raise click.ClickException(f"Not a directory: {directory}")

    click.echo(f"Scanning: {directory}")

    groups: dict[str, list[Path]] = defaultdict(list)
    for f in directory.iterdir():
        if not f.is_file():
            continue
        if f.suffix.lower() not in VIDEO_EXTS:
            continue
        if "_merged" in f.stem:
            continue
        groups[_skeleton(f.name)].append(f)

    if not groups:
        click.echo("No video files found.")
        return

    merged_any = False

    for skeleton, clips in sorted(groups.items()):
        clips = sorted(clips, key=_natural_key)
        ext = clips[0].suffix.lstrip(".").lower()
        out_ext = "mp4" if ext == "ts" else ext
        out = _unique_output(directory, out_ext)

        click.echo(f"\nGroup [{skeleton}] -> {out.name} ({len(clips)} file(s), input ext: .{ext})")
        for c in clips:
            click.echo(f"    {c.name}")

        if len(clips) < 2:
            click.echo("  -> only one file, skipping")
            continue

        if dry_run:
            continue

        click.echo("  merging (stream copy)...")
        if _merge(clips, out, no_audio, reencode=False):
            click.echo(f"  ok -> {out.name}")
        else:
            click.echo("  stream copy failed, retrying with re-encode...")
            if _merge(clips, out, no_audio, reencode=True):
                click.echo(f"  ok -> {out.name} (re-encoded)")
            else:
                click.echo(f"  FAILED — leaving originals in place", err=True)
                continue

        for clip in clips:
            clip.unlink()
            for thumb_ext in (".jpg", ".jpeg"):
                thumb = clip.with_suffix(thumb_ext)
                if not thumb.exists():
                    thumb = clip.with_suffix(thumb_ext.upper())
                if thumb.exists():
                    thumb.unlink()
                    click.echo(f"  removed thumbnail {thumb.name}")

        merged_any = True

    click.echo()
    click.echo("Done.")
