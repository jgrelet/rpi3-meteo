from __future__ import annotations

import json
from contextlib import asynccontextmanager
from typing import Dict, List, Union

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import APP_CONFIG, UI
from app.database import (
    fetch_latest_messages,
    fetch_latest_readings,
    fetch_reduced_stats,
    init_db,
)
from app.forecast import get_forecast
from app.mqtt_ingestion import MqttIngestionService


templates = Jinja2Templates(directory="app/templates")
mqtt_service = MqttIngestionService()
PAGE_LABELS = {
    "overview": "Accueil",
    "raw-data": "Temps reel",
    "reduced-data": "Synthese",
    "forecast-now": "Maintenant",
    "forecast-hours": "Prochaines heures",
    "forecast-days": "4 jours",
}
PRIMARY_REDUCED_METRICS = {
    "temperature_c": ("Temperature", "C"),
    "humidity_pct": ("Humidite", "%"),
    "pressure_hpa": ("Pression", "hPa"),
    "gas_kohms": ("Gaz", "kOhms"),
    "wind_speed_kmh": ("Vent", "km/h"),
    "wind_dir_deg": ("Direction", "deg"),
    "rain_mm_total": ("Pluie", "mm"),
}


def nav_pages() -> List[Dict[str, str]]:
    pages = []
    for page in UI["pages"]:
        pages.append(
            {
                "id": page,
                "label": PAGE_LABELS.get(page, page),
                "href": "/" if page == "overview" else "/pages/" + page,
            }
        )
    return pages


def compact_timestamp(value: str | None) -> str:
    if not value:
        return "-"
    return value.replace("T", " ")[:19]


def metric_cards_from_payload(payload_json: str | None) -> List[Dict[str, str]]:
    if not payload_json:
        return []
    payload = json.loads(payload_json)
    keys = [
        ("temperature_c", "Temperature", "C"),
        ("humidity_pct", "Humidite", "%"),
        ("pressure_hpa", "Pression", "hPa"),
        ("gas_kohms", "Gaz", "kOhms"),
        ("wind_speed_kmh", "Vent", "km/h"),
        ("wind_dir_cardinal", "Direction", ""),
        ("rain_mm_total", "Pluie", "mm"),
    ]
    cards = []
    for key, label, unit in keys:
        if key in payload:
            cards.append(
                {
                    "label": label,
                    "value": str(payload[key]),
                    "unit": unit,
                }
            )
    return cards


def split_reduced_stats(stats: List[Dict]) -> Dict[str, List[Dict[str, str]]]:
    primary = []
    secondary = []
    for row in stats:
        sensor_name = row["sensor_name"]
        if sensor_name in PRIMARY_REDUCED_METRICS:
            label, unit = PRIMARY_REDUCED_METRICS[sensor_name]
            primary.append(
                {
                    "label": label,
                    "value": str(row["avg_value"]),
                    "unit": unit or row["unit"] or "",
                    "mean_value": str(row["mean_value"]),
                    "median_value": str(row["median_value"]),
                    "stddev_value": str(row["stddev_value"]),
                    "samples": str(row["samples"]),
                    "min_value": str(row["min_value"]),
                    "max_value": str(row["max_value"]),
                    "last_seen": compact_timestamp(row["last_seen"]),
                }
            )
        elif sensor_name.startswith("aggregation_") or sensor_name in {"export_interval_seconds"}:
            continue
        else:
            secondary.append(
                {
                    "sensor_name": sensor_name,
                    "samples": row["samples"],
                    "avg_value": row["avg_value"],
                    "min_value": row["min_value"],
                    "max_value": row["max_value"],
                    "unit": row["unit"] or "",
                    "last_seen": compact_timestamp(row["last_seen"]),
                }
            )
    return {"primary": primary, "secondary": secondary}


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    mqtt_service.start()
    yield
    mqtt_service.stop()


app = FastAPI(title=UI["title"], lifespan=lifespan)
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/", response_class=HTMLResponse)
async def overview(request: Request) -> HTMLResponse:
    latest_readings = fetch_latest_readings(export_mode="aggregated")
    if not latest_readings:
        latest_readings = fetch_latest_readings(export_mode="raw")
    latest_raw = fetch_latest_messages(limit=1, export_mode="raw")
    latest_aggregated = fetch_latest_messages(limit=1, export_mode="aggregated")
    context = {
        "request": request,
        "title": UI["title"],
        "refresh_seconds": UI["refresh_seconds"],
        "pages": nav_pages(),
        "latest_readings": latest_readings,
        "raw_cards": metric_cards_from_payload(latest_raw[0]["payload_json"]) if latest_raw else [],
        "aggregated_cards": metric_cards_from_payload(latest_aggregated[0]["payload_json"]) if latest_aggregated else [],
        "latest_raw_at": compact_timestamp(latest_raw[0]["recorded_at"]) if latest_raw else "-",
        "latest_aggregated_at": compact_timestamp(latest_aggregated[0]["recorded_at"]) if latest_aggregated else "-",
        "mqtt_status": mqtt_service.status(),
    }
    return templates.TemplateResponse("overview.html", context)


@app.get("/health")
async def health() -> Dict[str, Union[str, bool]]:
    return {
        "status": "ok",
        "debug": APP_CONFIG["debug"],
        "forecast_provider": APP_CONFIG["default_forecast_provider"],
    }


@app.get("/pages/{page_name}")
async def page_placeholder(request: Request, page_name: str):
    if page_name == "raw-data":
        messages = fetch_latest_messages(export_mode="raw")
        return templates.TemplateResponse(
            "raw_data.html",
            {
                "request": request,
                "title": UI["title"],
                "refresh_seconds": UI["refresh_seconds"],
                "pages": nav_pages(),
                "messages": messages,
                "raw_cards": metric_cards_from_payload(messages[0]["payload_json"]) if messages else [],
                "latest_raw_at": compact_timestamp(messages[0]["recorded_at"]) if messages else "-",
            },
        )
    if page_name == "reduced-data":
        stats = fetch_reduced_stats(export_mode="aggregated")
        split_stats = split_reduced_stats(stats)
        return templates.TemplateResponse(
            "reduced_data.html",
            {
                "request": request,
                "title": UI["title"],
                "refresh_seconds": UI["refresh_seconds"],
                "pages": nav_pages(),
                "primary_stats": split_stats["primary"],
                "secondary_stats": split_stats["secondary"],
            },
        )
    if page_name in {"forecast", "forecast-now", "forecast-hours", "forecast-days"}:
        forecast = get_forecast()
        return templates.TemplateResponse(
            "forecast.html",
            {
                "request": request,
                "title": UI["title"],
                "refresh_seconds": UI["refresh_seconds"],
                "pages": nav_pages(),
                "forecast_provider": APP_CONFIG["default_forecast_provider"],
                "latitude": APP_CONFIG["latitude"],
                "longitude": APP_CONFIG["longitude"],
                "forecast": forecast,
                "forecast_page": "forecast-now" if page_name == "forecast" else page_name,
            },
        )
    return {"page": page_name, "status": "todo"}
