import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"


def env_str(name: str, default: str) -> str:
    return os.getenv(name, default)


def env_bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default).lower()).lower() == "true"


def env_int(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


def env_float(name: str):
    value = os.getenv(name)
    if value in (None, ""):
        return None
    return float(value)


def env_list(name: str, default: list[str]) -> list[str]:
    value = os.getenv(name)
    if value in (None, ""):
        return default
    return [item.strip() for item in value.split(",") if item.strip()]

APP_CONFIG = {
    "host": env_str("RPI3_METEO_HOST", "0.0.0.0"),
    "port": env_int("RPI3_METEO_PORT", 8000),
    "debug": env_bool("RPI3_METEO_DEBUG", False),
    "timezone": env_str("RPI3_METEO_TIMEZONE", "Europe/Paris"),
    "open_meteo_enabled": env_bool("RPI3_METEO_OPEN_METEO_ENABLED", True),
    "openweather_enabled": env_bool("RPI3_METEO_OPENWEATHER_ENABLED", False),
    "default_forecast_provider": env_str("RPI3_METEO_DEFAULT_FORECAST_PROVIDER", "open-meteo"),
    "latitude": env_float("RPI3_METEO_LATITUDE"),
    "longitude": env_float("RPI3_METEO_LONGITUDE"),
    "altitude_m": env_float("RPI3_METEO_ALTITUDE_M"),
    "location_label": env_str("RPI3_METEO_LOCATION_LABEL", "Exemple de localisation"),
}

DATABASE = {
    "engine": env_str("RPI3_METEO_DB_ENGINE", "sqlite"),
    "path": env_str("RPI3_METEO_DB_PATH", str(DATA_DIR / "weather.db")),
    "enabled": env_bool("RPI3_METEO_DB_ENABLED", True),
    "store_raw_messages": env_bool("RPI3_METEO_DB_STORE_RAW_MESSAGES", True),
    "store_sensor_readings": env_bool("RPI3_METEO_DB_STORE_SENSOR_READINGS", True),
}

AIR_QUALITY = {
    "enabled": env_bool("RPI3_METEO_AIR_QUALITY_ENABLED", True),
    "state_path": env_str(
        "RPI3_METEO_AIR_QUALITY_STATE_PATH",
        str(DATA_DIR / "air_quality_state.json"),
    ),
    "burn_in_samples": env_int("RPI3_METEO_AIR_QUALITY_BURN_IN_SAMPLES", 50),
    "baseline_window": env_int("RPI3_METEO_AIR_QUALITY_BASELINE_WINDOW", 50),
    "humidity_baseline_pct": float(env_str("RPI3_METEO_AIR_QUALITY_HUMIDITY_BASELINE_PCT", "40")),
    "humidity_weighting": float(env_str("RPI3_METEO_AIR_QUALITY_HUMIDITY_WEIGHTING", "0.25")),
    "baseline_adaptation_rate": float(env_str("RPI3_METEO_AIR_QUALITY_BASELINE_ADAPTATION_RATE", "0.03")),
    "score_smoothing": float(env_str("RPI3_METEO_AIR_QUALITY_SCORE_SMOOTHING", "0.2")),
}

INGESTION = {
    "default_channel": env_str("RPI3_METEO_DEFAULT_CHANNEL", "mqtt"),
    "mqtt": {
        "enabled": env_bool("RPI3_METEO_MQTT_ENABLED", True),
        "broker": env_str("RPI3_METEO_MQTT_BROKER", "mosquitto"),
        "port": env_int("RPI3_METEO_MQTT_PORT", 1883),
        "aggregated_topic": env_str("RPI3_METEO_MQTT_AGGREGATED_TOPIC", "weather/sensors"),
        "raw_topic": env_str("RPI3_METEO_MQTT_RAW_TOPIC", "weather/sensors/raw"),
        "client_id": env_str("RPI3_METEO_MQTT_CLIENT_ID", "rpi3-meteo-ui"),
        "user": os.getenv("RPI3_METEO_MQTT_USER") or None,
        "password": os.getenv("RPI3_METEO_MQTT_PASSWORD") or None,
        "keepalive": env_int("RPI3_METEO_MQTT_KEEPALIVE", 60),
        "qos": env_int("RPI3_METEO_MQTT_QOS", 0),
    },
    "serial": {
        "enabled": env_bool("RPI3_METEO_SERIAL_ENABLED", False),
        "device": env_str("RPI3_METEO_SERIAL_DEVICE", "/dev/ttyUSB0"),
        "baudrate": env_int("RPI3_METEO_SERIAL_BAUDRATE", 9600),
    },
    "udp": {
        "enabled": env_bool("RPI3_METEO_UDP_ENABLED", False),
        "host": env_str("RPI3_METEO_UDP_HOST", "0.0.0.0"),
        "port": env_int("RPI3_METEO_UDP_PORT", 9999),
    },
}

UI = {
    "title": env_str("RPI3_METEO_UI_TITLE", "RPi3 Meteo"),
    "refresh_seconds": env_int("RPI3_METEO_UI_REFRESH_SECONDS", 5),
    "screen_mode": env_str("RPI3_METEO_UI_SCREEN_MODE", "kiosk"),
    "pages": env_list(
        "RPI3_METEO_UI_PAGES",
        [
            "overview",
            "raw-data",
            "reduced-data",
            "forecast-now",
            "forecast-hours",
            "forecast-days",
        ],
    ),
}
