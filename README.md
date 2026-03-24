# rpi3-meteo

Weather dashboard designed for a Raspberry Pi 3.

The project combines:

- a `FastAPI` backend
- local `SQLite` storage
- MQTT-based sensor ingestion
- a touchscreen-friendly local UI
- forecast pages backed by weather providers such as `Open-Meteo`

Forecasts are split across three dedicated pages to reduce scrolling on a small display:

- `/pages/forecast-now`
- `/pages/forecast-hours`
- `/pages/forecast-days`

## MQTT contract

The application consumes JSON messages published by `weather_web_sensors` on two topics:

- `weather/sensors/raw` for raw acquisitions
- `weather/sensors` for aggregated snapshots

Example payload:

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

If the payload includes both `gas_kohms` and `humidity_pct`, the app automatically enriches it with a local heuristic score:

- `air_quality_relative_pct`
- `air_quality_relative_label`
- `air_quality_relative_ready`
- `air_quality_relative_baseline_kohms`

This score is intentionally a local relative indicator derived from the BME680. It is not a standard AQI and not Bosch BSEC IAQ.

Publish test messages with:

```bash
.venv/bin/python tools/publish_test_payload.py --host 127.0.0.1 --export-mode raw
.venv/bin/python tools/publish_test_payload.py --host 127.0.0.1 --export-mode aggregated
```

To inspect both MQTT flows inside the Docker stack:

```bash
docker exec -it rpi3-meteo-mosquitto mosquitto_sub -h 127.0.0.1 -p 1883 -t 'weather/sensors/#' -v
```

## Configuration

Runtime configuration is loaded from environment variables in `.env`.

- Use `.env.generic` as the starting point for your local `.env`.
- `app/config.py` contains the active config loader and validation rules.
- `app/config.example.py` documents the full config structure in Python form.
- Invalid values in `.env` stop startup with an explicit error instead of being silently accepted.

Settings to review first:

- `RPI3_METEO_LOCATION_LABEL`, `RPI3_METEO_LATITUDE`, `RPI3_METEO_LONGITUDE`, `RPI3_METEO_ALTITUDE_M` for forecast location
- `RPI3_METEO_MQTT_BROKER` to point to the Raspberry Pi broker or a remote broker
- `RPI3_METEO_MQTT_RAW_TOPIC` and `RPI3_METEO_MQTT_AGGREGATED_TOPIC` to stay aligned with `weather_web_sensors`
- `RPI3_METEO_UI_REFRESH_SECONDS` for screen refresh cadence
- `RPI3_METEO_DB_PATH` if you want to move the SQLite database
- `RPI3_METEO_DB_ENABLED`, `RPI3_METEO_DB_STORE_RAW_MESSAGES`, and `RPI3_METEO_DB_STORE_SENSOR_READINGS` to control persistence
- `RPI3_METEO_AIR_QUALITY_ENABLED` and the `RPI3_METEO_AIR_QUALITY_*` variables to tune or disable the relative air quality score

## Local development

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

The app is then available at `http://127.0.0.1:8000`.

Example without Docker, using explicit environment variables:

