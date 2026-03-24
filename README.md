# rpi3-meteo

Application de visualisation meteo ciblee pour Raspberry Pi 3.

## Premiere base

- backend `FastAPI`
- stockage local `SQLite`
- ingestion prevue d'abord via `MQTT`
- affichage local compatible ecran tactile 7 pouces
- previsions a brancher ensuite via `Open-Meteo`

Les previsions sont exposees sur trois pages dediees pour limiter le scrolling sur petit ecran :

- `/pages/forecast-now`
- `/pages/forecast-hours`
- `/pages/forecast-days`

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

Si le payload contient `gas_kohms` et `humidity_pct`, l'application enrichit automatiquement le message avec un score heuristique local :

- `air_quality_relative_pct`
- `air_quality_relative_label`
- `air_quality_relative_ready`
- `air_quality_relative_baseline_kohms`

Ce score est volontairement un indicateur relatif local base sur le BME680. Ce n'est ni un AQI standard, ni un IAQ Bosch BSEC.

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
Les variables d'instance et de localisation doivent etre definies dans un fichier `.env` local non versionne, a partir de `.env.generic`.

Parametres a adapter en priorite :

- `APP_CONFIG["latitude"]` et `APP_CONFIG["longitude"]` pour les previsions
- `INGESTION["mqtt"]["broker"]` pour pointer vers le broker local du Pi ou un broker distant
- `INGESTION["mqtt"]["raw_topic"]` et `INGESTION["mqtt"]["aggregated_topic"]` pour rester aligne avec `weather_web_sensors`
- `UI["refresh_seconds"]` selon la frequence voulue sur l'ecran tactile
- `DATABASE["path"]` si tu veux deplacer la base SQLite
- `DATABASE["enabled"]`, `DATABASE["store_raw_messages"]` et `DATABASE["store_sensor_readings"]` pour piloter l'enregistrement progressif des acquisitions
- `AIR_QUALITY["enabled"]` et les variables `RPI3_METEO_AIR_QUALITY_*` si tu veux ajuster ou desactiver le score relatif

## Demarrage local

```bash
cp .env.generic .env
python3 -m venv .venv
source .venv/bin/activate
set -a
source .env
set +a
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Application disponible sur `http://127.0.0.1:8000`.

Exemple d'utilisation des variables d'environnement hors Docker :

```bash
export RPI3_METEO_LOCATION_LABEL="Keronvel, 29810 Ploumoguer"
export RPI3_METEO_LATITUDE=48.4018424
export RPI3_METEO_LONGITUDE=-4.6927117
export RPI3_METEO_ALTITUDE_M=65
export RPI3_METEO_MQTT_BROKER=127.0.0.1
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Demarrage Docker

```bash
cp .env.generic .env
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
- la persistance MQTT est geree par des volumes Docker, et SQLite par le dossier `./data` du depot

Configuration fournie :

- `docker-compose.yml`
- `mosquitto/mosquitto.conf`
- `scripts/deploy_test_rpi3.sh`
- `.env.generic`

Notes de fonctionnement :

- le Pico publie sur l'IP du Pi, port `1883`
- ce port est expose par le conteneur `mosquitto`
- le conteneur `web` se connecte au broker via le nom de service Docker `mosquitto`
- les donnees SQLite sont conservees dans `./data/weather.db` sur l'hote
- les donnees Mosquitto sont conservees dans les volumes `mosquitto_data` et `mosquitto_log`
- les variables personnelles et de localisation sont lues depuis `.env`

Preparation recommandee :

```bash
cp .env.generic .env
```

Puis editer `.env` pour renseigner au minimum :

- `RPI3_METEO_LOCATION_LABEL`
- `RPI3_METEO_LATITUDE`
- `RPI3_METEO_LONGITUDE`
- `RPI3_METEO_ALTITUDE_M`

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

## Mode kiosque

Le depot fournit un mode kiosque reversible pour Raspberry Pi OS avec Chromium.

Scripts :

- `scripts/start_kiosk.sh`
- `scripts/stop_kiosk.sh`
- `scripts/install_kiosk_shortcuts.sh`

Lancement manuel :

```bash
chmod +x scripts/start_kiosk.sh scripts/stop_kiosk.sh
./scripts/start_kiosk.sh
```

Arret manuel :

```bash
./scripts/stop_kiosk.sh
```

Reprendre la main :

- `Alt+F4` ferme la fenetre kiosque
- `Ctrl+Alt+T` ouvre un terminal
- le script `stop_kiosk.sh` ferme uniquement le Chromium lance pour `http://127.0.0.1:8000`

Lanceurs graphiques fournis :

- `desktop/rpi3-meteo-kiosk.desktop`
- `desktop/rpi3-meteo-kiosk-stop.desktop`
- `desktop/rpi3-meteo-kiosk-autostart.desktop`

Installation conseillee sur le Pi :

```bash
chmod +x scripts/start_kiosk.sh scripts/stop_kiosk.sh scripts/install_kiosk_shortcuts.sh
./scripts/install_kiosk_shortcuts.sh
```

Le script genere automatiquement les fichiers `.desktop` avec le chemin reel du depot sur le Pi.

## Verification rapide

Une verification simple de syntaxe Python consiste a compiler tous les modules sans les executer :

```bash
python3 -m compileall app
```

Cette commande est utile pour detecter rapidement une erreur de syntaxe avant integration ou redeploiement.
