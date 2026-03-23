from __future__ import annotations

import json
import logging
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
logger = logging.getLogger(__name__)
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
    "air_quality_relative_pct": ("Qualite air relative", "%"),
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
    return str(value).replace("T", " ")[:19]


def gas_quality(value: object) -> Dict[str, str] | None:
    try:
        gas_kohms = float(value)
    except (TypeError, ValueError):
        return None
    if gas_kohms >= 25:
        return {"label": "Bon", "class_name": "good", "hint": "Heuristique gaz eleve"}
    if gas_kohms >= 12:
        return {"label": "Moyen", "class_name": "medium", "hint": "Heuristique gaz intermediaire"}
    return {"label": "Degrade", "class_name": "poor", "hint": "Heuristique gaz faible"}


def relative_air_quality_status(value: object) -> Dict[str, str] | None:
    try:
        score_pct = float(value)
    except (TypeError, ValueError):
        return None
    if score_pct >= 80:
        return {"label": "Bon", "class_name": "good", "hint": "Score relatif local"}
    if score_pct >= 60:
        return {"label": "Correct", "class_name": "medium", "hint": "Score relatif local"}
    if score_pct >= 40:
        return {"label": "Moyen", "class_name": "medium", "hint": "Score relatif local"}
    return {"label": "Degrade", "class_name": "poor", "hint": "Score relatif local"}


def metric_cards_from_payload(payload_json: str | None) -> List[Dict[str, str]]:
    if not payload_json:
        return []
    try:
        payload = json.loads(payload_json)
    except (TypeError, ValueError) as exc:
        logger.warning("Unable to decode payload_json for metric cards: %s", exc)
        return []
    if not isinstance(payload, dict):
        logger.warning("Ignoring non-object payload for metric cards: %r", type(payload).__name__)
        return []
    keys = [
        ("temperature_c", "Temperature", "C"),
        ("humidity_pct", "Humidite", "%"),
        ("pressure_hpa", "Pression", "hPa"),
        ("gas_kohms", "Gaz", "kOhms"),
        ("air_quality_relative_pct", "Qualite air relative", "%"),
        ("wind_speed_kmh", "Vent", "km/h"),
        ("wind_dir_cardinal", "Direction", ""),
        ("rain_mm_total", "Pluie", "mm"),
    ]
    cards = []
    for key, label, unit in keys:
        if key in payload:
            gas_status = gas_quality(payload[key]) if key == "gas_kohms" else None
            relative_status = (
                relative_air_quality_status(payload[key])
                if key == "air_quality_relative_pct"
                else None
            )
            status = relative_status or gas_status
            cards.append(
                {
                    "label": label,
                    "value": str(payload[key]),
                    "unit": unit,
                    "status_label": status["label"] if status else "",
                    "status_class": status["class_name"] if status else "",
                    "status_hint": status["hint"] if status else "",
                }
            )
    return cards


def template_context(request: Request) -> Dict[str, object]:
    return {
        "request": request,
        "title": UI["title"],
        "refresh_seconds": UI["refresh_seconds"],
        "pages": nav_pages(),
    }


def render_error_page(request: Request, title: str, detail: str) -> HTMLResponse:
    return HTMLResponse(
        """
        <!DOCTYPE html>
        <html lang="fr">
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <meta http-equiv="refresh" content="{refresh_seconds}">
            <title>{title}</title>
            <link rel="stylesheet" href="/static/app.css">
        </head>
        <body>
            <main class="layout">
                <section class="panel">
                    <div class="panel-head">
                        <h1>{title}</h1>
                        <span>Mode degrade</span>
                    </div>
                    <p>{detail}</p>
                    <p>La page va se recharger automatiquement.</p>
                    <p><a href="{path}">Recharger maintenant</a></p>
                </section>
            </main>
        </body>
        </html>
        """.format(
            refresh_seconds=UI["refresh_seconds"],
            title=title,
            detail=detail,
            path=request.url.path,
        ),
        status_code=503,
    )


