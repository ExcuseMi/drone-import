#!/usr/bin/env bash
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BOLD='\033[1m'; NC='\033[0m'
info()  { echo -e "${GREEN}[+]${NC} $*"; }
warn()  { echo -e "${YELLOW}[!]${NC} $*"; }
error() { echo -e "${RED}[x]${NC} $*" >&2; exit 1; }
ask()   {
    local var="$1" msg="$2" default="${3:-}"
    read -rp "$(echo -e "${YELLOW}?${NC} $msg${default:+ [${BOLD}$default${NC}]}: ")" val
    printf -v "$var" '%s' "${val:-$default}"
}

[[ $EUID -ne 0 ]] && error "Run as root: sudo ./install.sh"

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DRONE_USER="${SUDO_USER:-$(logname 2>/dev/null || whoami)}"
USER_HOME=$(eval echo "~$DRONE_USER")
CONFIG_DIR="$USER_HOME/.config/drone-import"

echo -e "${BOLD}drone-import installer${NC}"
echo "Installing for user: $DRONE_USER"
echo

# Check dependencies
for cmd in ffmpeg ffprobe python3 pipx; do
    command -v "$cmd" &>/dev/null || error "Missing dependency: $cmd (install with: sudo apt install ${cmd})"
done

# Gather settings
ask DEST        "Footage destination"  "/mnt/media/home_movies/Drone"
ask BACKUP_ROOT "Backup root"          "/mnt/media/originals"
ask MIN_DUR     "Min clip duration (seconds, shorter clips are skipped)" "10"

JELLYFIN_API_KEY=""; JELLYFIN_LIBRARY_ID=""
ask JELLYFIN_URL "Jellyfin URL (leave blank to skip)" "http://localhost:8096"
if [[ -n "$JELLYFIN_URL" ]]; then
    ask JELLYFIN_API_KEY   "Jellyfin API key (leave blank to skip)" ""
    [[ -n "$JELLYFIN_API_KEY" ]] && ask JELLYFIN_LIBRARY_ID "Jellyfin library ID" ""
fi
echo

# Install Python package via pipx (isolated venv, no system package conflicts)
info "Installing drone-import Python package..."
runuser -u "$DRONE_USER" -- pipx install "$REPO_DIR" 2>/dev/null \
    || runuser -u "$DRONE_USER" -- pipx reinstall drone-import

# Config directory
info "Setting up config..."
install -d -o "$DRONE_USER" -m 755 "$CONFIG_DIR" "$CONFIG_DIR/devices"

if [[ ! -f "$CONFIG_DIR/config.yaml" ]]; then
    cat > "$CONFIG_DIR/config.yaml" <<EOF
dest: $DEST
backup_root: $BACKUP_ROOT
min_duration: $MIN_DUR
clip_start_skip: 0

jellyfin_url: $JELLYFIN_URL
jellyfin_api_key: "$JELLYFIN_API_KEY"
jellyfin_library_id: "$JELLYFIN_LIBRARY_ID"
EOF
    chown "$DRONE_USER" "$CONFIG_DIR/config.yaml"
    info "Config written: $CONFIG_DIR/config.yaml"
else
    warn "Config already exists, not overwriting: $CONFIG_DIR/config.yaml"
fi

# Device configs (skip if already present)
for dev_file in "$REPO_DIR/devices/"*.yaml; do
    dev_name=$(basename "$dev_file")
    dest_file="$CONFIG_DIR/devices/$dev_name"
    if [[ ! -f "$dest_file" ]]; then
        install -o "$DRONE_USER" -m 644 "$dev_file" "$dest_file"
        info "Installed device config: $dev_name"
    else
        warn "Device config already exists, not overwriting: $dev_name"
    fi
done

# drone-autoinsert (substitute DRONE_USER placeholder)
info "Installing /usr/local/bin/drone-autoinsert..."
sed "s/REPLACE_USER/$DRONE_USER/g" "$REPO_DIR/scripts/drone-autoinsert" \
    > /usr/local/bin/drone-autoinsert
chmod 755 /usr/local/bin/drone-autoinsert

# drone-sd-cleanup
info "Installing /usr/local/bin/drone-sd-cleanup..."
install -m 755 "$REPO_DIR/scripts/drone-sd-cleanup" /usr/local/bin/drone-sd-cleanup

# Sudoers rule (for manual --cleanup from the drone user)
SUDOERS="/etc/sudoers.d/drone-import"
if [[ ! -f "$SUDOERS" ]]; then
    echo "$DRONE_USER ALL=(ALL) NOPASSWD: /usr/local/bin/drone-sd-cleanup" > "$SUDOERS"
    chmod 440 "$SUDOERS"
    info "Sudoers rule added: $SUDOERS"
else
    warn "Sudoers rule already exists: $SUDOERS"
fi

# Mount point
mkdir -p /mnt/drone-import
info "Mount point ready: /mnt/drone-import"

# udev rule
info "Installing udev rule..."
install -m 644 "$REPO_DIR/udev/99-drone-import.rules" /etc/udev/rules.d/
udevadm control --reload-rules
info "udev rules reloaded."

# systemd service
info "Installing systemd service..."
install -m 644 "$REPO_DIR/systemd/drone-import@.service" /etc/systemd/system/
systemctl daemon-reload
info "systemd daemon reloaded."

echo
echo -e "${GREEN}${BOLD}Installation complete!${NC}"
echo
echo "  Insert an HDZero or DJI SD card to start automatic import."
echo
echo "  Manual use:"
echo "    drone-import run hdzero"
echo "    drone-import run dji"
echo "    drone-import run hdzero --dry-run"
echo "    drone-import compress /path/to/file.mp4"
echo "    drone-import scan"
echo "    drone-import list-devices"
echo
echo "    merge-clips [DIR]"
echo
echo "  Logs (auto-import): journalctl -u 'drone-import@*' -f"
echo "  Logs (compression): journalctl -t drone-compress -f"
echo "  Config: $CONFIG_DIR/config.yaml"
