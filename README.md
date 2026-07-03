# rpi-meteo

Weather dashboard designed for a Raspberry Pi.

The project combines:

- a `FastAPI` backend
- `PostgreSQL` storage
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
docker exec -it rpi-meteo-mosquitto mosquitto_sub -h 127.0.0.1 -p 1883 -t 'weather/sensors/#' -v
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
- `RPI3_METEO_DB_HOST`, `RPI3_METEO_DB_PORT`, `RPI3_METEO_DB_NAME`, `RPI3_METEO_DB_USER`, `RPI3_METEO_DB_PASSWORD` for PostgreSQL access
- `RPI3_METEO_DB_ENABLED`, `RPI3_METEO_DB_STORE_RAW_MESSAGES`, and `RPI3_METEO_DB_STORE_SENSOR_READINGS` to control persistence
- `RPI3_METEO_AIR_QUALITY_ENABLED` and the `RPI3_METEO_AIR_QUALITY_*` variables to tune or disable the relative air quality score
- `RPI3_METEO_CONTAINER_UID` and `RPI3_METEO_CONTAINER_GID` to match the Docker web container user with the owner of the local `./data` directory

Database credentials can be replaced with your own secret values in `.env`. Keep `.env` out of version control and do not commit real passwords.

## Local development

```bash
cp .env.generic .env
conda env create -f environment.yml
conda activate rpi-meteo
set -a
source .env
set +a
uvicorn app.main:app --reload
```

The app is then available at `http://127.0.0.1:8000`.

Example without Docker, using explicit environment variables:

```bash
export RPI3_METEO_LOCATION_LABEL="Your location"
export RPI3_METEO_LATITUDE=42.40
export RPI3_METEO_LONGITUDE=-13.12
export RPI3_METEO_ALTITUDE_M=225
export RPI3_METEO_MQTT_BROKER=127.0.0.1
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Docker startup

```bash
cp .env.generic .env
docker compose up --build
```

For local development on WSL with Docker Desktop, you can also use:

```bash
chmod +x scripts/deploy_rpi.sh
./scripts/deploy_rpi.sh
```

If port `8000` is already in use on your workstation, set a different host port in `.env`, for example:

```bash
RPI3_METEO_WEB_PORT=8001
```

Typical local dev test flow on WSL:

1. Start the stack locally:

```bash
./scripts/deploy_rpi.sh
```

2. Open the app in a browser:

```text
http://127.0.0.1:8000
```

or the port defined by `RPI3_METEO_WEB_PORT`.

3. If the Pico is still publishing to the Raspberry Pi IP instead of your PC, no MQTT data will reach the local WSL stack. In that case, publish local sample messages to validate the full chain:

```bash
python tools/publish_test_payload.py --host 127.0.0.1 --export-mode raw
python tools/publish_test_payload.py --host 127.0.0.1 --export-mode aggregated
```

4. Refresh the dashboard and confirm that the realtime cards and recent measurements are populated.

## Fresh Raspberry Pi installation

On a new Raspberry Pi OS installation, install the basic tools first. This must be done on the Raspberry Pi itself, including from a Remote-SSH terminal: the Remote-SSH session uses the tools installed on the Pi, not the ones installed on your PC.

```bash
sudo apt update
sudo apt install -y git curl ca-certificates
```

## Miniconda on Raspberry Pi

Use a 64-bit Raspberry Pi OS image. Check the architecture first:

```bash
uname -m
```

Expected value for current Raspberry Pi OS 64-bit is `aarch64`. If the command returns `armv7l`, install the 64-bit OS before using the Miniconda installer below.

Download and install Miniconda for Linux aarch64:

```bash
cd /tmp
curl -fsSLO https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-aarch64.sh
bash Miniconda3-latest-Linux-aarch64.sh
```

Accept the license, keep the default install path when possible, and answer `yes` when the installer asks whether to initialize Conda. Then close and reopen the SSH session, or load Conda in the current shell:

```bash
source "$HOME/miniconda3/etc/profile.d/conda.sh"
```

After cloning the project with the commands below, create the project environment from the repository:

```bash
cd ~/github/rpi-meteo
conda env create -f environment.yml
conda activate rpi-meteo
```

When `environment.yml` changes later, update the existing environment with:

```bash
conda activate rpi-meteo
conda env update -f environment.yml --prune
```

If environment creation fails, the `rpi-meteo` environment is usually not created. Check with:

```bash
conda info --envs
```

Then fix `environment.yml` and run `conda env create -f environment.yml` again. If a partial environment appears in the list, remove it first:

```bash
conda env remove -n rpi-meteo
conda env create -f environment.yml
```

Run the app directly with Conda:

```bash
set -a
source .env
set +a
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

