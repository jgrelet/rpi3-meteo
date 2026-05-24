#!/bin/bash
set -euo pipefail

APP_URL="${APP_URL:-http://127.0.0.1:8000}"
BROWSER_BIN="${BROWSER_BIN:-chromium-browser}"
PROFILE_DIR="${PROFILE_DIR:-${HOME}/.config/rpi3-meteo-kiosk}"
WAYLAND_DISPLAY_NAME="${WAYLAND_DISPLAY_NAME:-wayland-0}"

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

pkill -9 -f chromium >/dev/null 2>&1 || true
sleep 1

mkdir -p "$PROFILE_DIR"
rm -f "$PROFILE_DIR"/Singleton*

nohup "$BROWSER_BIN" \
    --ozone-platform=wayland \
    --kiosk \
    --app="$APP_URL" \
    --start-fullscreen \
    --no-first-run \
    --no-default-browser-check \
    --disable-infobars \
    --noerrdialogs \
    --disable-session-crashed-bubble \
    --disable-extensions \
    --disable-component-update \
    --disable-background-networking \
    --disable-sync \
    --disable-translate \
    --disable-gcm \
    --disable-push-messaging \
    --disable-notifications \
    --disable-domain-reliability \
    --disable-client-side-phishing-detection \
    --metrics-recording-only \
    --disable-default-apps \
    --disable-features=MediaRouter,OptimizationHints,AutofillServerCommunication,Translate,AccessibilityObjectModel,PushMessaging,NotificationTriggers \
    --disable-renderer-accessibility \
    --disable-gpu \
    --disable-gpu-compositing \
    --disable-accelerated-2d-canvas \
    --disable-accelerated-video-decode \
    --disable-dev-shm-usage \
    --password-store=basic \
    --user-data-dir="$PROFILE_DIR" \
    --overscroll-history-navigation=0 \
    >/tmp/rpi3-meteo-kiosk.log 2>&1 &

echo "Mode kiosk Chromium lancé sur ${APP_URL}"
