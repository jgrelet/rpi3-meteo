#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
DESKTOP_DIR="${HOME}/Desktop"
AUTOSTART_DIR="${HOME}/.config/autostart"

mkdir -p "$DESKTOP_DIR" "$AUTOSTART_DIR"

install_launcher() {
    local src="$1"
    local dst="$2"
    sed "s|__APP_DIR__|${APP_DIR}|g" "$src" > "$dst"
    chmod +x "$dst"
}

install_launcher "${APP_DIR}/desktop/rpi3-meteo-kiosk.desktop" "${DESKTOP_DIR}/rpi3-meteo-kiosk.desktop"
install_launcher "${APP_DIR}/desktop/rpi3-meteo-kiosk-stop.desktop" "${DESKTOP_DIR}/rpi3-meteo-kiosk-stop.desktop"
install_launcher "${APP_DIR}/desktop/rpi3-meteo-kiosk-autostart.desktop" "${AUTOSTART_DIR}/rpi3-meteo-kiosk-autostart.desktop"

chmod +x "${APP_DIR}/scripts/start_kiosk.sh" "${APP_DIR}/scripts/stop_kiosk.sh"

echo "Lanceurs installes pour ${APP_DIR}"
echo "- Bureau: ${DESKTOP_DIR}/rpi3-meteo-kiosk.desktop"
echo "- Bureau: ${DESKTOP_DIR}/rpi3-meteo-kiosk-stop.desktop"
echo "- Autostart: ${AUTOSTART_DIR}/rpi3-meteo-kiosk-autostart.desktop"
