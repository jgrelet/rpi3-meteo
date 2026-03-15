#!/bin/bash
set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

sudo apt update
sudo apt install -y mosquitto mosquitto-clients
sudo cp "$REPO_DIR/mosquitto/mosquitto.conf" /etc/mosquitto/conf.d/rpi3-meteo.conf
sudo systemctl enable mosquitto
sudo systemctl restart mosquitto
sudo systemctl status mosquitto --no-pager
