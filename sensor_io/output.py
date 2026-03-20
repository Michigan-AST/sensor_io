"""Formatting helpers for CLI output."""

from __future__ import annotations

import json

from .models import SensorSnapshot


def snapshot_to_json(snapshot: SensorSnapshot) -> str:
    """Serialize one sensor snapshot as JSON."""

    # The dataclass tree is converted to plain dictionaries before JSON encoding.
    return json.dumps(snapshot.to_dict())


def snapshot_to_text(snapshot: SensorSnapshot) -> str:
    """Render one sensor snapshot in a simple human-readable layout."""

    # Pull the nested objects into short local names so the string formatting
    # below stays readable.
    imu = snapshot.imu
    barometer = snapshot.barometer
    gps = snapshot.gps

    # Build the output as a list of lines first. That makes the layout easy to
    # edit without mixing lots of `print()` calls into the formatting logic.
    lines = [
        "IMU",
        f"  accel: x={imu.accel_x} y={imu.accel_y} z={imu.accel_z}",
        f"  gyro_dps: x={imu.gyro_x_dps} y={imu.gyro_y_dps} z={imu.gyro_z_dps}",
        f"  mag: x={imu.mag_x} y={imu.mag_y} z={imu.mag_z}",
        "Barometer",
        (
            "  estimated_altitude_m="
            f"{barometer.estimated_altitude_m:.2f} variometer_cms={barometer.variometer_cms}"
        ),
        "GPS",
        (
            f"  fix={gps.fix} satellites={gps.satellites} "
            f"lat={gps.latitude_deg:.7f} lon={gps.longitude_deg:.7f}"
        ),
        (
            "  altitude_m="
            f"{gps.altitude_m:.2f} ground_speed_cms={gps.ground_speed_cms} "
            f"ground_course_deg={gps.ground_course_deg:.1f}"
        ),
        f"timestamp={snapshot.timestamp:.3f}",
    ]
    return "\n".join(lines)
