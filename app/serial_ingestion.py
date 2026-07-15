from __future__ import annotations

import json
import logging
import threading
from typing import Dict, Optional, Union

from paho.mqtt import client as mqtt_client

try:
    import serial
except ImportError:  # pragma: no cover - exercised only when dependency is missing at runtime.
    serial = None

from app.config import INGESTION
from app.hc12_protocol import parse_hc12_line


logger = logging.getLogger(__name__)


class Hc12MqttBridgeService:
    def __init__(self) -> None:
        hc12_cfg = INGESTION["hc12"]
        mqtt_cfg = INGESTION["mqtt"]
        self.enabled = INGESTION["transmission_mode"] == "hc-12"
        self.device = hc12_cfg["device"]
        self.baudrate = hc12_cfg["baudrate"]
        self.raw_prefix = hc12_cfg["raw_prefix"]
        self.aggregated_prefix = hc12_cfg["aggregated_prefix"]
        self.read_timeout_seconds = hc12_cfg["read_timeout_seconds"]
        self.reconnect_seconds = hc12_cfg["reconnect_seconds"]
        self.mqtt_host = mqtt_cfg["broker"]
        self.mqtt_port = mqtt_cfg["port"]
        self.mqtt_keepalive = mqtt_cfg["keepalive"]
        self.mqtt_qos = mqtt_cfg["qos"]
        self.mqtt_user = mqtt_cfg.get("user")
        self.mqtt_password = mqtt_cfg.get("password")
        self.mqtt_client_id = hc12_cfg["mqtt_client_id"]
        self.connected = False
        self.serial_connected = False
        self.mqtt_connected = False
        self.last_message_at: Optional[str] = None
        self.last_error: Optional[str] = None
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._mqtt_client: Optional[mqtt_client.Client] = None

    def start(self) -> None:
        if not self.enabled:
            logger.info("HC-12 MQTT bridge disabled")
            return
        if serial is None:
            self.last_error = "pyserial_missing"
            logger.error("HC-12 MQTT bridge requires pyserial")
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name="hc12-mqtt-bridge", daemon=True)
        self._thread.start()
        logger.info(
            "HC-12 MQTT bridge starting on %s at %s baud -> %s:%s",
            self.device,
            self.baudrate,
            self.mqtt_host,
            self.mqtt_port,
        )

    def stop(self) -> None:
        if not self.enabled:
            return
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)
        self._disconnect_mqtt()

    def status(self) -> Dict[str, Union[str, bool, int, None]]:
        return {
            "enabled": self.enabled,
            "connected": self.connected,
            "serial_connected": self.serial_connected,
            "mqtt_connected": self.mqtt_connected,
            "device": self.device,
            "baudrate": self.baudrate,
            "mqtt_host": self.mqtt_host,
            "mqtt_port": self.mqtt_port,
            "last_message_at": self.last_message_at,
            "last_error": self.last_error,
        }

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._read_loop()
            except Exception as exc:
                self.connected = False
                self.serial_connected = False
                self.last_error = str(exc)
                logger.exception("HC-12 MQTT bridge failed: %s", exc)
                self._disconnect_mqtt()
                self._stop_event.wait(self.reconnect_seconds)

    def _connect_mqtt(self) -> mqtt_client.Client:
        if self._mqtt_client:
            return self._mqtt_client
        client = mqtt_client.Client(
            mqtt_client.CallbackAPIVersion.VERSION2,
            client_id=self.mqtt_client_id,
        )
        if self.mqtt_user:
            client.username_pw_set(self.mqtt_user, self.mqtt_password)
        client.on_connect = self._on_mqtt_connect
        client.on_disconnect = self._on_mqtt_disconnect
        client.connect(self.mqtt_host, self.mqtt_port, self.mqtt_keepalive)
        client.loop_start()
        self._mqtt_client = client
        return client

    def _disconnect_mqtt(self) -> None:
        if not self._mqtt_client:
            self.mqtt_connected = False
            self.connected = False
            return
        self._mqtt_client.loop_stop()
        self._mqtt_client.disconnect()
        self._mqtt_client = None
        self.mqtt_connected = False
        self.connected = False

    def _on_mqtt_connect(self, _client, _userdata, _flags, reason_code, _properties) -> None:
        self.mqtt_connected = reason_code == 0
        self.connected = self.serial_connected and self.mqtt_connected
        if self.mqtt_connected:
            self.last_error = None
            logger.info("HC-12 bridge connected to MQTT broker")
        else:
            self.last_error = f"mqtt_connect_failed:{reason_code}"
            logger.warning("HC-12 bridge MQTT connection failed: %s", reason_code)

    def _on_mqtt_disconnect(self, _client, _userdata, _disconnect_flags, reason_code, _properties) -> None:
        self.mqtt_connected = False
        self.connected = False
        if reason_code != 0:
            self.last_error = f"mqtt_disconnect:{reason_code}"
            logger.warning("HC-12 bridge MQTT disconnected: %s", reason_code)

    def _read_loop(self) -> None:
        assert serial is not None
        mqtt = self._connect_mqtt()
        with serial.Serial(
            self.device,
            self.baudrate,
            timeout=self.read_timeout_seconds,
        ) as serial_port:
            self.serial_connected = True
            self.connected = self.mqtt_connected
            self.last_error = None
            logger.info("HC-12 serial port opened: %s", self.device)
            while not self._stop_event.is_set():
                raw_line = serial_port.readline()
                if not raw_line:
                    continue
                line = raw_line.decode("utf-8", errors="replace")
                self._bridge_line(mqtt, line)
        self.serial_connected = False
        self.connected = False

    def _bridge_line(self, mqtt: mqtt_client.Client, line: str) -> None:
        try:
            topic, _export_mode, payload = parse_hc12_line(
                line,
                raw_prefix=self.raw_prefix,
                aggregated_prefix=self.aggregated_prefix,
            )
            info = mqtt.publish(topic, json.dumps(payload), qos=self.mqtt_qos)
            if info.rc != mqtt_client.MQTT_ERR_SUCCESS:
                raise RuntimeError(f"mqtt_publish_failed:{info.rc}")
            self.last_message_at = payload.get("timestamp")
            self.last_error = None
        except Exception as exc:
            self.last_error = str(exc)
            logger.exception("HC-12 bridge payload processing failed: %s", exc)
