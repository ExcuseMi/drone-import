from __future__ import annotations

from pathlib import Path

import click

from .compress import compress_file
from .config import load_config
from .importer import run_import
from .jellyfin import trigger_scan


@click.group()
def main() -> None:
    """Automated drone footage importer for HDZero and DJI cameras."""


@main.command()
@click.argument("device")
@click.option("--mount", "-m", default=None, help="Override mount point from config")
@click.option("--dry-run", "-n", is_flag=True, help="Show what would be imported")
@click.option("--cleanup", is_flag=True, help="Clear SD card and unmount after import")
def run(device: str, mount: str | None, dry_run: bool, cleanup: bool) -> None:
    """Import footage from a device (e.g. hdzero, dji)."""
    cfg = load_config()
    run_import(device, cfg, mount=mount, dry_run=dry_run, cleanup=cleanup)


@main.command()
@click.argument("file", type=click.Path(exists=True, path_type=Path))
def compress(file: Path) -> None:
    """Compress a file to CRF-28 H.264 in-place (runs synchronously inside its container)."""
    click.echo(f"Compressing {file.name}...")
    ok = compress_file(file)
    if not ok:
        click.echo(f"Failed: {file}", err=True)
        raise SystemExit(1)


@main.command()
def scan() -> None:
    """Trigger a Jellyfin library scan."""
    cfg = load_config()
    ok = trigger_scan(cfg.jellyfin_url, cfg.jellyfin_api_key, cfg.jellyfin_library_id)
    if ok:
        click.echo("Jellyfin scan triggered.")
    else:
        click.echo("Scan failed or Jellyfin not configured.", err=True)
        raise SystemExit(1)


@main.command(name="list-devices")
def list_devices() -> None:
    """List configured devices."""
    cfg = load_config()
    if not cfg.devices:
        click.echo("No devices configured.")
        return
    for device_id, dev in sorted(cfg.devices.items()):
        click.echo(f"  {device_id:12s}  {dev.name}  (mount: {dev.mount})")
