"""Data models used throughout the project.

Keeping the sensor shapes in one place makes it easier for the team to answer
two common questions:
1. What data do we expect from Betaflight?
2. What units are those values expressed in?
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Dict


@dataclass
class ImuSample:
    """Raw IMU and magnetometer values from `MSP_RAW_IMU`.

    Betaflight returns accelerometer, gyro, and magnetometer values in one
    message. The field names here mirror that layout directly.

    Plain-English view:
    - accelerometer: "how is the drone accelerating or tilting?"
    - gyroscope: "how fast is the drone rotating?"
    - magnetometer: "which compass direction is the drone facing?"
    """

    # Accelerometer axes are left as raw integers because Betaflight defines the
    # message layout that way.
    accel_x: int
    accel_y: int
    accel_z: int
    # Gyro values are labeled with `_dps` to signal degrees per second.
    gyro_x_dps: int
    gyro_y_dps: int
    gyro_z_dps: int
    # Magnetometer values are also raw integers from the FC (flight controller).
    mag_x: int
    mag_y: int
    mag_z: int


@dataclass
class BarometerSample:
    """Altitude-related output derived by Betaflight from the barometer.

    This is not raw DPS310 pressure or temperature data. Betaflight's common
    MSP message exposes the flight controller's estimated altitude and vertical
    speed instead.

    Plain-English view:
    - estimated altitude: "roughly how high does Betaflight think we are?"
    - variometer: "how fast are we moving up or down?"
    """

    # Altitude is converted to meters for readability.
    estimated_altitude_m: float
    # Variometer is vertical speed in centimeters per second.
    variometer_cms: int


@dataclass
class GpsSample:
    """GPS information from `MSP_RAW_GPS`.

    Plain-English view:
    - fix: "do we currently have a usable GPS position?"
    - satellites: "how many satellites are being used or seen?"
    - latitude/longitude: "where are we on Earth?"
    - altitude: "how high does GPS think we are?"
    - ground speed/course: "how fast and in what direction are we moving?"
    """

    # `fix` tells us whether the GPS currently has a valid position solution
    # (solution meaning a usable computed location).
    fix: bool
    satellites: int
    # Latitude/longitude are converted into decimal degrees because that is the
    # most recognizable form for people and mapping tools.
    latitude_deg: float
    longitude_deg: float
    altitude_m: float
    ground_speed_cms: int
    ground_course_deg: float


@dataclass
class SensorSnapshot:
    """One complete sensor read across all requested subsystems.

    You can think of this as one row in a sensor log.
    """

    # Unix timestamp (seconds since 1970-01-01 UTC) marking when this combined
    # snapshot was assembled.
    timestamp: float
    imu: ImuSample
    barometer: BarometerSample
    gps: GpsSample

    def to_dict(self) -> Dict[str, object]:
        """Return a JSON-friendly representation."""

        # `asdict` recursively converts dataclasses into plain dictionaries.
        return {
            "timestamp": self.timestamp,
            "imu": asdict(self.imu),
            "barometer": asdict(self.barometer),
            "gps": asdict(self.gps),
        }
