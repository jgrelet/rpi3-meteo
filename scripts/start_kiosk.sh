#!/bin/bash
set -euo pipefail

APP_URL="${APP_URL:-http://127.0.0.1:8000}"
BROWSER_BIN="${BROWSER_BIN:-chromium-browser}"
PROFILE_DIR="${PROFILE_DIR:-${HOME}/.config/rpi3-meteo-kiosk}"
WAYLAND_DISPLAY_NAME="${WAYLAND_DISPLAY_NAME:-wayland-0}"
DISPLAY_OUTPUT="${DISPLAY_OUTPUT:-DSI-1}"
SCREEN_TIMEOUT="${SCREEN_TIMEOUT:-300}"

export XDG_RUNTIME_DIR="/run/user/$(id -u)"
export WAYLAND_DISPLAY="$WAYLAND_DISPLAY_NAME"

if ! command -v "$BROWSER_BIN" >/dev/null 2>&1; then
    if command -v chromium >/dev/null 2>&1; then
        BROWSER_BIN="chromium"
    else
        echo "Chromium introuvable."
        exit 1
    fi
fi

pkill swayidle >/dev/null 2>&1 || true

pkill -f chromium >/dev/null 2>&1 || true
sleep 2
pkill -9 -f chromium >/dev/null 2>&1 || true

rm -f "$PROFILE_DIR/SingletonLock" \
      "$PROFILE_DIR/SingletonSocket" \
      "$PROFILE_DIR/SingletonCookie"

mkdir -p "$PROFILE_DIR"

if command -v swayidle >/dev/null 2>&1 && command -v wlopm >/dev/null 2>&1; then
    nohup swayidle -w \
        timeout "$SCREEN_TIMEOUT" "wlopm --off $DISPLAY_OUTPUT" \
        resume "wlopm --on $DISPLAY_OUTPUT" \
        >/tmp/rpi3-meteo-swayidle.log 2>&1 &
else
    echo "Attention : swayidle ou wlopm introuvable, veille écran non activée."
fi

nohup "$BROWSER_BIN" \
    --kiosk \
    --app="$APP_URL" \
    --start-fullscreen \
    --no-first-run \
    --no-default-browser-check \
    --disable-infobars \
    --noerrdialogs \
    --disable-session-crashed-bubble \
    --password-store=basic \
    --user-data-dir="$PROFILE_DIR" \
    --check-for-update-interval=31536000 \
    --overscroll-history-navigation=0 \
    >/tmp/rpi3-meteo-kiosk.log 2>&1 &

echo "Mode kiosk lancé sur ${APP_URL}"
echo "Veille écran : ${SCREEN_TIMEOUT}s sur sortie ${DISPLAY_OUTPUT}"
