#!/usr/bin/env bash
set -euo pipefail

[[ $EUID -ne 0 ]] && echo "Run as root: sudo ./uninstall.sh" >&2 && exit 1

echo "Removing drone-import..."

rm -f /usr/local/bin/drone-autoinsert
rm -f /usr/local/bin/merge-clips
rm -f /usr/local/bin/drone-sd-cleanup
rm -f /etc/udev/rules.d/99-drone-import.rules
rm -f /etc/systemd/system/drone-import@.service
rm -f /etc/sudoers.d/drone-import

udevadm control --reload-rules
systemctl daemon-reload

pip3 uninstall -q -y drone-import 2>/dev/null || true

echo "Done. User config in ~/.config/drone-import/ was left in place."
