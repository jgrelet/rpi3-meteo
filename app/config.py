import os
from pathlib import Path
from typing import List, Optional, Set


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DEFAULT_UI_PAGES: List[str] = [
    "overview",
    "raw-data",
    "reduced-data",
    "forecast-now",
    "forecast-hours",
    "forecast-days",
]
ALLOWED_UI_PAGES: Set[str] = set(DEFAULT_UI_PAGES)
ALLOWED_FORECAST_PROVIDERS: Set[str] = {"open-meteo", "openweather"}
ALLOWED_SCREEN_MODES: Set[str] = {"kiosk", "windowed"}
ALLOWED_DB_ENGINES: Set[str] = {"postgresql"}
ALLOWED_CHANNELS: Set[str] = {"mqtt", "serial", "udp"}


class ConfigError(ValueError):
    pass


def _raw_env(name: str) -> Optional[str]:
    value = os.getenv(name)
    if value is None:
        return None
    value = value.strip()
    return value or None


def env_str(name: str, default: str) -> str:
    return _raw_env(name) or default


def env_bool(name: str, default: bool) -> bool:
    value = _raw_env(name)
    if value is None:
        return default
    normalized = value.lower()
    if normalized in {"true", "1", "yes", "on"}:
        return True
    if normalized in {"false", "0", "no", "off"}:
        return False
    raise ConfigError(f"{name} must be a boolean, got {value!r}")