def split_reduced_stats(stats: List[Dict]) -> Dict[str, List[Dict[str, str]]]:
    primary_by_sensor: Dict[str, Dict[str, str]] = {}
    secondary = []
    for row in stats:
        sensor_name = row["sensor_name"]
        if sensor_name in PRIMARY_REDUCED_METRICS:
            label, unit = PRIMARY_REDUCED_METRICS[sensor_name]
            gas_status = gas_quality(row["avg_value"]) if sensor_name == "gas_kohms" else None
            relative_status = (
                relative_air_quality_status(row["avg_value"])
                if sensor_name == "air_quality_relative_pct"
                else None
            )
            status = relative_status or gas_status
            primary_by_sensor[sensor_name] = {
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
                "status_label": status["label"] if status else "",
                "status_class": status["class_name"] if status else "",
                "status_hint": status["hint"] if status else "",
            }
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
    primary = [
        primary_by_sensor[sensor_name]
        for sensor_name in PRIMARY_REDUCED_METRICS
        if sensor_name in primary_by_sensor
    ]
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
    try:
        latest_readings = fetch_latest_readings(export_mode="aggregated")
        if not latest_readings:
            latest_readings = fetch_latest_readings(export_mode="raw")
        latest_raw = fetch_latest_messages(limit=1, export_mode="raw")
        latest_aggregated = fetch_latest_messages(limit=1, export_mode="aggregated")
        context = template_context(request)
        context.update(
            {
                "latest_readings": latest_readings,
                "raw_cards": metric_cards_from_payload(latest_raw[0]["payload_json"]) if latest_raw else [],
                "aggregated_cards": metric_cards_from_payload(latest_aggregated[0]["payload_json"]) if latest_aggregated else [],
                "latest_raw_at": compact_timestamp(latest_raw[0]["recorded_at"]) if latest_raw else "-",
                "latest_aggregated_at": compact_timestamp(latest_aggregated[0]["recorded_at"]) if latest_aggregated else "-",
                "mqtt_status": mqtt_service.status(),
            }
        )
        return templates.TemplateResponse("overview.html", context)
    except Exception:
        logger.exception("Failed to render overview page")
        return render_error_page(
            request,
            UI["title"],
            "Une erreur temporaire s'est produite pendant le chargement des donnees meteo.",
        )


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
        try:
            messages = fetch_latest_messages(export_mode="raw")
            context = template_context(request)
            context.update(
                {
                    "messages": messages,
                    "raw_cards": metric_cards_from_payload(messages[0]["payload_json"]) if messages else [],
                    "latest_raw_at": compact_timestamp(messages[0]["recorded_at"]) if messages else "-",
                }
            )
            return templates.TemplateResponse("raw_data.html", context)
        except Exception:
            logger.exception("Failed to render raw-data page")
            return render_error_page(
                request,
                UI["title"],
                "Les messages MQTT bruts sont temporairement indisponibles.",
            )
    if page_name == "reduced-data":
        try:
            stats = fetch_reduced_stats(export_mode="aggregated")
            split_stats = split_reduced_stats(stats)
            context = template_context(request)
            context.update(
                {
                    "primary_stats": split_stats["primary"],
                    "secondary_stats": split_stats["secondary"],
                }
            )
            return templates.TemplateResponse("reduced_data.html", context)
        except Exception:
            logger.exception("Failed to render reduced-data page")
            return render_error_page(
                request,
                UI["title"],
                "Les statistiques reduites sont temporairement indisponibles.",
            )
    if page_name in {"forecast", "forecast-now", "forecast-hours", "forecast-days"}:
        try:
            forecast = get_forecast()
            context = template_context(request)
            context.update(
                {
                    "forecast_provider": APP_CONFIG["default_forecast_provider"],
                    "latitude": APP_CONFIG["latitude"],
                    "longitude": APP_CONFIG["longitude"],
                    "forecast": forecast,
                    "forecast_page": "forecast-now" if page_name == "forecast" else page_name,
                }
            )
            return templates.TemplateResponse("forecast.html", context)
        except Exception:
            logger.exception("Failed to render forecast page")
            return render_error_page(
                request,
                UI["title"],
                "La prevision meteo externe est temporairement indisponible.",
            )
    return {"page": page_name, "status": "todo"}
