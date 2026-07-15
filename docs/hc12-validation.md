# HC-12 validation guide

This guide records the bench configuration and the ordered checks required to
validate the HC-12 transport between `weather_web_sensors` and `rpi3-meteo`.
Run one command at a time and validate its expected result before continuing.

## Layers and device roles

The validation setup keeps the Pico2-W connected to the Raspberry Pi 4 by USB:

| Layer | Endpoint | Purpose |
| --- | --- | --- |
| SSH | workstation -> Raspberry Pi | Run Raspberry Pi commands remotely |
| USB CDC | Pico -> `/dev/ttyACM0` | Power and MicroPython diagnostic console |
| Pico UART0 | `GP0` TX and `GP1` RX | Pico connection to its HC-12 |
| Raspberry Pi UART | `/dev/serial0` | Raspberry Pi connection to its HC-12 |
| HC-12 radio | HC-12 <-> HC-12 | Weather data link under test |
| MQTT | local Mosquitto | Application transport after radio validation |
| PostgreSQL | `sensor_readings` | Final persistence check after MQTT validation |

USB and HC-12 carry different traffic. `/dev/ttyACM0` must not be used as the
Raspberry Pi HC-12 port, and `/dev/serial0` must not be used as the Pico console.

## 1. Check the Pico USB connection

On the Raspberry Pi SSH terminal:

```bash
lsusb
```

Expected: a `MicroPython Board in FS mode` entry.

Then:

```bash
ls -l /dev/ttyACM0
```

Expected: the device exists and normally belongs to group `dialout`. Confirm that
the current user belongs to that group with `id` if access is denied.

## 2. Check the Pico application and console

The recommended development setup uses one multi-root VS Code workspace connected
to the Raspberry Pi over SSH, with both repositories added as workspace folders:

- `rpi3-meteo`: Raspberry Pi, Docker, MQTT and PostgreSQL work
- `weather_web_sensors`: Pico, MicroPython and HC-12 test work

Keep `weather_web_sensors` as the first workspace folder. MicroPico targets the first
root when initializing or uploading a project; if `rpi3-meteo` comes first, files can
be copied under the wrong Pico path instead of replacing `/app` and `/config.py`.

Using a single Remote-SSH window keeps one MicroPico extension host responsible for
`/dev/ttyACM0`. Do not open a second Remote-SSH VS Code window with MicroPico
auto-connecting to the same Pico: the two extension hosts can compete for the port
and report `Cannot lock port`.

Install and enable the **MicroPico** extension on the SSH host in this workspace.
MicroPython is the firmware running on the Pico; MicroPico is the VS Code extension
that controls it. Run `MicroPico: Initialize MicroPico project` once in the existing
`weather_web_sensors` folder, then run `MicroPico: Connect`. Do not select the
MicroPython status-bar action `New project`, which is intended to generate a new
project rather than initialize this existing repository.

The MicroPico vREPL should identify the board, for example:

```text
MicroPython v1.27.0 on 2025-12-09; Raspberry Pi Pico 2 W with RP2350
>>>
```

If `MicroPico: Connect` reports `cannot lock port`, another process such as miniterm
still owns `/dev/ttyACM0`. Close that terminal or process before reconnecting.

As a command-line fallback, open the console from the Raspberry Pi SSH terminal:

```bash
python -m serial.tools.miniterm /dev/ttyACM0 115200
```

After a normal reboot, the Pico starts `main.py`. In Wi-Fi mode, messages such as
`Exported raw via MqttExporter.` confirm that the normal application is running.

Press `Ctrl+C` once to stop it and obtain the MicroPython `>>>` prompt. Exit
miniterm with `Ctrl+]` only when the console is no longer needed. On keyboard layouts
where that shortcut cannot be sent, killing the dedicated VS Code terminal also
closes miniterm and releases `/dev/ttyACM0`.

## 3. Start the standalone Pico HC-12 test

With MicroPico, open `tools/hc12_pico_test.py` from the `weather_web_sensors`
workspace folder and run
`MicroPico: Run current file on Pico`. This executes the test without replacing the
deployed `main.py`.

The test file previously copied to the Pico filesystem is also available at its
root. When using the plain MicroPython `>>>` prompt instead of MicroPico, start it
with:

```python
import hc12_pico_test
```

Expected startup output:

```text
HC-12 Pico test on UART0 TX=GP0 RX=GP1 baud=9600
Loop sends PING_PICO and replies ACK_PICO to received lines.
```

The console then prints a `sent: PING_PICO ...` line about every two seconds.
An import from `tools.hc12_pico_test` is not appropriate for the current deployed
layout, even though the source file lives under `tools/` in the Git repository.

The test is started manually and does not survive a Pico or Raspberry Pi power
cycle. Repeat sections 2 and 3 after every reboot.

## 4. Prepare the Raspberry Pi Python environment

Activate the `rpi-meteo` Conda environment, then install the serial dependency if
needed:

```bash
conda install pyserial=3.5
```

`pyserial` is the required package. The unrelated PyPI package named `serial`
does not provide `serial.Serial` and must not be installed.

## 5. Release the Raspberry Pi UART from the Linux console

Run:

```bash
sudo raspi-config
```

Under `Interface Options` -> `Serial Port`, answer:

- login shell accessible over serial: **No**
- serial port hardware enabled: **Yes**

