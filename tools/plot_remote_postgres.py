#!/usr/bin/env python3

import argparse
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
from psycopg import connect
from psycopg.rows import dict_row


DEFAULT_SENSORS = [
    "temperature_c",
    "humidity_pct",
    "pressure_hpa",
    "wind_speed_kmh",
    "rain_mm_total",
]

DEFAULT_COLORS = [
    "#2a9d8f",
    "#e76f51",
    "#264653",
    "#e9c46a",
    "#457b9d",
    "#8d99ae",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Query a remote PostgreSQL weather database and plot time series with matplotlib/numpy."
    )
    parser.add_argument("--host", default=os.getenv("RPI3_METEO_DB_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("RPI3_METEO_DB_PORT", "5432")))
    parser.add_argument("--dbname", default=os.getenv("RPI3_METEO_DB_NAME", "rpi3_meteo"))
    parser.add_argument("--user", default=os.getenv("RPI3_METEO_DB_USER", "rpi3_meteo"))
    parser.add_argument("--password", default=os.getenv("RPI3_METEO_DB_PASSWORD", "rpi3_meteo"))
    parser.add_argument("--hours", type=int, default=24, help="Window size in hours to query.")
    parser.add_argument(
        "--sensors",
        nargs="+",
        default=DEFAULT_SENSORS,
        help="Sensor names to plot. Example: temperature_c humidity_pct pressure_hpa",
    )
    parser.add_argument(
        "--export-mode",
        choices=["raw", "aggregated"],
        default="aggregated",
        help="Filter on the acquisition export mode.",
    )
    parser.add_argument(
        "--resolution",
        choices=["hourly", "raw"],
        default="hourly",
        help="Use hourly aggregates from the PostgreSQL view or raw sensor_readings samples.",
    )
    parser.add_argument(
        "--source",
        default=None,
        help="Optional source filter, for example weather_web_sensors.",
    )
    parser.add_argument(
        "--channel",
        default=None,
        help="Optional channel filter, for example mqtt.",
    )
    parser.add_argument(
        "--out",
        default="plots/weather_timeseries.png",
        help="Output PNG path.",
    )
    parser.add_argument("--title", default="RPi3 Meteo Remote Plots")
    parser.add_argument("--show", action="store_true", help="Display the figure on screen in addition to saving it.")
    return parser.parse_args()


def build_dsn(args: argparse.Namespace) -> str:
    return (
        f"host={args.host} "
        f"port={args.port} "
        f"dbname={args.dbname} "
        f"user={args.user} "
        f"password={args.password}"
    )


def fetch_series(args: argparse.Namespace) -> List[Dict]:
    recorded_after = datetime.now(timezone.utc) - timedelta(hours=args.hours)
    if args.resolution == "hourly":
        table_name = "hourly_sensor_stats"
        recorded_column = "recorded_hour"
        value_column = "avg_value"
    else:
        table_name = "sensor_series_numeric"
        recorded_column = "recorded_at"
        value_column = "numeric_value"

    predicates = [
        "{recorded_column} >= %(recorded_after)s".format(recorded_column=recorded_column),
        "sensor_name = ANY(%(sensor_names)s)",
        "export_mode = %(export_mode)s",
    ]
    params = {
        "recorded_after": recorded_after,
        "sensor_names": list(args.sensors),
        "export_mode": args.export_mode,
    }
    if args.source:
        predicates.append("source = %(source)s")
        params["source"] = args.source
    if args.channel:
        predicates.append("channel = %(channel)s")
        params["channel"] = args.channel

    query = """
    SELECT sensor_name, {value_column} AS numeric_value, unit, {recorded_column} AS recorded_at
    FROM {table_name}
    WHERE {where_clause}
    ORDER BY {recorded_column} ASC
    """.format(
        value_column=value_column,
        recorded_column=recorded_column,
        table_name=table_name,
        where_clause=" AND ".join(predicates),
    )

    with connect(build_dsn(args), row_factory=dict_row) as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchall()


def split_series(rows: Sequence[Dict]) -> Dict[str, Tuple[np.ndarray, np.ndarray, str]]:
    grouped: Dict[str, List[Tuple[datetime, float]]] = {}
    units: Dict[str, str] = {}
    for row in rows:
        sensor_name = row["sensor_name"]
        grouped.setdefault(sensor_name, []).append((row["recorded_at"], float(row["numeric_value"])))
        units[sensor_name] = row["unit"] or ""

    series: Dict[str, Tuple[np.ndarray, np.ndarray, str]] = {}
    for sensor_name, samples in grouped.items():
        dates = np.array([sample[0] for sample in samples], dtype=object)
        values = np.array([sample[1] for sample in samples], dtype=float)
        series[sensor_name] = (dates, values, units.get(sensor_name, ""))
    return series


def render_plot(args: argparse.Namespace, series: Dict[str, Tuple[np.ndarray, np.ndarray, str]]) -> Path:
    output_path = Path(args.out).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    sensor_names = [name for name in args.sensors if name in series]
    figure, axes = plt.subplots(len(sensor_names), 1, figsize=(14, 3.8 * max(len(sensor_names), 1)), sharex=True)
    if not isinstance(axes, np.ndarray):
        axes = np.array([axes])

    figure.patch.set_facecolor("#f7f3e9")
    for index, sensor_name in enumerate(sensor_names):
        ax = axes[index]
        dates, values, unit = series[sensor_name]
        color = DEFAULT_COLORS[index % len(DEFAULT_COLORS)]
        ax.plot(dates, values, color=color, linewidth=1.8)
        ax.fill_between(dates, values, np.min(values), color=color, alpha=0.08)
        ax.set_ylabel(unit or sensor_name)
        ax.set_title(sensor_name, loc="left", fontsize=11, fontweight="bold")
        ax.grid(True, linestyle=":", linewidth=0.7, alpha=0.6)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m %H:%M"))

    axes[-1].set_xlabel("Timestamp")
    figure.suptitle(args.title, fontsize=16, fontweight="bold", y=0.995)
    figure.autofmt_xdate()
    figure.tight_layout()
    figure.savefig(output_path, dpi=150, bbox_inches="tight")
    if args.show:
        plt.show()
    plt.close(figure)
    return output_path


def main() -> None:
    args = parse_args()
    rows = fetch_series(args)
    if not rows:
        raise SystemExit("No numeric sensor data found for the requested filters.")
    series = split_series(rows)
    output_path = render_plot(args, series)
    print(output_path)


if __name__ == "__main__":
    main()