The dashboard is then available at `http://<raspberry-pi-ip>:8000`.

## Docker installation on Raspberry Pi

Install Docker with the official convenience script, then add the current user to the `docker` group:

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker "$USER"
```

Close and reopen the SSH session so the new group membership is applied. For the current shell only, you can also run:

```bash
newgrp docker
```

Verify Docker and the Compose plugin:

```bash
docker run hello-world
docker compose version
```

Then clone and start the project:

```bash
mkdir -p ~/github
cd ~/github
git clone git@github.com:jgrelet/rpi3-meteo.git rpi-meteo
cd rpi-meteo
cp .env.generic .env
```

If the Pi does not have a GitHub SSH key configured yet, use the HTTPS URL instead:

```bash
git clone https://github.com/jgrelet/rpi3-meteo.git rpi-meteo
```

Edit `.env` and set at least the local forecast values:

- `RPI3_METEO_LOCATION_LABEL`
- `RPI3_METEO_LATITUDE`
- `RPI3_METEO_LONGITUDE`
- `RPI3_METEO_ALTITUDE_M`

Start the full stack:

```bash
docker compose up -d --build
```

The dashboard is then available from the Pi at:

```text
http://127.0.0.1:8000
```

or from another machine on the same network at:

```text
http://<raspberry-pi-ip>:8000
```

## Docker on WSL and Raspberry Pi

Recommended workflow:

- develop and test on WSL with Docker Desktop
- perform final validation on the Raspberry Pi

The `Dockerfile` uses a Conda-based Miniforge image and installs the runtime from `environment.yml` with `conda`.
The app uses `psycopg` without the `binary` extra so it remains compatible with Raspberry Pi OS and Docker targets.

Useful checks:

```bash
docker compose up --build
```

From WSL, you can also validate a 64-bit Raspberry Pi target build without deploying to the device:

```bash
docker buildx build --platform linux/arm64 -t rpi-meteo:test .
```

That build check is useful, but it does not replace a real Raspberry Pi validation for memory usage, performance, and full startup behavior.

## Full Docker stack

The deployment target is fully containerized:

- `mosquitto` runs in `docker compose`
- `postgres` runs in `docker compose`
- the web app runs in `docker compose`
- MQTT persistence uses Docker volumes
- PostgreSQL persistence uses a Docker volume
- local auxiliary files such as the air-quality state stay in the repository `./data` directory

Provided files:

- `docker-compose.yml`
- `mosquitto/mosquitto.conf`
- `scripts/deploy_rpi.sh`
- `.env.generic`

Runtime notes:

- the Pico publishes to the Pi IP on port `1883`
- that port is exposed by the `mosquitto` container
- PostgreSQL is exposed on port `5432` so a remote WSL script can query the database
- the `web` container connects to the broker through the Docker service name `mosquitto`
- the `web` container connects to PostgreSQL through the Docker service name `postgres`
- PostgreSQL data is stored in the `postgres_data` volume
- Mosquitto data is stored in the `mosquitto_data` and `mosquitto_log` volumes
- local state files are stored in `./data`
- personal and location-specific values are read from `.env`
- the web container runs with `RPI3_METEO_CONTAINER_UID:RPI3_METEO_CONTAINER_GID`, defaulting to `1000:1000`, so it can write to bind-mounted local files such as `./data/air_quality_state.json`

Recommended preparation:

```bash
cp .env.generic .env
```

If the Raspberry Pi user that owns the repository is not uid/gid `1000:1000`, set these values before deployment:

```bash
id -u
id -g
```

Then copy the returned values into `.env`:

```bash
RPI3_METEO_CONTAINER_UID=<id -u result>
RPI3_METEO_CONTAINER_GID=<id -g result>
```

Then edit `.env` and set at least:

- `RPI3_METEO_LOCATION_LABEL`
- `RPI3_METEO_LATITUDE`
- `RPI3_METEO_LONGITUDE`
- `RPI3_METEO_ALTITUDE_M`

Quick test with sample messages:

```bash
python tools/publish_test_payload.py --host 127.0.0.1 --export-mode raw
python tools/publish_test_payload.py --host 127.0.0.1 --export-mode aggregated
```

To inspect messages handled by the containerized broker:

```bash
docker exec -it rpi-meteo-mosquitto mosquitto_sub -h 127.0.0.1 -p 1883 -t 'weather/sensors/#' -v
```

To inspect PostgreSQL data from the Raspberry Pi host:

```bash
docker exec -it rpi-meteo-postgres psql -U "$RPI3_METEO_DB_USER" -d "$RPI3_METEO_DB_NAME" -c 'select count(*) from raw_messages;'
docker exec -it rpi-meteo-postgres psql -U "$RPI3_METEO_DB_USER" -d "$RPI3_METEO_DB_NAME" -c 'select count(*) from sensor_readings;'
```

Available PostgreSQL views created by the app:

- `latest_sensor_values`: latest value per `source/channel/export_mode/sensor_name`
- `sensor_series_numeric`: numeric time series with precomputed hour/day buckets
- `hourly_sensor_stats`: hourly aggregates ready for plotting or reporting

## Remote plotting from WSL

The repository now includes [tools/plot_remote_postgres.py](tools/plot_remote_postgres.py), a dedicated script to query a remote PostgreSQL instance and produce time-series plots with `matplotlib` and `numpy`.

It is intentionally separate from the web app runtime so the Docker image does not need the plotting stack.
The script automatically reads database credentials from `.env` when present and uses a non-interactive backend unless `--show` is passed.
For remote plotting outside Docker, use `RPI3_METEO_PLOT_DB_HOST` when `RPI3_METEO_DB_HOST=postgres` is only valid from inside the Docker network.

Install the plotting dependencies on WSL with `conda`:

```bash
conda activate rpi-meteo
conda install -c conda-forge psycopg matplotlib numpy
```

Example against the Raspberry Pi database:

```bash
python tools/plot_remote_postgres.py \
  --host 192.168.1.42 \
  --port 5432 \
  --dbname rpi_meteo \
  --user rpi_meteo \
  --password rpi_meteo \
  --hours 48 \
  --export-mode aggregated \
  --sensors temperature_c humidity_pct pressure_hpa wind_speed_kmh rain_mm_total \
  --out plots/rpi-meteo-48h.png
