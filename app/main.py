from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Dict, Union

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
from app.mqtt_ingestion import MqttIngestionService


templates = Jinja2Templates(directory="app/templates")
mqtt_service = MqttIngestionService()


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
    latest_readings = fetch_latest_readings()
    context = {
        "request": request,
        "title": UI["title"],
        "refresh_seconds": UI["refresh_seconds"],
        "pages": UI["pages"],
        "latest_readings": latest_readings,
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
        messages = fetch_latest_messages()
        return templates.TemplateResponse(
            "raw_data.html",
            {
                "request": request,
                "title": UI["title"],
                "refresh_seconds": UI["refresh_seconds"],
                "pages": UI["pages"],
                "messages": messages,
            },
        )
    if page_name == "reduced-data":
        stats = fetch_reduced_stats()
        return templates.TemplateResponse(
            "reduced_data.html",
            {
                "request": request,
                "title": UI["title"],
                "refresh_seconds": UI["refresh_seconds"],
                "pages": UI["pages"],
                "stats": stats,
            },
        )
    if page_name == "forecast":
        return templates.TemplateResponse(
            "forecast.html",
            {
                "request": request,
                "title": UI["title"],
                "refresh_seconds": UI["refresh_seconds"],
                "pages": UI["pages"],
                "forecast_provider": APP_CONFIG["default_forecast_provider"],
                "latitude": APP_CONFIG["latitude"],
                "longitude": APP_CONFIG["longitude"],
            },
        )
    return {"page": page_name, "status": "todo"}
