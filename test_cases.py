#!/usr/bin/env python3
"""Self-contained test cases for the sensor reader project.

This file is meant to answer a practical question:
"Can we prove the code works without a real drone attached?"

The answer is "mostly yes" by testing three layers:
1. parser tests: do raw bytes decode into the right field values?
2. MSP transport tests: do request/response packets get built and validated?
3. end-to-end fake device test: can we read a full sensor snapshot from a
   pretend flight controller?

The tests use only Python's standard library so the team can run them with:

    python3 test_cases.py
"""

from __future__ import annotations

import sys
import struct
import types
import unittest
from unittest.mock import patch

# The production code depends on `pyserial`. For tests that use a fake serial
# device, we can safely provide a tiny stub when `pyserial` is not installed.
try:
    import serial as _serial  # type: ignore
except ModuleNotFoundError:
    serial_stub = types.ModuleType("serial")
    serial_stub.Serial = object
    serial_stub.SerialException = RuntimeError
    sys.modules["serial"] = serial_stub

from sensor_io.msp import MSP_ALTITUDE, MSP_RAW_GPS, MSP_RAW_IMU, MspClient, MspError
from sensor_io.parsers import (
    parse_barometer_payload,
    parse_gps_payload,
    parse_imu_payload,
)
from sensor_io.reader import read_sensor_snapshot


def build_msp_response(command: int, payload: bytes, *, error: bool = False) -> bytes:
    """Build a fake MSP response frame.

    This mirrors what Betaflight would send back over the wire:
    - a header
    - the payload length
    - the command ID
    - the payload bytes
    - a checksum
    """

    header = b"$M!" if error else b"$M>"
    payload_size = len(payload)
    checksum = payload_size ^ command
    for byte in payload:
        checksum ^= byte
    return header + bytes((payload_size, command)) + payload + bytes((checksum,))


class FakeSerial:
    """Tiny fake serial port used by the tests.

    It behaves just enough like `pyserial.Serial` for our code to interact with
    it:
    - `write()` stores outgoing bytes so we can inspect them
    - `read()` returns bytes from a preset input buffer
    - `reset_input_buffer()` optionally clears stale bytes

    The `preserve_on_reset` option exists because the production code clears the
    serial input buffer before each request. In real hardware that is useful.
    In a fake test device, we often preload the next response bytes up front, so
    we choose to preserve them.
    """

    def __init__(self, incoming: bytes = b"", *, preserve_on_reset: bool = True) -> None:
        self.incoming = bytearray(incoming)
        self.written = bytearray()
        self.closed = False
        self.preserve_on_reset = preserve_on_reset

    def read(self, count: int) -> bytes:
        chunk = bytes(self.incoming[:count])
        del self.incoming[:count]
        return chunk

    def write(self, data: bytes) -> int:
        self.written.extend(data)
        return len(data)

    def flush(self) -> None:
        # Real serial ports may flush buffered outgoing bytes. Our fake object
        # writes immediately, so nothing extra is needed here.
        return None

    def reset_input_buffer(self) -> None:
        if not self.preserve_on_reset:
            self.incoming.clear()

    def close(self) -> None:
        self.closed = True


class ParserTests(unittest.TestCase):
    """Validate that binary payloads decode into the expected values."""

    def test_parse_imu_payload(self) -> None:
        payload = struct.pack("<9h", 1, -2, 3, 4, -5, 6, 7, -8, 9)

        sample = parse_imu_payload(payload)

        self.assertEqual(sample.accel_x, 1)
        self.assertEqual(sample.accel_y, -2)
        self.assertEqual(sample.accel_z, 3)
        self.assertEqual(sample.gyro_x_dps, 4)
        self.assertEqual(sample.gyro_y_dps, -5)
        self.assertEqual(sample.gyro_z_dps, 6)
        self.assertEqual(sample.mag_x, 7)
        self.assertEqual(sample.mag_y, -8)
        self.assertEqual(sample.mag_z, 9)

    def test_parse_barometer_payload(self) -> None:
        # 12345 cm should become 123.45 m in the friendlier output model.
        payload = struct.pack("<ih", 12345, -42)

        sample = parse_barometer_payload(payload)

        self.assertEqual(sample.estimated_altitude_m, 123.45)
        self.assertEqual(sample.variometer_cms, -42)

    def test_parse_gps_payload(self) -> None:
        payload = struct.pack("<BBiihhh", 1, 10, 423456789, -834567890, 250, 1200, 915)

        sample = parse_gps_payload(payload)

        self.assertTrue(sample.fix)
        self.assertEqual(sample.satellites, 10)
        self.assertEqual(sample.latitude_deg, 42.3456789)
        self.assertEqual(sample.longitude_deg, -83.456789)
        self.assertEqual(sample.altitude_m, 250.0)
        self.assertEqual(sample.ground_speed_cms, 1200)
        self.assertEqual(sample.ground_course_deg, 91.5)

    def test_parse_imu_payload_rejects_wrong_size(self) -> None:
        with self.assertRaises(MspError):
            parse_imu_payload(b"\x00" * 17)


