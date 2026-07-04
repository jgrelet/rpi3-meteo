#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="${ENV_FILE:-${APP_DIR}/.env}"
WEB_PORT="8000"
SCREEN_BLANK_SECONDS="60"
STARTUP_WAIT_SECONDS="60"

env_value() {
    local key="$1"
    local value
    value="$(grep -E "^${key}=" "$ENV_FILE" 2>/dev/null | tail -n 1 | cut -d '=' -f 2- || true)"
    value="${value%\"}"
    value="${value#\"}"
    value="${value%\'}"
    value="${value#\'}"
    echo "$value"
}

env_value_or_default() {
    local key="$1"
    local default_value="$2"
    local value
    value="$(env_value "$key")"
    if [ -z "$value" ]; then
        value="$default_value"
    fi
    echo "$value"
}

require_seconds() {
    local name="$1"
    local value="$2"
    if ! [[ "$value" =~ ^[0-9]+$ ]]; then
        echo "$name doit etre un nombre de secondes, valeur recue: $value"
        exit 1
    fi
}

if [ -f "$ENV_FILE" ]; then
    WEB_PORT="$(env_value_or_default RPI3_METEO_WEB_PORT "$WEB_PORT")"
    SCREEN_BLANK_SECONDS="$(env_value_or_default RPI3_METEO_KIOSK_SCREEN_BLANK_SECONDS "$SCREEN_BLANK_SECONDS")"
    STARTUP_WAIT_SECONDS="$(env_value_or_default RPI3_METEO_KIOSK_STARTUP_WAIT_SECONDS "$STARTUP_WAIT_SECONDS")"
fi

require_seconds RPI3_METEO_KIOSK_SCREEN_BLANK_SECONDS "$SCREEN_BLANK_SECONDS"
require_seconds RPI3_METEO_KIOSK_STARTUP_WAIT_SECONDS "$STARTUP_WAIT_SECONDS"

APP_URL="${APP_URL:-http://127.0.0.1:${WEB_PORT}}"
BROWSER_BIN="${BROWSER_BIN:-chromium-browser}"
PROFILE_DIR="${PROFILE_DIR:-${HOME}/.config/rpi-meteo-kiosk}"
WAYLAND_DISPLAY_NAME="${WAYLAND_DISPLAY_NAME:-wayland-0}"
DISABLE_GPU="${DISABLE_GPU:-false}"

export XDG_RUNTIME_DIR="/run/user/$(id -u)"
export WAYLAND_DISPLAY="$WAYLAND_DISPLAY_NAME"
export NO_AT_BRIDGE=1
export GTK_A11Y=none

wait_for_graphical_session() {
    local deadline=$((SECONDS + STARTUP_WAIT_SECONDS))
    while [ "$SECONDS" -le "$deadline" ]; do
        if [ -S "${XDG_RUNTIME_DIR}/${WAYLAND_DISPLAY}" ] || [ -n "${DISPLAY:-}" ]; then
            return 0
        fi
        sleep 1
    done

    echo "Session graphique non detectee apres ${STARTUP_WAIT_SECONDS}s."
    echo "XDG_RUNTIME_DIR=${XDG_RUNTIME_DIR}, WAYLAND_DISPLAY=${WAYLAND_DISPLAY}, DISPLAY=${DISPLAY:-}"
    exit 1
}

wait_for_app() {
    local deadline=$((SECONDS + STARTUP_WAIT_SECONDS))
    while [ "$SECONDS" -le "$deadline" ]; do
        if command -v curl >/dev/null 2>&1; then
            curl --silent --fail --max-time 2 "$APP_URL" >/dev/null 2>&1 && return 0
        elif command -v wget >/dev/null 2>&1; then
            wget --quiet --spider --timeout=2 "$APP_URL" >/dev/null 2>&1 && return 0
        else
            echo "curl/wget introuvable: impossible de verifier ${APP_URL}, lancement sans attente HTTP."
            return 0
        fi
        sleep 1
    done

    echo "Application non joignable apres ${STARTUP_WAIT_SECONDS}s: ${APP_URL}"
    exit 1
}

configure_screen_blank() {
    if command -v xset >/dev/null 2>&1 && [ -n "${DISPLAY:-}" ]; then
        if [ "$SCREEN_BLANK_SECONDS" = "0" ]; then
            xset s off s noblank -dpms >/dev/null 2>&1 || true
            echo "Veille ecran desactivee via xset."
        else
            xset s "$SCREEN_BLANK_SECONDS" "$SCREEN_BLANK_SECONDS" +dpms >/dev/null 2>&1 || true
            xset dpms "$SCREEN_BLANK_SECONDS" "$SCREEN_BLANK_SECONDS" "$SCREEN_BLANK_SECONDS" >/dev/null 2>&1 || true
            echo "Veille ecran configuree a ${SCREEN_BLANK_SECONDS}s via xset."
        fi
    elif [ "$SCREEN_BLANK_SECONDS" != "0" ]; then
        echo "xset/DISPLAY indisponible: la veille ecran doit etre geree par le compositeur Wayland."
    fi
}

wait_for_graphical_session
wait_for_app

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

configure_screen_blank

CHROMIUM_FLAGS=(
    --ozone-platform=wayland
    --kiosk
    --app="$APP_URL"
    --start-fullscreen
    --no-first-run
    --no-default-browser-check
    --disable-infobars
    --noerrdialogs
    --disable-session-crashed-bubble
    --disable-extensions
    --disable-component-update
    --disable-background-networking
    --disable-sync
    --disable-translate
    --disable-gcm
    --disable-push-messaging
    --disable-notifications
    --disable-domain-reliability
    --disable-client-side-phishing-detection
    --metrics-recording-only
    --disable-default-apps
    --disable-features=MediaRouter,OptimizationHints,AutofillServerCommunication,Translate,AccessibilityObjectModel,PushMessaging,NotificationTriggers
    --disable-renderer-accessibility
    --disable-dev-shm-usage
    --password-store=basic
    --user-data-dir="$PROFILE_DIR"
    --overscroll-history-navigation=0
)

if [ "$DISABLE_GPU" = "true" ]; then
    CHROMIUM_FLAGS+=(
        --disable-gpu
        --disable-gpu-compositing
        --disable-accelerated-2d-canvas
        --disable-accelerated-video-decode
    )
fi

nohup "$BROWSER_BIN" "${CHROMIUM_FLAGS[@]}" >/tmp/rpi-meteo-kiosk.log 2>&1 &

echo "Mode kiosk Chromium lancé sur ${APP_URL}"
