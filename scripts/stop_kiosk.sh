#!/bin/bash
set -euo pipefail

APP_URL="${APP_URL:-http://127.0.0.1:8000}"

pkill -f "chromium.*${APP_URL}" >/dev/null 2>&1 || true
pkill -f "chromium-browser.*${APP_URL}" >/dev/null 2>&1 || true

echo "Mode kiosk arrete."