Reboot when requested, reconnect over SSH, and remember to restart the standalone
Pico test as described in sections 2 and 3.

Confirm that the kernel command line no longer assigns a console to the UART:

```bash
cat /proc/cmdline
```

Expected: neither `console=ttyS0,115200` nor `console=serial0,115200` is present.

Then inspect the UART device:

```bash
ls -l /dev/serial0 "$(readlink -f /dev/serial0)"
```

Expected on the current Raspberry Pi 4: `/dev/serial0 -> ttyS0`, with the target
device writable by `root:dialout` and the current user in `dialout`.

When the application runs in Docker, also set `RPI3_METEO_HC12_DEVICE_GID` to the
numeric host GID returned by `getent group dialout`. Compose must add this GID as a
supplementary group to the web container user. A device mounted as `root:dialout`
with mode `660` otherwise remains inaccessible even when it is visible in the
container.

## 6. Validate Pico-to-Raspberry-Pi reception

Keep miniterm open with `hc12_pico_test` running. Open a second SSH terminal in the
`rpi3-meteo` repository and run:

```bash
python tools/hc12_rpi_test.py --device /dev/serial0 --receive
```

Expected: complete `received: PING_PICO ...` lines about every two seconds, with
timestamps in both UTC and `Europe/Paris`. Stop the receiver with `Ctrl+C` before
starting another Raspberry Pi serial test.

## 7. Validate Raspberry-Pi-to-Pico transmission

With the Pico test still visible in miniterm, run from the second terminal:

```bash
python tools/hc12_rpi_test.py --device /dev/serial0 --send
```

Expected in the Pico console: `received: PING_RPI ...`, followed by an
`ACK_PICO ...` response. The Raspberry Pi terminal should also print the returned
`ACK_PICO PING_RPI ...` line. It can additionally receive the Pico's periodic
`PING_PICO` frames while this bidirectional test is running. Stop the sender with
`Ctrl+C` before the next test.

## 8. Remaining validation

After the standalone scripts provide reliable complete lines:

- validate acknowledgements in both directions;
- run the standalone link for at least ten minutes;
- confirm that counters progress and no messages are corrupted or repeatedly lost;
- switch the Pico from `TRANSPORT_MODE = "wifi"` to `"hc-12"`;
- set `RPI3_METEO_TRANSMISSION_MODE=hc-12` on the Raspberry Pi;
- start the HC-12-to-MQTT bridge;
- inspect `weather/sensors/raw` for real-time messages;
- allow for the normal hourly delay before expecting `weather/sensors` aggregates;
- verify PostgreSQL counters by `export_mode`.

Only one process may open `/dev/serial0`. Stop all standalone serial tests before
starting the application bridge.

Use a serial read timeout of at least five seconds for application payloads. The
standalone pings are short, but a paced weather JSON line can take longer than one
second to reach its final newline; a shorter timeout makes `readline()` return an
incomplete payload.

## Validation record

Bench validation on 2026-07-14:

- [x] Pico detected as a MicroPython USB device on `/dev/ttyACM0`
- [x] USB console accessible by user `jgrelet` through group `dialout`
- [x] standalone Pico HC-12 test starts at 9600 baud on UART0, `GP0`/`GP1`
- [x] Linux serial login console removed from `/dev/serial0`
- [x] `/dev/serial0 -> /dev/ttyS0`, accessible through `dialout`
- [x] Pico-to-Raspberry-Pi `PING_PICO` frames received over HC-12
- [x] Raspberry-Pi-to-Pico `PING_RPI` frames received over HC-12
- [x] bidirectional `PING_RPI` / `ACK_PICO` exchange validated with simultaneous `PING_PICO` traffic
- [x] standalone bidirectional reliability and endurance validated
- [x] HC-12-to-MQTT bridge validated
- [x] MQTT-to-PostgreSQL ingestion validated

Observed successful Pico-to-Raspberry-Pi reception began at
`2026-07-14 15:27:11 UTC` / `2026-07-14 17:27:11 Europe/Paris`.

Complete bidirectional frames and acknowledgements were validated on
`2026-07-15 06:38:49 UTC` / `2026-07-15 08:38:49 Europe/Paris`.

The ten-minute endurance test completed from `2026-07-15 06:42:38 UTC` /
`2026-07-15 08:42:38 Europe/Paris` through `2026-07-15 06:52:37 UTC` /
`2026-07-15 08:52:37 Europe/Paris`. Results: 150 `PING_RPI` sent, 150 matching
`ACK_PICO` received, and all 298 consecutive `PING_PICO` frames from counter 237
through 534 received. No radio loss was observed during this run.

The application path HC-12 -> `weather/sensors/raw` -> PostgreSQL was validated on
2026-07-15. Consecutive raw messages were stored at `2026-07-15 12:25:30 UTC`,
`12:25:40 UTC` and `12:25:50 UTC`, corresponding to `14:25:30`, `14:25:40` and
`14:25:50 Europe/Paris`.

During the Pico `test` timing profile, raw acquisitions are emitted every 10 seconds
and aggregated snapshots every 60 seconds. Set the local Raspberry Pi
`RPI3_METEO_UI_REFRESH_SECONDS=10` while validating this profile so the kiosk can
show each raw update. The generic production default remains 30 seconds.
