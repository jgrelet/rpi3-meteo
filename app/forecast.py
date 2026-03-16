from __future__ import annotations

import json
import time
from datetime import datetime
from typing import Dict, List, Optional
from urllib.parse import urlencode
from urllib.request import urlopen

from app.config import APP_CONFIG


OPEN_METEO_BASE_URL = "https://api.open-meteo.com/v1/forecast"
FORECAST_CACHE_SECONDS = 900
_forecast_cache: Dict[str, object] = {
    "expires_at": 0.0,
    "payload": None,
}

WEATHER_CODE_LABELS = {
    0: "Clair",
    1: "Plutot clair",
    2: "Variable",
    3: "Couvert",
    45: "Brouillard",
    48: "Brouillard givrant",
    51: "Bruine faible",
    53: "Bruine",
    55: "Bruine forte",
    61: "Pluie faible",
    63: "Pluie",
    65: "Pluie forte",
    71: "Neige faible",
    73: "Neige",
    75: "Neige forte",
    80: "Averses faibles",
    81: "Averses",
    82: "Averses fortes",
    95: "Orage",
    96: "Orage grele",
    99: "Orage fort",
}

WEATHER_CODE_ICONS = {
    0: "☀",
    1: "☀",
    2: "⛅",
    3: "☁",
    45: "〰",
    48: "〰",
    51: "☂",
    53: "☂",
    55: "☂",
    61: "☔",
    63: "☔",
    65: "☔",
    71: "❄",
    73: "❄",
    75: "❄",
    80: "☔",
    81: "☔",
    82: "☔",
    95: "⚡",
    96: "⛈",
    99: "⛈",
}


def _fetch_open_meteo_payload() -> Dict:
    if APP_CONFIG["latitude"] is None or APP_CONFIG["longitude"] is None:
        raise ValueError("Forecast location is not configured")
    params = {
        "latitude": APP_CONFIG["latitude"],
        "longitude": APP_CONFIG["longitude"],
        "timezone": APP_CONFIG["timezone"],
        "forecast_days": 4,
        "current": [
            "temperature_2m",
            "precipitation",
            "weather_code",
            "wind_speed_10m",
            "wind_direction_10m",
        ],
        "hourly": [
            "temperature_2m",
            "precipitation",
            "weather_code",
            "wind_speed_10m",
            "wind_direction_10m",
        ],
        "daily": [
            "weather_code",
            "temperature_2m_max",
            "temperature_2m_min",
            "precipitation_sum",
            "wind_direction_10m_dominant",
            "wind_speed_10m_max",
            "sunrise",
            "sunset",
        ],
    }
    query = urlencode(params, doseq=True)
    with urlopen(OPEN_METEO_BASE_URL + "?" + query, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def _weather_label(code: Optional[int]) -> str:
    if code is None:
        return "-"
    return WEATHER_CODE_LABELS.get(int(code), str(code))


def _weather_icon(code: Optional[int]) -> str:
    if code is None:
        return "·"
    return WEATHER_CODE_ICONS.get(int(code), "☁")


def _compact_hour(value: str) -> str:
    return datetime.fromisoformat(value).strftime("%H:%M")


def _compact_day(value: str) -> str:
    return datetime.fromisoformat(value).strftime("%a %d")


def _format_wind_direction(value: Optional[float]) -> str:
    if value is None:
        return "-"
    return str(round(float(value)))


def get_forecast() -> Dict:
    now = time.time()
    if _forecast_cache["payload"] and now < float(_forecast_cache["expires_at"]):
        return _forecast_cache["payload"]  # type: ignore[return-value]

    if APP_CONFIG["latitude"] is None or APP_CONFIG["longitude"] is None:
        return {
            "location_label": APP_CONFIG["location_label"],
            "altitude_m": APP_CONFIG["altitude_m"],
            "configured": False,
            "current": {
                "temperature": "-",
                "rain": "-",
                "wind": "-",
                "direction": "-",
                "weather": "Localisation non configuree",
                "time": "-",
            },
            "next_hours": [],
            "daily_cards": [],
        }

    payload = _fetch_open_meteo_payload()
    current = payload.get("current", {})
    hourly = payload.get("hourly", {})
    daily = payload.get("daily", {})

    next_hours: List[Dict[str, str]] = []
    hourly_times = hourly.get("time", [])
    current_time = current.get("time")
    start_index = 0
    if current_time:
        current_dt = datetime.fromisoformat(current_time)
        for index, hour_value in enumerate(hourly_times):
            if datetime.fromisoformat(hour_value) >= current_dt:
                start_index = index
                break
    for index in range(start_index, min(start_index + 6, len(hourly_times))):
        hour_value = hourly_times[index]
        next_hours.append(
            {
                "time": _compact_hour(hour_value),
                "temperature": str(hourly["temperature_2m"][index]),
                "rain": str(hourly["precipitation"][index]),
                "wind": str(hourly["wind_speed_10m"][index]),
                "direction": _format_wind_direction(hourly["wind_direction_10m"][index]),
                "weather": _weather_label(hourly["weather_code"][index]),
                "icon": _weather_icon(hourly["weather_code"][index]),
            }
        )

    daily_cards: List[Dict[str, str]] = []
    daily_times = daily.get("time", [])
    for index, day_value in enumerate(daily_times[:4]):
        daily_cards.append(
            {
                "day": _compact_day(day_value),
                "weather": _weather_label(daily["weather_code"][index]),
                "temp_min": str(daily["temperature_2m_min"][index]),
                "temp_max": str(daily["temperature_2m_max"][index]),
                "rain": str(daily["precipitation_sum"][index]),
                "wind": str(daily["wind_speed_10m_max"][index]),
                "direction": _format_wind_direction(daily["wind_direction_10m_dominant"][index]),
                "sunrise": _compact_hour(daily["sunrise"][index]),
                "sunset": _compact_hour(daily["sunset"][index]),
                "icon": _weather_icon(daily["weather_code"][index]),
            }
        )

    forecast = {
        "location_label": APP_CONFIG["location_label"],
        "altitude_m": APP_CONFIG["altitude_m"],
        "configured": True,
        "current": {
            "temperature": str(current.get("temperature_2m", "-")),
            "rain": str(current.get("precipitation", "-")),
            "wind": str(current.get("wind_speed_10m", "-")),
            "direction": _format_wind_direction(current.get("wind_direction_10m")),
            "weather": _weather_label(current.get("weather_code")),
            "icon": _weather_icon(current.get("weather_code")),
            "time": current.get("time", "-"),
        },
        "next_hours": next_hours,
        "daily_cards": daily_cards,
    }
    _forecast_cache["payload"] = forecast
    _forecast_cache["expires_at"] = now + FORECAST_CACHE_SECONDS
    return forecast
