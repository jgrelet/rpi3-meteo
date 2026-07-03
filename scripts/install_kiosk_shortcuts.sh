#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
AUTOSTART_DIR="${HOME}/.config/autostart"

desktop_dir() {
    if command -v xdg-user-dir >/dev/null 2>&1; then
        local xdg_desktop
        xdg_desktop="$(xdg-user-dir DESKTOP 2>/dev/null || true)"
        if [ -n "$xdg_desktop" ] && [ "$xdg_desktop" != "$HOME" ]; then
            echo "$xdg_desktop"
            return
        fi
    fi

    if [ -d "${HOME}/Bureau" ]; then
        echo "${HOME}/Bureau"
        return
    fi

    echo "${HOME}/Desktop"
}

DESKTOP_DIR="$(desktop_dir)"

mkdir -p "$DESKTOP_DIR" "$AUTOSTART_DIR"

install_launcher() {
    local src="$1"
    local dst="$2"
    sed "s|__APP_DIR__|${APP_DIR}|g" "$src" > "$dst"
    chmod +x "$dst"
}

install_launcher "${APP_DIR}/desktop/rpi-meteo-kiosk.desktop" "${DESKTOP_DIR}/rpi-meteo-kiosk.desktop"
install_launcher "${APP_DIR}/desktop/rpi-meteo-kiosk-stop.desktop" "${DESKTOP_DIR}/rpi-meteo-kiosk-stop.desktop"
install_launcher "${APP_DIR}/desktop/rpi-meteo-kiosk-autostart.desktop" "${AUTOSTART_DIR}/rpi-meteo-kiosk-autostart.desktop"

chmod +x "${APP_DIR}/scripts/start_kiosk.sh" "${APP_DIR}/scripts/stop_kiosk.sh"

echo "Lanceurs installes pour ${APP_DIR}"
echo "- Bureau: ${DESKTOP_DIR}/rpi-meteo-kiosk.desktop"
echo "- Bureau: ${DESKTOP_DIR}/rpi-meteo-kiosk-stop.desktop"
echo "- Autostart: ${AUTOSTART_DIR}/rpi-meteo-kiosk-autostart.desktop"
