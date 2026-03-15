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
    "latitude": None,
    "longitude": None,
}

DATABASE = {
    "engine": "sqlite",
    "path": str(DATA_DIR / "weather.db"),
}

INGESTION = {
    "default_channel": "mqtt",
    "mqtt": {
        "enabled": True,
        "broker": "127.0.0.1",
        "port": 1883,
        "topic": "weather/sensors",
        "client_id": "rpi3-meteo-ui",
        "user": None,
        "password": None,
        "keepalive": 60,
        "qos": 0,
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
