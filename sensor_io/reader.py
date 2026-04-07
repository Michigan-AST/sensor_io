"""High-level sensor reading workflow.

If a teammate wants to know "what happens when we read the FC?", this file is
the answer. It coordinates the MSP transport and the payload parsers without
exposing lower-level framing details.
"""

from __future__ import annotations

import time

from .models import SensorSnapshot
from .msp import MSP_ALTITUDE, MSP_RAW_GPS, MSP_RAW_IMU, MspClient
from .parsers import parse_barometer_payload, parse_gps_payload, parse_imu_payload


def read_sensor_snapshot(client: MspClient) -> SensorSnapshot:
    """Read one complete set of sensor values from Betaflight."""

    # Read each message separately so the code mirrors the protocol at a glance.
    # This is slightly more verbose than a compact loop, but much easier to
    # understand when debugging sensor-specific issues.
    imu = parse_imu_payload(client.request(MSP_RAW_IMU))
    barometer = parse_barometer_payload(client.request(MSP_ALTITUDE))
    gps = parse_gps_payload(client.request(MSP_RAW_GPS))

    # Use one timestamp for the final combined snapshot so downstream code knows
    # when this batch of values was assembled.
    return SensorSnapshot(
        timestamp=time.time(),
        imu=imu,
        barometer=barometer,
        gps=gps,
    )
