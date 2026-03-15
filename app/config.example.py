import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

APP_CONFIG = {
    "host": "0.0.0.0",
    "port": 8000,
    "debug": False,
    "timezone": "Europe/Paris",
    "open_meteo_enabled": True,
    "openweather_enabled": False,
    "default_forecast_provider": "open-meteo",
    "latitude": 48.8566,
    "longitude": 2.3522,
}

DATABASE = {
    "engine": "sqlite",
    "path": os.getenv("RPI3_METEO_DB_PATH", str(DATA_DIR / "weather.db")),
}

INGESTION = {
    "default_channel": "mqtt",
    "mqtt": {
        "enabled": os.getenv("RPI3_METEO_MQTT_ENABLED", "true").lower() == "true",
        "broker": os.getenv("RPI3_METEO_MQTT_BROKER", "mosquitto"),
        "port": int(os.getenv("RPI3_METEO_MQTT_PORT", "1883")),
        "aggregated_topic": os.getenv("RPI3_METEO_MQTT_AGGREGATED_TOPIC", "weather/sensors"),
        "raw_topic": os.getenv("RPI3_METEO_MQTT_RAW_TOPIC", "weather/sensors/raw"),
        "client_id": os.getenv("RPI3_METEO_MQTT_CLIENT_ID", "rpi3-meteo-ui"),
        "user": os.getenv("RPI3_METEO_MQTT_USER") or None,
        "password": os.getenv("RPI3_METEO_MQTT_PASSWORD") or None,
        "keepalive": int(os.getenv("RPI3_METEO_MQTT_KEEPALIVE", "60")),
        "qos": int(os.getenv("RPI3_METEO_MQTT_QOS", "0")),
    },
    "serial": {
        "enabled": False,
        "device": "/dev/ttyUSB0",
        "baudrate": 9600,
    },
    "udp": {
        "enabled": False,
        "host": "0.0.0.0",
        "port": 9999,
    },
}

UI = {
    "title": "RPi3 Meteo",
    "refresh_seconds": 5,
    "screen_mode": "kiosk",
    "pages": [
        "overview",
        "raw-data",
        "reduced-data",
        "forecast",
    ],
}
