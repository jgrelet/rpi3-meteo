# rpi-meteo

A display dashboard for a Raspberry Pi showing weather data acquired using a custom-designed [Pico2-w](https://github.com/jgrelet/weather_web_sensors)

Originally, the project was intended to use a Raspberry Pi 3 with its built-in 7-inch screen, but the hardware resources proved insufficient for this project. I therefore had to adapt the case to accommodate a Raspberry Pi 4 with 4 GB of RAM, which offers excellent performance in terms of responsiveness to events.

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

## Sensor transport

The Pico can transmit weather data through one active field link at a time:

- `RPI3_METEO_TRANSMISSION_MODE=wifi` for the existing Wi-Fi path, where the Pico publishes MQTT directly
- `RPI3_METEO_TRANSMISSION_MODE=hc-12` for HC-12 radio over UART, where the Raspberry Pi bridges HC-12 lines back into MQTT

Keep the Pico `TRANSPORT_MODE` in `../weather_web_sensors/config.py` aligned with
`RPI3_METEO_TRANSMISSION_MODE`. The application still consumes the local Mosquitto
broker in both modes.

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

## HC-12 contract

HC-12 mode uses transparent UART lines. The Raspberry Pi web service reads these
lines and republishes them to the same MQTT topics used by Wi-Fi mode:

- `JSON_RAW {...}` for raw acquisitions
- `JSON {...}` for aggregated snapshots

### Recommended validation setup

Validate the radio link independently before switching either application to HC-12
mode. Keep the Pico2-W connected to a Raspberry Pi USB port during these tests:

- Pico USB (`/dev/ttyACM0`): power and MicroPython diagnostic console only
- Pico UART0 on `GP0`/`GP1`: connection to the sensor-side HC-12
- Raspberry Pi UART on `/dev/serial0`: connection to the receiver-side HC-12
- SSH: Raspberry Pi control terminal

USB and HC-12 therefore remain active at the same time, but carry different traffic.
The Pico test script prints diagnostics over USB while its UART exchanges test frames
over the two HC-12 modules. Do not enable the application HC-12 bridge until the
standalone bidirectional test has passed: only one process may open `/dev/serial0`.

### Validation sequence

Run the following checks in order and fix each stage before continuing.
The detailed restart procedure, expected output and validation checklist are kept in
[`docs/hc12-validation.md`](docs/hc12-validation.md).

1. Confirm that the Raspberry Pi detects the Pico USB console:

   ```bash
   lsusb
   ls -l /dev/ttyACM0
   ```

   The USB list should contain a MicroPython board and `/dev/ttyACM0` should exist.
   The Raspberry Pi user must belong to the group that owns the device, normally
   `dialout`.

2. Confirm that the Pico test program is running:

   ```bash
   python -m serial.tools.miniterm /dev/ttyACM0 115200
   ```

   The console should print a new `sent: PING_PICO ...` line about every two seconds.
   Exit miniterm with `Ctrl+]`. The Pico USB port is not the Raspberry Pi HC-12 port.

3. Install the Raspberry Pi serial dependency in the active Conda environment:

   ```bash
   conda install pyserial=3.5
   ```

   `pyserial` is the required package. Do not install the unrelated PyPI package named
   `serial`, which imports successfully but does not provide `serial.Serial`.

4. Enable the Raspberry Pi UART without assigning a Linux login console to it:

   ```bash
   sudo raspi-config
   ```

   In `Interface Options` -> `Serial Port`, answer the two questions exactly as follows:

   - login shell accessible over serial: **No**
   - serial port hardware enabled: **Yes**

   These answers are intentionally different. Answering **Yes** to the login-shell
   question adds `console=ttyS0,115200` to the kernel command line, reserves the HC-12
   UART for Linux and can leave `/dev/ttyS0` accessible only by `root`. Reboot after
   changing this setting.

5. After rebooting and reconnecting over SSH, confirm that the console no longer owns
   the UART and that the user can access it:

   ```bash
   cat /proc/cmdline
   ls -l /dev/serial0 "$(readlink -f /dev/serial0)"
   ```

   `/proc/cmdline` must not contain `console=ttyS0,115200` or
   `console=serial0,115200`. `/dev/serial0` should resolve to the enabled UART and its
   target should be accessible to the current user, normally through `dialout`.

6. With `tools/hc12_pico_test.py` still running on the Pico, validate each direction
   from the `rpi3-meteo` repository:

   ```bash
   python tools/hc12_rpi_test.py --device /dev/serial0 --receive
   python tools/hc12_rpi_test.py --device /dev/serial0 --send
   python tools/hc12_rpi_test.py --device /dev/serial0 --echo
   ```

   Run one command at a time. Expected results are Pico-to-Pi `PING_PICO`, Pi-to-Pico
   `PING_RPI`, then acknowledgements in both directions. Finally leave the echo test
   running for at least ten minutes and check that there are no corrupted lines or
   repeated losses.

7. Only after the standalone radio test passes, switch the Pico to
   `TRANSPORT_MODE = "hc-12"`, configure the Raspberry Pi with
   `RPI3_METEO_TRANSMISSION_MODE=hc-12`, start the application bridge and verify the
   HC-12 -> MQTT -> PostgreSQL path.

Default Raspberry Pi settings:

```bash
RPI3_METEO_TRANSMISSION_MODE=hc-12
RPI3_METEO_HC12_HOST_DEVICE=/dev/serial0
RPI3_METEO_HC12_DEVICE=/dev/serial0
RPI3_METEO_HC12_DEVICE_GID=20
RPI3_METEO_HC12_BAUDRATE=9600
```

Docker maps `RPI3_METEO_HC12_HOST_DEVICE` from the host to `RPI3_METEO_HC12_DEVICE`
inside the `web` container. The default host device in `.env.generic` is `/dev/null`
so local non-Raspberry Pi Docker starts do not fail before HC-12 hardware is installed.
`RPI3_METEO_HC12_DEVICE_GID` must match the host group that owns the UART, normally
the numeric GID shown by `getent group dialout`. Compose adds this as a supplementary
group to the non-root web user; mounting the device alone does not grant access to a
`root:dialout` device with mode `660`.

Recommended wiring:

- Raspberry Pi GPIO14 / TXD0, physical pin `8` -> HC-12 `RXD`
- Raspberry Pi GPIO15 / RXD0, physical pin `10` <- HC-12 `TXD`
- Raspberry Pi `GND`, physical pin `6` -> HC-12 `GND`
- Pico2-W `GP0` / UART0 TX, physical pin `1` -> HC-12 `RXD`
- Pico2-W `GP1` / UART0 RX, physical pin `2` <- HC-12 `TXD`
- Pico2-W `GND`, for example physical pin `3` or `38` -> HC-12 `GND`
- HC-12 `SET` can stay unconnected for normal transparent mode

Hardware notes:

- cross TX/RX on each side
- keep a common ground
- mount antennas before transmitting
- start with the HC-12 factory default `9600` baud
- keep UART wires short while validating the first setup
- enable the Raspberry Pi UART before production use, then verify `/dev/serial0`

Deploy `tools/hc12_pico_test.py` from `../weather_web_sensors` to the Pico and run it
from Thonny, MicroPico or the MicroPython REPL for the standalone validation sequence.

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
- `RPI3_METEO_TRANSMISSION_MODE` to choose Wi-Fi/MQTT direct mode or HC-12 bridge mode
- `RPI3_METEO_HC12_*` when using HC-12 over the Raspberry Pi UART
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
git clone git@github.com:/rpi3-meteo.git rpi-meteo
cd rpi-meteo
cp .env.generic .env
```

If the Pi does not have a GitHub SSH key configured yet, use the HTTPS URL instead:

```bash
git clone https://github.com//rpi3-meteo.git rpi-meteo
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
The kiosk script reads `.env`, waits for the graphical session and the local web app,
then opens Chromium on `http://127.0.0.1:${RPI3_METEO_WEB_PORT:-8000}`.

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

Kiosk settings in `.env`:

```bash
RPI3_METEO_KIOSK_SCREEN_BLANK_SECONDS=60
RPI3_METEO_KIOSK_STARTUP_WAIT_SECONDS=60
```

- `RPI3_METEO_KIOSK_SCREEN_BLANK_SECONDS` controls the screen blanking delay in seconds.
  The default is `60`. Set it to `0` to disable blanking from the kiosk script.
- `RPI3_METEO_KIOSK_STARTUP_WAIT_SECONDS` controls how long autostart waits for the
  graphical session and the local web app before giving up.

On X11 sessions, the script applies the blanking delay with `xset`.
On Wayland sessions without an X11 `DISPLAY`, screen blanking is controlled by the
desktop compositor; keep the same `.env` value as the application setting and configure
the Raspberry Pi OS power-management setting to match when needed.

Kiosk diagnostics:

```bash
tail -n 100 /tmp/rpi-meteo-kiosk.log
journalctl --user -b --no-pager | grep -i rpi-meteo
docker compose ps
curl -I http://127.0.0.1:${RPI3_METEO_WEB_PORT:-8000}
```

## Quick verification

A simple Python syntax check is to compile all modules without executing them:

```bash
python3 -m compileall app
```

This is a fast way to catch syntax errors before integration or redeployment.

## Take and recover a kiosk screenshot

Create a local directory for captures:

```bash
mkdir -p tmp
```

The Raspberry Pi kiosk currently uses Wayland. From an SSH terminal, provide the
graphical session environment explicitly and capture the complete display with
`grim`:

```bash
XDG_RUNTIME_DIR=/run/user/$(id -u) WAYLAND_DISPLAY=wayland-0 grim tmp/capture-kiosque.png
```

If `grim` is not installed, install the Raspberry Pi OS package with
`sudo apt install grim`. The Wayland socket can be checked with
`ls -l /run/user/$(id -u)/wayland-*` if the command cannot find the display.

For an X11 session, use `scrot` instead:

```bash
DISPLAY=:0 scrot tmp/capture-kiosque.png
```

The PNG can be opened directly from the Remote-SSH VS Code explorer. To retrieve it
from another computer, run there:

```bash
scp user@192.168.1.x:~/tmp/capture-kiosque.png .
```

## Roadmap

- Complete the rain and wind sensors, including electronics, mechanical assembly,
  calibration and software validation.
- Integrate the autonomous station into its enclosure with the 3D-printed weather
  shield.
- Add a Radar kiosk menu for weather-radar animation playback inspired by the
  Météo & Radar presentation.
- Measure each operating state and establish a complete power-consumption and
  solar-energy budget.