```

The script supports:

- `--hours` to define the time window
- `--sensors` to choose which series to plot
- `--export-mode raw|aggregated`
- `--resolution hourly|raw` to choose hourly aggregates or raw samples
- `--source` and `--channel` to narrow the query
- `--show` to display the figure interactively

## Deploy on Raspberry Pi

The `scripts/deploy_rpi.sh` script restarts the full Docker stack from the current working tree.
It is the preferred workflow when editing directly on the Raspberry Pi with Remote-SSH.

```bash
chmod +x scripts/deploy_rpi.sh
./scripts/deploy_rpi.sh
```

By default, it works from the repository that contains the script. You can override the target path:

```bash
APP_DIR=/home/user/github/rpi-meteo ./scripts/deploy_rpi.sh
```

Default `up` runs:

- `docker compose down`
- `docker compose build`
- `docker compose up -d`

Useful commands:

```bash
./scripts/deploy_rpi.sh ps
./scripts/deploy_rpi.sh logs
./scripts/deploy_rpi.sh restart
./scripts/deploy_rpi.sh down
```

If you still want the old Git-based deployment flow, use:

```bash
./scripts/deploy_rpi.sh pull-up
```

Migration note: older deployments used `rpi3-meteo` as the Docker Compose prefix.
The current stack uses `rpi-meteo`, so new Docker volumes are named with the `rpi-meteo_` prefix.
The deploy script removes old containers with the previous prefix to avoid port conflicts, but it does not delete old volumes.
If you need to keep existing PostgreSQL data, back it up before switching prefixes.

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

- `desktop/rpi-meteo-kiosk.desktop`
- `desktop/rpi-meteo-kiosk-stop.desktop`
- `desktop/rpi-meteo-kiosk-autostart.desktop`

These files are templates. Do not copy them manually as-is: their `Exec` entries contain
`__APP_DIR__`, which must be replaced by the real repository path on the Raspberry Pi.

Recommended installation on the Pi:

```bash
chmod +x scripts/start_kiosk.sh scripts/stop_kiosk.sh scripts/install_kiosk_shortcuts.sh
./scripts/install_kiosk_shortcuts.sh
```

The script generates the `.desktop` files automatically with the real repository path on the Pi.
It installs:

- `rpi-meteo-kiosk.desktop` on the desktop, using `xdg-user-dir DESKTOP`, `~/Bureau`, or `~/Desktop`
- `rpi-meteo-kiosk-stop.desktop` in the same desktop directory
- `rpi-meteo-kiosk-autostart.desktop` in `~/.config/autostart`

After installation, the kiosk launcher can be started from the desktop and the autostart entry
will launch the kiosk at the next graphical session login.

## Quick verification

A simple Python syntax check is to compile all modules without executing them:

```bash
python3 -m compileall app
```

This is a fast way to catch syntax errors before integration or redeployment.

## Take and recover screenshot

With X11, use:
```bash
DISPLAY:0 scrop /tmp/screenshot-acceuil.png
```

with Waylan:
```bash
grim /tmp/screenshot-acceuil.png
```

and copy with scp:
```bash
scp user@192.168.1.x:/tmp/screenshot-*.png .
```
