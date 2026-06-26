"""Decode raw MSP payloads into typed sensor samples.

Each parser in this file does one job:
1. validate the payload length
2. unpack bytes into numbers
3. convert raw units into friendlier field values when needed
"""

from __future__ import annotations

import struct

from .models import BarometerSample, GpsSample, ImuSample
from .msp import MspError


def parse_imu_payload(payload: bytes) -> ImuSample:
    """Decode `MSP_RAW_IMU`.

    Payload layout:
    - 9 signed 16-bit integers
    - accel x/y/z
    - gyro x/y/z
    - mag x/y/z
    """

    # 9 signed 16-bit values = 18 total bytes.
    expected_size = 18
    if len(payload) != expected_size:
        raise MspError(f"Unexpected MSP_RAW_IMU payload length: {len(payload)}")

    # `struct.unpack` applies the binary layout exactly as MSP defines it:
    # `<` means little-endian (least-significant byte first)
    # `h` means signed 16-bit integer
    accel_x, accel_y, accel_z, gyro_x, gyro_y, gyro_z, mag_x, mag_y, mag_z = struct.unpack(
        "<9h", payload
    )
    # Return a named dataclass instead of a tuple so readers do not need to
    # remember field positions.
    return ImuSample(
        accel_x=accel_x,
        accel_y=accel_y,
        accel_z=accel_z,
        gyro_x_dps=gyro_x,
        gyro_y_dps=gyro_y,
        gyro_z_dps=gyro_z,
        mag_x=mag_x,
        mag_y=mag_y,
        mag_z=mag_z,
    )


def parse_barometer_payload(payload: bytes) -> BarometerSample:
    """Decode `MSP_ALTITUDE` into altitude and vertical speed."""

    # `MSP_ALTITUDE` contains one 32-bit altitude value and one 16-bit
    # variometer value, for a total of 6 bytes.
    expected_size = 6
    if len(payload) != expected_size:
        raise MspError(f"Unexpected MSP_ALTITUDE payload length: {len(payload)}")

    altitude_cm, variometer_cms = struct.unpack("<ih", payload)
    # Convert centimeters to meters because that unit is easier to read in logs.
    return BarometerSample(
        estimated_altitude_m=altitude_cm / 100.0,
        variometer_cms=variometer_cms,
    )


def parse_gps_payload(payload: bytes) -> GpsSample:
    """Decode `MSP_RAW_GPS`.

    The latitude and longitude values arrive as signed integers in 1e-7 degrees.
    The altitude field arrives in meters in this MSP message.
    """

    # GPS payload size is fixed for this legacy MSP message.
    expected_size = 16
    if len(payload) != expected_size:
        raise MspError(f"Unexpected MSP_RAW_GPS payload length: {len(payload)}")

    # Layout:
    # B  = unsigned 8-bit integer
    # i  = signed 32-bit integer
    # h  = signed 16-bit integer
    fix, satellites, latitude_raw, longitude_raw, altitude_m, speed_cms, course_tenths = (
        struct.unpack("<BBiihhh", payload)
    )
    # Latitude and longitude are scaled integers rather than floats on the wire
    # because binary protocols often avoid floating-point values for simplicity.
    return GpsSample(
        fix=bool(fix),
        satellites=satellites,
        latitude_deg=latitude_raw / 10_000_000.0,
        longitude_deg=longitude_raw / 10_000_000.0,
        altitude_m=float(altitude_m),
        ground_speed_cms=speed_cms,
        ground_course_deg=course_tenths / 10.0,
    )
