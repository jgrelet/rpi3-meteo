#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_APP_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
APP_DIR="${APP_DIR:-$DEFAULT_APP_DIR}"
ENV_FILE="${ENV_FILE:-.env}"
DETACH="${DETACH:-true}"

if [ ! -d "$APP_DIR/.git" ]; then
    echo "Depot introuvable: $APP_DIR"
    exit 1
fi

cd "$APP_DIR"

if [ ! -f "$ENV_FILE" ]; then
    echo "Fichier d'environnement introuvable: $APP_DIR/$ENV_FILE"
    echo "Copie d'abord .env.generic vers .env puis adapte les variables necessaires."
    exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
    echo "Docker est introuvable dans le PATH."
    exit 1
fi

compose() {
    docker compose "$@"
}

show_help() {
    cat <<'EOF'
Usage: ./scripts/deploy_dev.sh [command]

Commands:
  up       Arrete, reconstruit et redemarre la stack Docker locale (defaut)
  down     Arrete la stack locale
  restart  Redemarre la stack sans reconstruction
  logs     Affiche les logs des services
  ps       Affiche l'etat des conteneurs
  help     Affiche cette aide

Variables optionnelles:
  APP_DIR=/chemin/vers/le/depot
  ENV_FILE=.env
  DETACH=true|false
EOF
}

command_name="${1:-up}"

case "$command_name" in
    up)
        echo "[1/5] Verification du fichier d'environnement"
        echo "Utilisation de $APP_DIR/$ENV_FILE"

        echo "[2/5] Arret de la stack existante"
        compose down

        echo "[3/5] Reconstruction des images"
        compose build

        echo "[4/5] Demarrage des services"
        if [ "$DETACH" = "true" ]; then
            compose up -d
        else
            compose up
        fi

        echo "[5/5] Etat des services"
        compose ps

        echo
        echo "URLs utiles:"
        web_port="$(grep -E '^RPI3_METEO_WEB_PORT=' "$ENV_FILE" 2>/dev/null | tail -n 1 | cut -d '=' -f 2-)"
        if [ -z "$web_port" ]; then
            web_port="8000"
        fi
        echo "  Application: http://127.0.0.1:$web_port"
        echo "  PostgreSQL : 127.0.0.1:5432"
        echo
        echo "Commandes utiles:"
        echo "  docker exec -it rpi3-meteo-postgres psql -U \"\$RPI3_METEO_DB_USER\" -d \"\$RPI3_METEO_DB_NAME\""
        echo "  docker exec -it rpi3-meteo-mosquitto mosquitto_sub -h 127.0.0.1 -p 1883 -t 'weather/sensors/#' -v"
        ;;
    down)
        compose down
        ;;
    restart)
        compose restart
        compose ps
        ;;
    logs)
        compose logs -f
        ;;
    ps)
        compose ps
        ;;
    help|-h|--help)
        show_help
        ;;
    *)
        echo "Commande inconnue: $command_name"
        echo
        show_help
        exit 1
        ;;
esac
