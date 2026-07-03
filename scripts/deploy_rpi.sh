#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_APP_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
APP_DIR="${APP_DIR:-$DEFAULT_APP_DIR}"
ENV_FILE="${ENV_FILE:-.env}"
DETACH="${DETACH:-true}"
PRUNE="${PRUNE:-false}"

if [ ! -d "$APP_DIR/.git" ]; then
    echo "Depot introuvable: $APP_DIR"
    exit 1
fi

cd "$APP_DIR"

compose() {
    docker compose "$@"
}

require_env_file() {
    if [ ! -f "$ENV_FILE" ]; then
        echo "Fichier d'environnement introuvable: $APP_DIR/$ENV_FILE"
        echo "Copie d'abord .env.generic vers .env puis adapte les variables necessaires."
        exit 1
    fi
}

env_value() {
    local key="$1"
    grep -E "^${key}=" "$ENV_FILE" 2>/dev/null | tail -n 1 | cut -d '=' -f 2-
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

require_numeric() {
    local name="$1"
    local value="$2"
    if ! [[ "$value" =~ ^[0-9]+$ ]]; then
        echo "$name doit etre numerique, valeur recue: $value"
        exit 1
    fi
}

validate_docker_env() {
    local bind_host
    local exposed_port
    bind_host="$(env_value RPI3_METEO_HOST)"
    exposed_port="$(env_value RPI3_METEO_WEB_PORT)"
    if [ -z "$exposed_port" ]; then
        exposed_port="8000"
    fi

    if [ -n "$bind_host" ] && [ "$bind_host" != "0.0.0.0" ]; then
        cat <<EOF
Configuration Docker invalide dans $APP_DIR/$ENV_FILE:
  RPI3_METEO_HOST=$bind_host

Dans Docker, le serveur web doit ecouter sur 0.0.0.0 a l'interieur du conteneur.
Mets plutot:
  RPI3_METEO_HOST=0.0.0.0

L'adresse IP du Raspberry Pi sert uniquement depuis le navigateur d'une autre machine,
par exemple http://<raspberry-pi-ip>:${exposed_port}.
EOF
        exit 1
    fi
}

prepare_data_dir() {
    local container_uid
    local container_gid
    container_uid="$(env_value_or_default RPI3_METEO_CONTAINER_UID 1000)"
    container_gid="$(env_value_or_default RPI3_METEO_CONTAINER_GID 1000)"
    require_numeric RPI3_METEO_CONTAINER_UID "$container_uid"
    require_numeric RPI3_METEO_CONTAINER_GID "$container_gid"

    mkdir -p "$APP_DIR/data"

    if ! chown -R "${container_uid}:${container_gid}" "$APP_DIR/data" 2>/dev/null; then
        if command -v sudo >/dev/null 2>&1; then
            echo "Correction des droits de $APP_DIR/data avec sudo pour ${container_uid}:${container_gid}."
            sudo chown -R "${container_uid}:${container_gid}" "$APP_DIR/data"
        else
            cat <<EOF
Impossible de changer le proprietaire de $APP_DIR/data.
Execute manuellement:
  sudo chown -R ${container_uid}:${container_gid} "$APP_DIR/data"
EOF
            exit 1
        fi
    fi

    chmod -R u+rwX,g+rwX,o-rwx "$APP_DIR/data"
}

require_docker() {
    if ! command -v docker >/dev/null 2>&1; then
        echo "Docker est introuvable dans le PATH."
        exit 1
    fi

    if ! docker compose version >/dev/null 2>&1; then
        echo "Le plugin Docker Compose est introuvable ou Docker n'est pas accessible."
        echo "Verifie l'installation Docker et les droits du groupe docker."
        exit 1
    fi
}

remove_legacy_containers() {
    local legacy_containers=(
        rpi3-meteo-web
        rpi3-meteo-postgres
        rpi3-meteo-mosquitto
    )
    local existing=()
    local name

    for name in "${legacy_containers[@]}"; do
        if docker container inspect "$name" >/dev/null 2>&1; then
            existing+=("$name")
        fi
    done

    if [ "${#existing[@]}" -gt 0 ]; then
        echo "Anciens conteneurs detectes: ${existing[*]}"
        echo "Suppression des anciens conteneurs pour eviter les conflits de ports."
        docker rm -f "${existing[@]}"
    fi
}

web_port() {
    local port
    port="$(env_value RPI3_METEO_WEB_PORT)"
    if [ -z "$port" ]; then
        port="8000"
    fi
    echo "$port"
}

show_help() {
    cat <<'EOF'
Usage: ./scripts/deploy_rpi.sh [command]

Commands:
  up       Arrete, reconstruit et redemarre la stack Docker locale (defaut)
  pull-up  Met a jour le depot avec git pull --ff-only puis lance up
  down     Arrete la stack locale
  restart  Redemarre la stack sans reconstruction
  logs     Affiche les logs des services
  ps       Affiche l'etat des conteneurs
  prune    Supprime les images Docker inutilisees
  help     Affiche cette aide

Variables optionnelles:
  APP_DIR=/chemin/vers/le/depot
  ENV_FILE=.env
  DETACH=true|false
  PRUNE=true|false

Notes:
  - up ne fait pas de git pull: c'est le mode adapte au developpement direct
    sur Raspberry Pi via Remote-SSH.
  - pull-up garde l'ancien flux de deploiement depuis Git quand c'est utile.
EOF
}

run_up() {
    require_env_file
    validate_docker_env
    require_docker

    echo "[1/6] Verification du fichier d'environnement"
    echo "Utilisation de $APP_DIR/$ENV_FILE"

    echo "[2/6] Preparation du volume data"
    prepare_data_dir

    echo "[3/6] Arret de la stack existante"
    remove_legacy_containers
    compose down

    echo "[4/6] Reconstruction des images"
    compose build

    echo "[5/6] Demarrage des services"
    if [ "$DETACH" = "true" ]; then
        compose up -d
    else
        compose up
    fi

    if [ "$PRUNE" = "true" ]; then
        echo "[6/7] Nettoyage des images inutilisees"
        docker image prune -f
        echo "[7/7] Etat des services"
    else
        echo "[6/6] Etat des services"
    fi
    compose ps

    echo
    echo "URLs utiles:"
    echo "  Application: http://127.0.0.1:$(web_port)"
    echo "  PostgreSQL : 127.0.0.1:5432"
    echo
    echo "Commandes utiles:"
    echo "  docker exec -it rpi-meteo-postgres psql -U \"\$RPI3_METEO_DB_USER\" -d \"\$RPI3_METEO_DB_NAME\""
    echo "  docker exec -it rpi-meteo-mosquitto mosquitto_sub -h 127.0.0.1 -p 1883 -t 'weather/sensors/#' -v"
}

command_name="${1:-up}"

case "$command_name" in
    up)
        run_up
        ;;
    pull-up)
        echo "[0/6] Mise a jour du depot"
        git pull --ff-only
        run_up
        ;;
    down)
        require_docker
        compose down
        ;;
    restart)
        require_docker
        compose restart
        compose ps
        ;;
    logs)
        require_docker
        compose logs -f
        ;;
    ps)
        require_docker
        compose ps
        ;;
    prune)
        require_docker
        docker image prune -f
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
