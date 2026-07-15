#!/usr/bin/env python3
from __future__ import annotations

import argparse
import time
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import serial


PARIS_TZ = ZoneInfo("Europe/Paris")


def timestamp_label() -> str:
    now_utc = datetime.now(UTC).replace(microsecond=0)
    now_local = now_utc.astimezone(PARIS_TZ)
    return "{} UTC / {} Europe/Paris".format(
        now_utc.replace(tzinfo=None).isoformat(),
        now_local.replace(microsecond=0).isoformat(),
    )


def open_serial(args: argparse.Namespace) -> serial.Serial:
    return serial.Serial(args.device, args.baudrate, timeout=args.timeout)


def send_loop(args: argparse.Namespace) -> None:
    with open_serial(args) as serial_port:
        counter = 0
        next_send = time.monotonic()
        while True:
            now = time.monotonic()
            if now >= next_send:
                counter += 1
                message = "PING_RPI {} {}".format(counter, int(time.time()))
                serial_port.write((message + "\n").encode("utf-8"))
                serial_port.flush()
                print("[{}] sent: {}".format(timestamp_label(), message))
                next_send = now + args.interval

            line = serial_port.readline()
            if line:
                decoded = line.decode("utf-8", errors="replace").strip()
                if decoded:
                    print("[{}] received: {}".format(timestamp_label(), decoded))


def receive_loop(args: argparse.Namespace) -> None:
    with open_serial(args) as serial_port:
        while True:
            line = serial_port.readline()
            if not line:
                continue
            decoded = line.decode("utf-8", errors="replace").strip()
            print("[{}] received: {}".format(timestamp_label(), decoded))
            if args.echo:
                response = "ACK_RPI {}".format(decoded)
                serial_port.write((response + "\n").encode("utf-8"))
                serial_port.flush()
                print("[{}] sent: {}".format(timestamp_label(), response))


def main() -> None:
    parser = argparse.ArgumentParser(description="Test bidirectional HC-12 UART from Raspberry Pi")
    parser.add_argument("--device", default="/dev/serial0", help="Serial device, default /dev/serial0")
    parser.add_argument("--baudrate", type=int, default=9600, help="UART baudrate, default 9600")
    parser.add_argument("--timeout", type=float, default=1.0, help="Read timeout in seconds")
    parser.add_argument("--interval", type=float, default=2.0, help="Send interval in seconds")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--send", action="store_true", help="Send PING_RPI lines and print received replies")
    mode.add_argument("--receive", action="store_true", help="Receive and print lines forever")
    mode.add_argument("--echo", action="store_true", help="Receive lines and reply with ACK_RPI")
    args = parser.parse_args()

    if args.send:
        send_loop(args)
    else:
        receive_loop(args)


if __name__ == "__main__":
    main()
