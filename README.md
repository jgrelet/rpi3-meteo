# rpi3-meteo

Application de visualisation meteo ciblee pour Raspberry Pi 3.

## Premiere base

- backend `FastAPI`
- stockage local `SQLite`
- ingestion prevue d'abord via `MQTT`
- affichage local compatible ecran tactile 7 pouces
- previsions a brancher ensuite via `Open-Meteo`

## Contrat MQTT

Le projet consomme les messages JSON publies par `weather_web_sensors` sur le topic `weather/sensors`.

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

Un message de test plus complet peut etre publie avec :

```bash
.venv/bin/python tools/publish_test_payload.py --host 127.0.0.1 --port 1883 --topic weather/sensors
```

## Configuration de l'application

Le fichier actif est [app/config.py](/home/jgrelet/git/Python/rpi3-meteo/app/config.py).
Un exemple de reference est disponible dans [app/config.example.py](/home/jgrelet/git/Python/rpi3-meteo/app/config.example.py).

Parametres a adapter en priorite :

- `APP_CONFIG["latitude"]` et `APP_CONFIG["longitude"]` pour les previsions
- `INGESTION["mqtt"]["broker"]` pour pointer vers le broker local du Pi ou un broker distant
- `INGESTION["mqtt"]["topic"]` pour rester aligne avec `weather_web_sensors`
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

## Mosquitto sur Raspberry Pi 3

Pour un systeme autonome, le plus propre est d'executer le broker MQTT directement sur le Pi3.

Configuration fournie :

- [mosquitto/mosquitto.conf](/home/jgrelet/git/Python/rpi3-meteo/mosquitto/mosquitto.conf)
- [scripts/install_mosquitto_rpi3.sh](/home/jgrelet/git/Python/rpi3-meteo/scripts/install_mosquitto_rpi3.sh)
- [scripts/deploy_test_rpi3.sh](/home/jgrelet/git/Python/rpi3-meteo/scripts/deploy_test_rpi3.sh)

Installation :

```bash
chmod +x scripts/install_mosquitto_rpi3.sh
./scripts/install_mosquitto_rpi3.sh
```

Ce script :

- installe `mosquitto` et `mosquitto-clients`
- copie la configuration dans `/etc/mosquitto/conf.d/rpi3-meteo.conf`
- active le service au demarrage
- redemarre le broker

Configuration minimale retenue pour le Pi3 :

```conf
listener 1883 0.0.0.0
allow_anonymous true
persistence true
persistence_location /var/lib/mosquitto/
```

Verification :

```bash
systemctl status mosquitto
mosquitto_sub -h 127.0.0.1 -p 1883 -t weather/sensors -v
```

Test rapide avec un faux message :

```bash
.venv/bin/python tools/publish_test_payload.py --host 127.0.0.1
```

Si tu veux durcir ensuite la config, la premiere evolution sera de remplacer `allow_anonymous true` par une authentification locale.

## Redeploiement de test sur le Pi3

Le script [scripts/deploy_test_rpi3.sh](/home/jgrelet/git/Python/rpi3-meteo/scripts/deploy_test_rpi3.sh) permet de remettre a jour et relancer l'application Docker sur le Raspberry Pi 3.

```bash
chmod +x scripts/deploy_test_rpi3.sh
./scripts/deploy_test_rpi3.sh
```

Par defaut, il travaille dans le depot parent du script, donc dans le clone courant. Tu peux aussi surcharger le chemin cible :

```bash
APP_DIR=/home/jgrelet/github/python/rpi3-meteo ./scripts/deploy_test_rpi3.sh
```

Puis il execute :

- `git pull --ff-only`
- `docker compose down`
- `docker compose up -d --build`
- `docker image prune -f`

## Installation Docker sur le Pi3

Le script [scripts/install_docker_rpi3.sh](/home/jgrelet/git/Python/rpi3-meteo/scripts/install_docker_rpi3.sh) installe Docker Engine depuis le depot officiel Docker pour Raspberry Pi OS 32-bit.

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