class MspTransportTests(unittest.TestCase):
    """Validate MSP packet building and response handling."""

    def test_build_request_frame(self) -> None:
        frame = MspClient._build_request_frame(MSP_RAW_IMU)

        # For a request with no payload, the frame is:
        # header + zero payload size + command byte + checksum
        self.assertEqual(frame, b"$M<\x00\x66\x66")

    def test_request_returns_matching_payload(self) -> None:
        expected_payload = struct.pack("<ih", 500, 12)
        fake_serial = FakeSerial(build_msp_response(MSP_ALTITUDE, expected_payload))
        client = object.__new__(MspClient)
        client.serial = fake_serial

        payload = client.request(MSP_ALTITUDE)

        self.assertEqual(payload, expected_payload)
        self.assertEqual(fake_serial.written, MspClient._build_request_frame(MSP_ALTITUDE))

    def test_request_rejects_bad_checksum(self) -> None:
        payload = struct.pack("<ih", 500, 12)
        frame = bytearray(build_msp_response(MSP_ALTITUDE, payload))
        frame[-1] ^= 0x01
        fake_serial = FakeSerial(bytes(frame))
        client = object.__new__(MspClient)
        client.serial = fake_serial

        with self.assertRaises(MspError):
            client.request(MSP_ALTITUDE)

    def test_request_rejects_error_frame(self) -> None:
        fake_serial = FakeSerial(build_msp_response(MSP_RAW_IMU, b"", error=True))
        client = object.__new__(MspClient)
        client.serial = fake_serial

        with self.assertRaises(MspError):
            client.request(MSP_RAW_IMU)


class EndToEndTests(unittest.TestCase):
    """Exercise the full read path using a pretend flight controller."""

    def test_read_sensor_snapshot_from_fake_flight_controller(self) -> None:
        imu_payload = struct.pack("<9h", 100, 200, -300, 10, 20, 30, 40, 50, 60)
        altitude_payload = struct.pack("<ih", 4321, -15)
        gps_payload = struct.pack("<BBiihhh", 1, 12, 420000000, -830000000, 215, 850, 2700)

        all_frames = (
            build_msp_response(MSP_RAW_IMU, imu_payload)
            + build_msp_response(MSP_ALTITUDE, altitude_payload)
            + build_msp_response(MSP_RAW_GPS, gps_payload)
        )

        fake_serial = FakeSerial(all_frames)

        with patch("sensor_io.msp.serial.Serial", return_value=fake_serial):
            with MspClient(port="fake-port", baudrate=115200, timeout=1.0) as client:
                snapshot = read_sensor_snapshot(client)

        self.assertEqual(snapshot.imu.accel_x, 100)
        self.assertEqual(snapshot.imu.mag_z, 60)
        self.assertEqual(snapshot.barometer.estimated_altitude_m, 43.21)
        self.assertEqual(snapshot.barometer.variometer_cms, -15)
        self.assertTrue(snapshot.gps.fix)
        self.assertEqual(snapshot.gps.satellites, 12)
        self.assertEqual(snapshot.gps.latitude_deg, 42.0)
        self.assertEqual(snapshot.gps.longitude_deg, -83.0)
        self.assertEqual(snapshot.gps.altitude_m, 215.0)
        self.assertEqual(snapshot.gps.ground_speed_cms, 850)
        self.assertEqual(snapshot.gps.ground_course_deg, 270.0)
        self.assertTrue(fake_serial.closed)


if __name__ == "__main__":
    unittest.main(verbosity=2)
