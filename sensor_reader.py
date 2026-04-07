#!/usr/bin/env python3
"""CLI entry point for reading Betaflight sensor data over MSP.

The project is intentionally split into small modules:
- `sensor_io.msp`: serial transport and MSP framing
- `sensor_io.parsers`: raw payload decoding
- `sensor_io.reader`: the high-level "read everything once" workflow
- `sensor_io.output`: text and JSON formatting

This file stays focused on command-line behavior so it reads top-to-bottom like
an operations script.
"""

from __future__ import annotations

import argparse
import sys
import time
from typing import Optional

import serial

from sensor_io.msp import MspClient, MspError
from sensor_io.output import snapshot_to_json, snapshot_to_text
from sensor_io.reader import read_sensor_snapshot


def parse_args() -> argparse.Namespace:
    """Define and parse CLI arguments."""

    # Keep the command-line interface (CLI, meaning "command-line interface")
    # compact so operators can discover the script behavior with `--help`.
    parser = argparse.ArgumentParser(
        description=(
            "Read IMU, magnetometer, GPS, and barometer-derived altitude from "
            "Betaflight over MSP."
        )
    )
    parser.add_argument(
        "--port",
        required=True,
        help="Serial device path, for example /dev/tty.usbmodem12301",
    )
    parser.add_argument(
        "--baudrate",
        type=int,
        default=115200,
        help="Serial baudrate. Default: 115200",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=1.0,
        help="Serial read timeout in seconds. Default: 1.0",
    )
    parser.add_argument(
        "--rate",
        type=float,
        default=2.0,
        help="Polling rate in Hz for streaming mode. Default: 2.0",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=1,
        help="Number of samples to read. Use 0 to stream until interrupted. Default: 1",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit each sample as one JSON object",
    )
    return parser.parse_args()


def calculate_poll_interval(rate_hz: float) -> float:
    """Translate a rate in Hz into a sleep interval in seconds."""

    # A non-positive rate means "do not throttle the loop".
    if rate_hz <= 0:
        return 0.0
    return 1.0 / rate_hz


def emit_snapshot(client: MspClient, as_json: bool) -> None:
    """Read one snapshot and print it in the requested format."""

    # This helper keeps the top-level loop easy to scan: read once, format once,
    # print once.
    snapshot = read_sensor_snapshot(client)
    if as_json:
        # JSON (JavaScript Object Notation, a common text data format) is useful
        # when another program will consume the output.
        print(snapshot_to_json(snapshot))
        return

    # The text path is aimed at humans watching the terminal directly.
    print(snapshot_to_text(snapshot))
    print()


def run_loop(
    *,
    port: str,
    baudrate: int,
    timeout: float,
    count: int,
    rate_hz: float,
    as_json: bool,
) -> int:
    """Open the serial port and read one or more sensor snapshots."""

    poll_interval = calculate_poll_interval(rate_hz)
    # `count=0` means "run forever" until the user stops the script.
    remaining_reads: Optional[int] = None if count == 0 else count

    with MspClient(port=port, baudrate=baudrate, timeout=timeout) as client:
        while remaining_reads is None or remaining_reads > 0:
            # `monotonic()` is a clock that only moves forward, so it is safer
            # for loop timing than wall-clock time.
            started_at = time.monotonic()
            emit_snapshot(client, as_json=as_json)

            if remaining_reads is not None:
                remaining_reads -= 1

            # Sleep only long enough to honor the requested poll rate.
            wait_before_next_read(started_at=started_at, poll_interval=poll_interval)

    return 0


def wait_before_next_read(*, started_at: float, poll_interval: float) -> None:
    """Sleep until the next polling slot, if one is needed."""

    # A zero interval means "start the next read immediately".
    if poll_interval <= 0:
        return

    elapsed = time.monotonic() - started_at
    remaining = poll_interval - elapsed
    # If the sensor read already took longer than the target interval, skip
    # sleeping and continue right away.
    if remaining > 0:
        time.sleep(remaining)


def main() -> int:
    # `main()` is intentionally short so the high-level script behavior is clear:
    # parse input, run the loop, translate failures into exit codes.
    args = parse_args()

    try:
        return run_loop(
            port=args.port,
            baudrate=args.baudrate,
            timeout=args.timeout,
            count=args.count,
            rate_hz=args.rate,
            as_json=args.json,
        )
    except KeyboardInterrupt:
        # Exit code 130 is the standard "terminated by Ctrl+C" convention.
        return 130
    except (serial.SerialException, MspError) as exc:
        # Print errors to stderr (standard error, the normal stream for failures)
        # so stdout (standard output) stays clean for data consumers.
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
