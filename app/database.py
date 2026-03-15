from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from app.config import DATABASE


CREATE_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS raw_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    channel TEXT NOT NULL,
    topic TEXT,
    payload_json TEXT NOT NULL,
    recorded_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sensor_readings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    channel TEXT NOT NULL,
    sensor_name TEXT NOT NULL,
    numeric_value REAL,
    text_value TEXT,
    unit TEXT,
    recorded_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sensor_readings_recorded_at
ON sensor_readings(recorded_at);

CREATE INDEX IF NOT EXISTS idx_sensor_readings_sensor_name
ON sensor_readings(sensor_name);

CREATE INDEX IF NOT EXISTS idx_raw_messages_recorded_at
ON raw_messages(recorded_at);
"""


def _connect_sync() -> sqlite3.Connection:
    return sqlite3.connect(DATABASE["path"])


def _guess_unit(sensor_name: str) -> Optional[str]:
    suffix_to_unit = {
        "_temperature_c": "C",
        "_pressure_hpa": "hPa",
        "_humidity_pct": "%",
        "_speed_kmh": "km/h",
        "_gas_kohms": "kOhms",
        "_rain_mm": "mm",
        "_rain_mm_total": "mm",
        "_dir_deg": "deg",
    }
    for suffix, unit in suffix_to_unit.items():
        if sensor_name.endswith(suffix):
            return unit
    return None


def _normalize_payload(payload: Dict) -> List[Tuple[str, Optional[float], Optional[str], Optional[str]]]:
    readings = []
    for key, value in payload.items():
        if key == "timestamp":
            continue
        if key.startswith("error_"):
            readings.append((key, None, str(value), None))
            continue
        if isinstance(value, bool):
            readings.append((key, float(value), None, None))
            continue
        if isinstance(value, (int, float)):
            readings.append((key, float(value), None, _guess_unit(key)))
            continue
        if isinstance(value, str):
            readings.append((key, None, value, _guess_unit(key)))
    return readings


def init_db() -> None:
    db_path = Path(DATABASE["path"])
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as connection:
        connection.executescript(CREATE_SCHEMA_SQL)
        connection.commit()


def store_payload(source: str, channel: str, topic: Optional[str], payload: Dict, recorded_at: str) -> None:
    rows = _normalize_payload(payload)
    with _connect_sync() as connection:
        connection.execute(
            """
            INSERT INTO raw_messages(source, channel, topic, payload_json, recorded_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (source, channel, topic, json.dumps(payload), recorded_at),
        )
        connection.executemany(
            """
            INSERT INTO sensor_readings(
                source, channel, sensor_name, numeric_value, text_value, unit, recorded_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (source, channel, sensor_name, numeric_value, text_value, unit, recorded_at)
                for sensor_name, numeric_value, text_value, unit in rows
            ],
        )
        connection.commit()


def fetch_latest_readings(limit: int = 25) -> List[Dict]:
    query = """
    SELECT source, channel, sensor_name, numeric_value, text_value, unit, recorded_at
    FROM sensor_readings
    ORDER BY recorded_at DESC
    LIMIT ?
    """
    with sqlite3.connect(DATABASE["path"]) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(query, (limit,)).fetchall()
    return [dict(row) for row in rows]


def fetch_latest_messages(limit: int = 20) -> List[Dict]:
    query = """
    SELECT source, channel, topic, payload_json, recorded_at
    FROM raw_messages
    ORDER BY recorded_at DESC
    LIMIT ?
    """
    with sqlite3.connect(DATABASE["path"]) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(query, (limit,)).fetchall()
    return [dict(row) for row in rows]


def fetch_reduced_stats() -> List[Dict]:
    query = """
    SELECT
        sensor_name,
        unit,
        COUNT(*) AS samples,
        ROUND(AVG(numeric_value), 2) AS avg_value,
        ROUND(MIN(numeric_value), 2) AS min_value,
        ROUND(MAX(numeric_value), 2) AS max_value,
        MAX(recorded_at) AS last_seen
    FROM sensor_readings
    WHERE numeric_value IS NOT NULL
    GROUP BY sensor_name, unit
    ORDER BY sensor_name
    """
    with sqlite3.connect(DATABASE["path"]) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(query).fetchall()
    return [dict(row) for row in rows]
