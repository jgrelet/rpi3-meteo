#!/bin/bash
set -euo pipefail

APP_URL="${APP_URL:-http://127.0.0.1:8000}"
BROWSER_BIN="${BROWSER_BIN:-chromium-browser}"

if ! command -v "$BROWSER_BIN" >/dev/null 2>&1; then
    if command -v chromium >/dev/null 2>&1; then
        BROWSER_BIN="chromium"
    else
        echo "Chromium introuvable."
        exit 1
    fi
fi

pkill -f "chromium.*${APP_URL}" >/dev/null 2>&1 || true

nohup "$BROWSER_BIN" \
    --kiosk \
    --app="$APP_URL" \
    --start-fullscreen \
    --disable-infobars \
    --noerrdialogs \
    --disable-session-crashed-bubble \
    --check-for-update-interval=31536000 \
    --overscroll-history-navigation=0 \
    >/tmp/rpi3-meteo-kiosk.log 2>&1 &

echo "Mode kiosk lance sur ${APP_URL}"
