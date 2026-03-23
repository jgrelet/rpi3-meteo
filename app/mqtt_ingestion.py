from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Dict, Optional, Union

from paho.mqtt import client as mqtt_client

from app.air_quality import air_quality_estimator
from app.config import AIR_QUALITY
from app.config import INGESTION
from app.database import store_payload


logger = logging.getLogger(__name__)


class MqttIngestionService:
    def __init__(self) -> None:
        mqtt_cfg = INGESTION["mqtt"]
        self.enabled = mqtt_cfg.get("enabled", False)
        self.aggregated_topic = mqtt_cfg["aggregated_topic"]
        self.raw_topic = mqtt_cfg["raw_topic"]
        self.topics = [self.aggregated_topic, self.raw_topic]
        self.client = mqtt_client.Client(
            mqtt_client.CallbackAPIVersion.VERSION2,
            client_id=mqtt_cfg["client_id"],
        )
        if mqtt_cfg.get("user"):
            self.client.username_pw_set(mqtt_cfg["user"], mqtt_cfg.get("password"))
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect
        self.host = mqtt_cfg["broker"]
        self.port = mqtt_cfg["port"]
        self.keepalive = mqtt_cfg["keepalive"]
        self.connected = False
        self.last_message_at: Optional[str] = None
        self.last_error: Optional[str] = None

    def start(self) -> None:
        if not self.enabled:
            logger.info("MQTT ingestion disabled")
            return
        self.client.connect_async(self.host, self.port, self.keepalive)
        self.client.loop_start()
        logger.info("MQTT ingestion starting for %s:%s topics=%s", self.host, self.port, self.topics)

    def stop(self) -> None:
        if not self.enabled:
            return
        self.client.loop_stop()
        self.client.disconnect()

    def status(self) -> Dict[str, Union[str, bool, None]]:
        return {
            "enabled": self.enabled,
            "connected": self.connected,
            "aggregated_topic": self.aggregated_topic,
            "raw_topic": self.raw_topic,
            "last_message_at": self.last_message_at,
            "last_error": self.last_error,
        }

    def _on_connect(self, client, _userdata, _flags, reason_code, _properties) -> None:
        self.connected = reason_code == 0
        if self.connected:
            for topic in self.topics:
                client.subscribe(topic)
            self.last_error = None
            logger.info("MQTT connected and subscribed to %s", self.topics)
        else:
            self.last_error = f"connect_failed:{reason_code}"
            logger.warning("MQTT connection failed: %s", reason_code)

    def _on_disconnect(self, _client, _userdata, _disconnect_flags, reason_code, _properties) -> None:
        self.connected = False
        if reason_code != 0:
            self.last_error = f"disconnect:{reason_code}"
            logger.warning("MQTT disconnected: %s", reason_code)

    def _on_message(self, _client, _userdata, message) -> None:
        recorded_at = datetime.now(timezone.utc).isoformat()
        try:
            payload = json.loads(message.payload.decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("payload is not a JSON object")
            if AIR_QUALITY["enabled"]:
                payload = air_quality_estimator.enrich_payload(payload)
            store_payload(
                source="weather_web_sensors",
                channel="mqtt",
                topic=message.topic,
                payload=payload,
                recorded_at=recorded_at,
            )
            self.last_message_at = recorded_at
            self.last_error = None
        except Exception as exc:
            self.last_error = str(exc)
            logger.exception("MQTT payload processing failed: %s", exc)