def env_int(name: str, default: int) -> int:
    value = _raw_env(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer, got {value!r}") from exc


def env_float(name: str) -> Optional[float]:
    value = _raw_env(name)
    if value is None:
        return None
    try:
        return float(value)
    except ValueError as exc:
        raise ConfigError(f"{name} must be a float, got {value!r}") from exc


def env_list(name: str, default: List[str]) -> List[str]:
    value = _raw_env(name)
    if value is None:
        return default
    items = [item.strip() for item in value.split(",") if item.strip()]
    if not items:
        raise ConfigError(f"{name} must contain at least one value")
    return items


def env_optional_str(name: str) -> Optional[str]:
    return _raw_env(name)


def _require_choice(name: str, value: str, allowed: Set[str]) -> str:
    if value not in allowed:
        allowed_values = ", ".join(sorted(allowed))
        raise ConfigError(f"{name} must be one of: {allowed_values}. Got {value!r}")
    return value


def _require_positive_int(name: str, value: int) -> int:
    if value <= 0:
        raise ConfigError(f"{name} must be > 0, got {value}")
    return value


def _require_non_negative_float(name: str, value: Optional[float]) -> Optional[float]:
    if value is not None and value < 0:
        raise ConfigError(f"{name} must be >= 0, got {value}")
    return value


APP_CONFIG = {
    "host": env_str("RPI3_METEO_HOST", "0.0.0.0"),
    "port": _require_positive_int("RPI3_METEO_PORT", env_int("RPI3_METEO_PORT", 8000)),
    "debug": env_bool("RPI3_METEO_DEBUG", False),
    "timezone": env_str("RPI3_METEO_TIMEZONE", "Europe/Paris"),
    "open_meteo_enabled": env_bool("RPI3_METEO_OPEN_METEO_ENABLED", True),
    "openweather_enabled": env_bool("RPI3_METEO_OPENWEATHER_ENABLED", False),
    "default_forecast_provider": _require_choice(
        "RPI3_METEO_DEFAULT_FORECAST_PROVIDER",
        env_str("RPI3_METEO_DEFAULT_FORECAST_PROVIDER", "open-meteo"),
        ALLOWED_FORECAST_PROVIDERS,
    ),
    "latitude": env_float("RPI3_METEO_LATITUDE"),
    "longitude": env_float("RPI3_METEO_LONGITUDE"),
    "altitude_m": _require_non_negative_float("RPI3_METEO_ALTITUDE_M", env_float("RPI3_METEO_ALTITUDE_M")),
    "location_label": env_str("RPI3_METEO_LOCATION_LABEL", "Localisation a definir"),
}

DATABASE = {
    "engine": _require_choice(
        "RPI3_METEO_DB_ENGINE",
        env_str("RPI3_METEO_DB_ENGINE", "postgresql"),
        ALLOWED_DB_ENGINES,
    ),
    "host": env_str("RPI3_METEO_DB_HOST", "postgres"),
    "port": _require_positive_int("RPI3_METEO_DB_PORT", env_int("RPI3_METEO_DB_PORT", 5432)),
    "name": env_str("RPI3_METEO_DB_NAME", "rpi3_meteo"),
    "user": env_str("RPI3_METEO_DB_USER", "rpi3_meteo"),
    "password": env_str("RPI3_METEO_DB_PASSWORD", "rpi3_meteo"),
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
    "burn_in_samples": _require_positive_int(
        "RPI3_METEO_AIR_QUALITY_BURN_IN_SAMPLES",
        env_int("RPI3_METEO_AIR_QUALITY_BURN_IN_SAMPLES", 50),
    ),
    "baseline_window": _require_positive_int(
        "RPI3_METEO_AIR_QUALITY_BASELINE_WINDOW",
        env_int("RPI3_METEO_AIR_QUALITY_BASELINE_WINDOW", 50),
    ),
    "humidity_baseline_pct": float(env_str("RPI3_METEO_AIR_QUALITY_HUMIDITY_BASELINE_PCT", "40")),
    "humidity_weighting": float(env_str("RPI3_METEO_AIR_QUALITY_HUMIDITY_WEIGHTING", "0.25")),
    "baseline_adaptation_rate": float(env_str("RPI3_METEO_AIR_QUALITY_BASELINE_ADAPTATION_RATE", "0.03")),
    "score_smoothing": float(env_str("RPI3_METEO_AIR_QUALITY_SCORE_SMOOTHING", "0.2")),
}

INGESTION = {
    "default_channel": _require_choice(
        "RPI3_METEO_DEFAULT_CHANNEL",
        env_str("RPI3_METEO_DEFAULT_CHANNEL", "mqtt"),
        ALLOWED_CHANNELS,
    ),
    "mqtt": {
        "enabled": env_bool("RPI3_METEO_MQTT_ENABLED", True),
        "broker": env_str("RPI3_METEO_MQTT_BROKER", "mosquitto"),
        "port": _require_positive_int("RPI3_METEO_MQTT_PORT", env_int("RPI3_METEO_MQTT_PORT", 1883)),
        "aggregated_topic": env_str("RPI3_METEO_MQTT_AGGREGATED_TOPIC", "weather/sensors"),
        "raw_topic": env_str("RPI3_METEO_MQTT_RAW_TOPIC", "weather/sensors/raw"),
        "client_id": env_str("RPI3_METEO_MQTT_CLIENT_ID", "rpi3-meteo-ui"),
        "user": env_optional_str("RPI3_METEO_MQTT_USER"),
        "password": env_optional_str("RPI3_METEO_MQTT_PASSWORD"),
        "keepalive": _require_positive_int(
            "RPI3_METEO_MQTT_KEEPALIVE",
            env_int("RPI3_METEO_MQTT_KEEPALIVE", 60),
        ),
        "qos": env_int("RPI3_METEO_MQTT_QOS", 0),
    },
    "serial": {
        "enabled": env_bool("RPI3_METEO_SERIAL_ENABLED", False),
        "device": env_str("RPI3_METEO_SERIAL_DEVICE", "/dev/ttyUSB0"),
        "baudrate": _require_positive_int(
            "RPI3_METEO_SERIAL_BAUDRATE",
            env_int("RPI3_METEO_SERIAL_BAUDRATE", 9600),
        ),
    },
    "udp": {
        "enabled": env_bool("RPI3_METEO_UDP_ENABLED", False),
        "host": env_str("RPI3_METEO_UDP_HOST", "0.0.0.0"),
        "port": _require_positive_int("RPI3_METEO_UDP_PORT", env_int("RPI3_METEO_UDP_PORT", 9999)),
    },
}

UI = {
    "title": env_str("RPI3_METEO_UI_TITLE", "RPi3 Meteo"),
    "refresh_seconds": _require_positive_int(
        "RPI3_METEO_UI_REFRESH_SECONDS",
        env_int("RPI3_METEO_UI_REFRESH_SECONDS", 5),
    ),
    "screen_mode": _require_choice(
        "RPI3_METEO_UI_SCREEN_MODE",
        env_str("RPI3_METEO_UI_SCREEN_MODE", "kiosk"),
        ALLOWED_SCREEN_MODES,
    ),
    "pages": env_list("RPI3_METEO_UI_PAGES", DEFAULT_UI_PAGES),
}

AIR_QUALITY["humidity_baseline_pct"] = _require_non_negative_float(
    "RPI3_METEO_AIR_QUALITY_HUMIDITY_BASELINE_PCT",
    AIR_QUALITY["humidity_baseline_pct"],
)
AIR_QUALITY["humidity_weighting"] = _require_non_negative_float(
    "RPI3_METEO_AIR_QUALITY_HUMIDITY_WEIGHTING",
    AIR_QUALITY["humidity_weighting"],
)
AIR_QUALITY["baseline_adaptation_rate"] = _require_non_negative_float(
    "RPI3_METEO_AIR_QUALITY_BASELINE_ADAPTATION_RATE",
    AIR_QUALITY["baseline_adaptation_rate"],
)
AIR_QUALITY["score_smoothing"] = _require_non_negative_float(
    "RPI3_METEO_AIR_QUALITY_SCORE_SMOOTHING",
    AIR_QUALITY["score_smoothing"],
)

if INGESTION["mqtt"]["qos"] not in {0, 1, 2}:
    raise ConfigError(f"RPI3_METEO_MQTT_QOS must be 0, 1 or 2, got {INGESTION['mqtt']['qos']}")

invalid_pages = [page for page in UI["pages"] if page not in ALLOWED_UI_PAGES]
if invalid_pages:
    raise ConfigError(
        "RPI3_METEO_UI_PAGES contains unsupported pages: {}".format(", ".join(invalid_pages))
    )

if APP_CONFIG["default_forecast_provider"] == "open-meteo" and not APP_CONFIG["open_meteo_enabled"]:
    raise ConfigError("RPI3_METEO_DEFAULT_FORECAST_PROVIDER=open-meteo but RPI3_METEO_OPEN_METEO_ENABLED=false")

if APP_CONFIG["default_forecast_provider"] == "openweather" and not APP_CONFIG["openweather_enabled"]:
    raise ConfigError("RPI3_METEO_DEFAULT_FORECAST_PROVIDER=openweather but RPI3_METEO_OPENWEATHER_ENABLED=false")
