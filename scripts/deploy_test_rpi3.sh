#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_APP_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
APP_DIR="${APP_DIR:-$DEFAULT_APP_DIR}"

if [ ! -d "$APP_DIR/.git" ]; then
    echo "Depot introuvable: $APP_DIR"
    exit 1
fi

cd "$APP_DIR"

echo "[1/4] Mise a jour du depot"
git pull --ff-only

echo "[2/4] Arret des conteneurs existants"
docker compose down

echo "[3/4] Reconstruction et redemarrage"
docker compose up -d --build

echo "[4/4] Nettoyage des images inutilisees"
docker image prune -f

echo "Deploiement termine."
