# rpi3-meteo

Application de visualisation meteo ciblee pour Raspberry Pi 3.

## Premiere base

- backend `FastAPI`
- stockage local `SQLite`
- ingestion prevue d'abord via `MQTT`
- affichage local compatible ecran tactile 7 pouces
- previsions a brancher ensuite via `Open-Meteo`

## Contrat MQTT

Le projet consomme les messages JSON publies par `weather_web_sensors` sur deux topics :

- `weather/sensors/raw` pour les acquisitions brutes
- `weather/sensors` pour les snapshots agreges

Exemple de payload :

```json
{
  "timestamp": 1771428856,
  "temperature_c": 20.11,
  "humidity_pct": 59.54,
  "pressure_hpa": 978.34,
  "wind_speed_kmh": 0.0,
  "wind_dir_cardinal": "W",
  "rain_mm_total": 0.0
}
```

Des messages de test peuvent etre publies avec :

```bash
.venv/bin/python tools/publish_test_payload.py --host 127.0.0.1 --export-mode raw
.venv/bin/python tools/publish_test_payload.py --host 127.0.0.1 --export-mode aggregated
```

Pour observer les deux flux MQTT dans la stack Docker :

```bash
docker exec -it rpi3-meteo-mosquitto mosquitto_sub -h 127.0.0.1 -p 1883 -t 'weather/sensors/#' -v
```

## Configuration de l'application

Le fichier actif est `app/config.py`.
Un exemple de reference est disponible dans `app/config.example.py`.

Parametres a adapter en priorite :

- `APP_CONFIG["latitude"]` et `APP_CONFIG["longitude"]` pour les previsions
- `INGESTION["mqtt"]["broker"]` pour pointer vers le broker local du Pi ou un broker distant
- `INGESTION["mqtt"]["raw_topic"]` et `INGESTION["mqtt"]["aggregated_topic"]` pour rester aligne avec `weather_web_sensors`
- `UI["refresh_seconds"]` selon la frequence voulue sur l'ecran tactile
- `DATABASE["path"]` si tu veux deplacer la base SQLite

## Demarrage local

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Application disponible sur `http://127.0.0.1:8000`.

## Demarrage Docker

```bash
docker compose up --build
```

## Docker WSL et Pi3

Le flux recommande est :

- developpement et tests sous WSL avec Docker Desktop
- validation finale sur Raspberry Pi 3

Le `Dockerfile` utilise `python:3.11-slim-bookworm`, ce qui reste plus stable qu'un tag Debian implicite et est publie aussi pour `arm32v7` dans l'image officielle Python Docker Hub.

Tests utiles :

```bash
docker compose up --build
```

Depuis WSL, pour verifier aussi un build cible Pi3 sans deployer sur le Pi :

```bash
docker buildx build --platform linux/arm/v7 -t rpi3-meteo:test .
```

Ce test de build est utile, mais il ne remplace pas une validation reelle sur le Pi3 pour la memoire, les performances et le demarrage complet.

## Stack Docker complete

La cible de deploiement est maintenant entierement conteneurisee :

- `mosquitto` tourne dans `docker compose`
- l'application web tourne dans `docker compose`
- la persistance MQTT et SQLite est geree par des volumes Docker

Configuration fournie :

- `docker-compose.yml`
- `mosquitto/mosquitto.conf`
- `scripts/deploy_test_rpi3.sh`

Notes de fonctionnement :

- le Pico publie sur l'IP du Pi, port `1883`
- ce port est expose par le conteneur `mosquitto`
- le conteneur `web` se connecte au broker via le nom de service Docker `mosquitto`
- les donnees SQLite sont conservees dans le volume Docker `sqlite_data`
- les donnees Mosquitto sont conservees dans les volumes `mosquitto_data` et `mosquitto_log`

Test rapide avec un faux message :

```bash
.venv/bin/python tools/publish_test_payload.py --host 127.0.0.1 --export-mode raw
.venv/bin/python tools/publish_test_payload.py --host 127.0.0.1 --export-mode aggregated
```

Observation des messages MQTT recuperees par le broker conteneurise :

```bash
docker exec -it rpi3-meteo-mosquitto mosquitto_sub -h 127.0.0.1 -p 1883 -t 'weather/sensors/#' -v
```

## Redeploiement de test sur le Pi3

Le script `scripts/deploy_test_rpi3.sh` permet de remettre a jour et relancer toute la stack Docker sur le Raspberry Pi 3.

```bash
chmod +x scripts/deploy_test_rpi3.sh
./scripts/deploy_test_rpi3.sh
```

Par defaut, il travaille dans le depot parent du script, donc dans le clone courant. Tu peux aussi surcharger le chemin cible :

```bash
APP_DIR=/home/user/github/python/rpi3-meteo ./scripts/deploy_test_rpi3.sh
```

Puis il execute :

- `git pull --ff-only`
- `docker compose down`
- `docker compose up -d --build`
- `docker image prune -f`

## Installation Docker sur le Pi3

Le script `scripts/install_docker_rpi3.sh` installe Docker Engine depuis le depot officiel Docker pour Raspberry Pi OS 32-bit.

```bash
chmod +x scripts/install_docker_rpi3.sh
./scripts/install_docker_rpi3.sh
```

Le script :

- supprime les paquets Docker non officiels qui peuvent entrer en conflit
- ajoute le depot officiel Docker `debian` adapte au Pi3 en `armhf`
- cherche automatiquement une version `28.x` de `docker-ce`
- installe `docker-ce`, `docker-ce-cli`, `containerd.io`, `docker-buildx-plugin` et `docker-compose-plugin`
- active le service Docker
- execute `hello-world`
- ajoute l'utilisateur courant au groupe `docker`

Notes importantes :

- Docker Docs indique que `Docker Engine v28` est la derniere grande version supportee sur Raspberry Pi OS 32-bit `armhf`
- apres ajout au groupe `docker`, il faut se deconnecter/reconnecter avant d'utiliser `docker` sans `sudo`

Sources officielles :

- https://docs.docker.com/engine/install/raspberry-pi-os/
- https://docs.docker.com/engine/install/linux-postinstall/