```bash
export RPI3_METEO_LOCATION_LABEL="Keronvel, 29810 Ploumoguer"
export RPI3_METEO_LATITUDE=48.4018424
export RPI3_METEO_LONGITUDE=-4.6927117
export RPI3_METEO_ALTITUDE_M=65
export RPI3_METEO_MQTT_BROKER=127.0.0.1
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Docker startup

```bash
cp .env.generic .env
docker compose up --build
```

## Docker on WSL and Raspberry Pi 3

Recommended workflow:

- develop and test on WSL with Docker Desktop
- perform final validation on the Raspberry Pi 3

The `Dockerfile` uses `python:3.11-slim-bookworm`, which is more predictable than an implicit Debian tag and is also published for `arm32v7` in the official Python Docker images.

Useful checks:

```bash
docker compose up --build
```

From WSL, you can also validate a Pi 3 target build without deploying to the device:

```bash
docker buildx build --platform linux/arm/v7 -t rpi3-meteo:test .
```

That build check is useful, but it does not replace a real Pi 3 validation for memory usage, performance, and full startup behavior.

## Full Docker stack

The deployment target is fully containerized:

- `mosquitto` runs in `docker compose`
- the web app runs in `docker compose`
- MQTT persistence uses Docker volumes
- SQLite persistence uses the repository `./data` directory

Provided files:

- `docker-compose.yml`
- `mosquitto/mosquitto.conf`
- `scripts/deploy_test_rpi3.sh`
- `.env.generic`

Runtime notes:

- the Pico publishes to the Pi IP on port `1883`
- that port is exposed by the `mosquitto` container
- the `web` container connects to the broker through the Docker service name `mosquitto`
- SQLite data is stored in `./data/weather.db` on the host
- Mosquitto data is stored in the `mosquitto_data` and `mosquitto_log` volumes
- personal and location-specific values are read from `.env`

Recommended preparation:

```bash
cp .env.generic .env
```

Then edit `.env` and set at least:

- `RPI3_METEO_LOCATION_LABEL`
- `RPI3_METEO_LATITUDE`
- `RPI3_METEO_LONGITUDE`
- `RPI3_METEO_ALTITUDE_M`

Quick test with sample messages:

```bash
.venv/bin/python tools/publish_test_payload.py --host 127.0.0.1 --export-mode raw
.venv/bin/python tools/publish_test_payload.py --host 127.0.0.1 --export-mode aggregated
```

To inspect messages handled by the containerized broker:

```bash
docker exec -it rpi3-meteo-mosquitto mosquitto_sub -h 127.0.0.1 -p 1883 -t 'weather/sensors/#' -v
```

## Test redeploy on Raspberry Pi 3

The `scripts/deploy_test_rpi3.sh` script updates and restarts the full Docker stack on the Raspberry Pi 3.

```bash
chmod +x scripts/deploy_test_rpi3.sh
./scripts/deploy_test_rpi3.sh
```

By default, it works from the repository that contains the script. You can override the target path:

```bash
APP_DIR=/home/user/github/python/rpi3-meteo ./scripts/deploy_test_rpi3.sh
```

It runs:

- `git pull --ff-only`
- `docker compose down`
- `docker compose up -d --build`
- `docker image prune -f`

## Install Docker on Raspberry Pi 3

The `scripts/install_docker_rpi3.sh` script installs Docker Engine from the official Docker repository for 32-bit Raspberry Pi OS.

```bash
chmod +x scripts/install_docker_rpi3.sh
./scripts/install_docker_rpi3.sh
```

The script:

- removes unofficial Docker packages that may conflict
- adds the official Docker `debian` repository for Pi 3 `armhf`
- looks for a compatible `28.x` `docker-ce` version
- installs `docker-ce`, `docker-ce-cli`, `containerd.io`, `docker-buildx-plugin`, and `docker-compose-plugin`
- enables the Docker service
- runs `hello-world`
- adds the current user to the `docker` group

Important notes:

- Docker documentation states that Docker Engine v28 is the latest major version supported on Raspberry Pi OS 32-bit `armhf`
- after the user is added to the `docker` group, a logout/login cycle is required before using `docker` without `sudo`

Official references:

- https://docs.docker.com/engine/install/raspberry-pi-os/
- https://docs.docker.com/engine/install/linux-postinstall/

## Kiosk mode

The repository includes a reversible kiosk mode for Raspberry Pi OS with Chromium.

Scripts:

- `scripts/start_kiosk.sh`
- `scripts/stop_kiosk.sh`
- `scripts/install_kiosk_shortcuts.sh`

Manual start:

```bash
chmod +x scripts/start_kiosk.sh scripts/stop_kiosk.sh
./scripts/start_kiosk.sh
```

Manual stop:

```bash
./scripts/stop_kiosk.sh
```

Recover the desktop:

- `Alt+F4` closes the kiosk window
- `Ctrl+Alt+T` opens a terminal
- `stop_kiosk.sh` only closes the Chromium instance started for `http://127.0.0.1:8000`

Provided desktop launchers:

- `desktop/rpi3-meteo-kiosk.desktop`
- `desktop/rpi3-meteo-kiosk-stop.desktop`
- `desktop/rpi3-meteo-kiosk-autostart.desktop`

Recommended installation on the Pi:

```bash
chmod +x scripts/start_kiosk.sh scripts/stop_kiosk.sh scripts/install_kiosk_shortcuts.sh
./scripts/install_kiosk_shortcuts.sh
```

The script generates the `.desktop` files automatically with the real repository path on the Pi.

## Quick verification

A simple Python syntax check is to compile all modules without executing them:

```bash
python3 -m compileall app
```

This is a fast way to catch syntax errors before integration or redeployment.
