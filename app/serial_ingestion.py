from __future__ import annotations

import json
import logging
import queue
import threading
import time
import uuid
from datetime import datetime, timezone
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
        self._command_queue: queue.Queue[Dict[str, object]] = queue.Queue()
        self._command_lock = threading.Lock()
        self._last_command: Optional[Dict[str, object]] = None
        self._station_status: Optional[Dict[str, object]] = None
        self._last_auto_status_at = 0.0
        self._auto_status_retry_seconds = 60.0

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
            "last_command": self.last_command_status(),
            "station": self.station_status(),
        }

    def last_command_status(self) -> Optional[Dict[str, object]]:
        with self._command_lock:
            return dict(self._last_command) if self._last_command else None

    def station_status(self) -> Optional[Dict[str, object]]:
        with self._command_lock:
            return dict(self._station_status) if self._station_status else None

    def send_command(self, action: str, **parameters: object) -> Dict[str, object]:
        if not self.enabled:
            raise RuntimeError("HC-12 bridge is disabled")
        command = {
            "id": uuid.uuid4().hex[:12],
            "action": action,
            **parameters,
        }
        status = {
            "id": command["id"],
            "action": action,
            "status": "queued",
            "submitted_at": datetime.now(timezone.utc).isoformat(),
        }
        with self._command_lock:
            self._last_command = status
        self._command_queue.put(command)
        return dict(status)

    def _request_automatic_status(self) -> None:
        now = time.monotonic()
        with self._command_lock:
            if self._station_status is not None:
                return
            if now - self._last_auto_status_at < self._auto_status_retry_seconds:
                return
            self._last_auto_status_at = now
        command = {
            "id": uuid.uuid4().hex[:12],
            "action": "get_status",
        }
        self._command_queue.put(command)
        logger.info("HC-12 automatic station status requested")

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
            timeout=min(float(self.read_timeout_seconds), 0.2),
        ) as serial_port:
            self.serial_connected = True
            self.connected = self.mqtt_connected
            self.last_error = None
            logger.info("HC-12 serial port opened: %s", self.device)
            rx_buffer = bytearray()
            last_rx_at = 0.0
            while not self._stop_event.is_set():
                available = serial_port.in_waiting
                raw = serial_port.read(available or 1)
                if raw:
                    rx_buffer.extend(raw)
                    last_rx_at = time.monotonic()
                    while b"\n" in rx_buffer:
                        newline_index = rx_buffer.find(b"\n")
                        raw_line = bytes(rx_buffer[:newline_index])
                        rx_buffer = rx_buffer[newline_index + 1 :]
                        line = raw_line.decode("utf-8", errors="replace").strip()
                        if line:
                            self._handle_line(mqtt, line)
                if self._command_queue.qsize() and time.monotonic() - last_rx_at >= 0.3:
                    self._write_queued_command(serial_port)
                if len(rx_buffer) > 8192:
                    logger.error("HC-12 RX buffer overflow: %s bytes", len(rx_buffer))
                    rx_buffer = bytearray()
        self.serial_connected = False
        self.connected = False

    def _write_queued_command(self, serial_port) -> None:
        try:
            command = self._command_queue.get_nowait()
        except queue.Empty:
            return
        line = "CMD {}\n".format(json.dumps(command, separators=(",", ":")))
        serial_port.write(line.encode("utf-8"))
        serial_port.flush()
        with self._command_lock:
            if self._last_command and self._last_command.get("id") == command["id"]:
                self._last_command["status"] = "sent"
                self._last_command["sent_at"] = datetime.now(timezone.utc).isoformat()

    def _handle_line(self, mqtt: mqtt_client.Client, line: str) -> None:
        if line.startswith("ACK "):
            self._handle_ack(line)
            return
        self._bridge_line(mqtt, line)

    def _handle_ack(self, line: str) -> None:
        try:
            payload = json.loads(line[4:].strip())
            if not isinstance(payload, dict):
                raise ValueError("ACK payload is not a JSON object")
            with self._command_lock:
                result = payload.get("result")
                if isinstance(result, dict):
                    self._station_status = dict(result)
                if self._last_command and self._last_command.get("id") == payload.get("id"):
                    self._last_command["status"] = "acknowledged" if payload.get("ok") else "failed"
                    self._last_command["acknowledged_at"] = datetime.now(timezone.utc).isoformat()
                    self._last_command["response"] = payload
        except Exception as exc:
            self.last_error = "invalid_ack:{}".format(exc)
            logger.exception("HC-12 ACK processing failed: %s", exc)

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
            self._request_automatic_status()
        except Exception as exc:
            self.last_error = str(exc)
            logger.exception("HC-12 bridge payload processing failed: %s", exc)
