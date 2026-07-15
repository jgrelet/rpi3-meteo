from __future__ import annotations

import json
from typing import Dict, Tuple


def parse_hc12_line(
    line: str,
    raw_prefix: str = "JSON_RAW",
    aggregated_prefix: str = "JSON",
) -> Tuple[str, str, Dict[str, object]]:
    stripped = line.strip()
    if not stripped:
        raise ValueError("empty HC-12 line")

    prefixes = (
        (raw_prefix, "raw", "weather/sensors/raw"),
        (aggregated_prefix, "aggregated", "weather/sensors"),
    )
    for prefix, export_mode, topic in prefixes:
        marker = prefix + " "
        if stripped.startswith(marker):
            payload_json = stripped[len(marker) :].strip()
            payload = json.loads(payload_json)
            if not isinstance(payload, dict):
                raise ValueError("HC-12 payload is not a JSON object")
            payload.setdefault("export_mode", export_mode)
            return topic, export_mode, payload

    raise ValueError(f"unsupported HC-12 line prefix: {stripped[:32]!r}")
