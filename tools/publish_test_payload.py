#!/usr/bin/env python3

import argparse
import json
import time

import paho.mqtt.publish as publish


def build_payload() -> dict:
    return {
        "timestamp": int(time.time()),
        "temperature_c": 20.11,
        "humidity_pct": 59.54,
        "pressure_hpa": 978.34,
        "wind_speed_kmh": 0.0,
        "wind_dir_cardinal": "W",
        "wind_dir_deg": 270.0,
        "rain_mm_total": 0.0,
        "sensor_bme680_temperature_c": 20.11,
        "sensor_bme680_humidity_pct": 59.54,
        "sensor_bme680_pressure_hpa": 978.34,
        "sensor_aht20_temperature_c": 20.77,
        "sensor_aht20_humidity_pct": 64.15,
        "sensor_dht22_temperature_c": 20.60,
        "sensor_dht22_humidity_pct": 59.30,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish a sample weather payload to MQTT.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=1883)
    parser.add_argument("--topic", default=None)
    parser.add_argument("--export-mode", choices=["raw", "aggregated"], default="raw")
    args = parser.parse_args()

    payload = build_payload()
    payload["export_mode"] = args.export_mode
    topic = args.topic or ("weather/sensors/raw" if args.export_mode == "raw" else "weather/sensors")
    publish.single(
        topic=topic,
        payload=json.dumps(payload),
        hostname=args.host,
        port=args.port,
    )
    print(json.dumps(payload, ensure_ascii=True))


if __name__ == "__main__":
    main()
