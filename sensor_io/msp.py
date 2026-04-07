"""Minimal MSP v1 transport layer.

This module only knows how to:
- send an MSP command with no payload
- read the matching response
- validate the frame checksum

It deliberately does not know anything about sensor field layouts. That keeps
the protocol framing concerns separate from the message parsing concerns.
"""

from __future__ import annotations

import serial


# These command IDs come from the MSP (MultiWii Serial Protocol) message table
# used by Betaflight for legacy sensor reads.
MSP_RAW_IMU = 102
MSP_RAW_GPS = 106
MSP_ALTITUDE = 109

# MSP v1 frames start with a 3-byte header. The last character shows direction:
# `<` means host-to-flight-controller, `>` means flight-controller-to-host,
# `!` means an error response.
MSP_HEADER_OUT = b"$M<"
MSP_HEADER_IN = b"$M>"
MSP_HEADER_ERR = b"$M!"


class MspError(RuntimeError):
    """Raised when an MSP exchange cannot be completed safely."""


class MspClient:
    """Small wrapper around a serial port carrying MSP traffic."""

    def __init__(self, port: str, baudrate: int, timeout: float) -> None:
        # `pyserial` handles the platform-specific details of opening USB/UART
        # serial devices, so the rest of the code can stay protocol-focused.
        self.serial = serial.Serial(port=port, baudrate=baudrate, timeout=timeout)

    def close(self) -> None:
        self.serial.close()

    def __enter__(self) -> "MspClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def request(self, command: int) -> bytes:
        """Send one command and return its raw payload bytes."""

        # Clear any older bytes before starting a new request/response exchange.
        # That reduces the chance of parsing stale data from a previous read.
        self.serial.reset_input_buffer()
        self.serial.write(self._build_request_frame(command))
        self.serial.flush()
        return self._read_response_payload(expected_command=command)

    @staticmethod
    def _build_request_frame(command: int) -> bytes:
        # These requests carry no payload, so the payload size is zero and the
        # checksum only needs to combine the size and command fields.
        payload_size = 0
        checksum = payload_size ^ command
        return MSP_HEADER_OUT + bytes((payload_size, command, checksum))

    def _read_exact(self, count: int) -> bytes:
        # MSP framing is byte-precise, so partial reads are not useful here.
        # Either we receive the exact number of bytes needed, or the read fails.
        data = self.serial.read(count)
        if len(data) != count:
            raise MspError(f"Timed out while reading {count} bytes from the serial port")
        return data

    def _read_response_payload(self, expected_command: int) -> bytes:
        """Read frames until the expected command response arrives."""

        while True:
            # Read the fixed-size frame prefix first so we know how much payload
            # data the rest of the frame contains.
            header = self._read_exact(3)
            if header not in (MSP_HEADER_IN, MSP_HEADER_ERR):
                raise MspError(f"Unexpected MSP header: {header!r}")

            payload_size = self._read_exact(1)[0]
            command = self._read_exact(1)[0]
            payload = self._read_exact(payload_size)
            checksum = self._read_exact(1)[0]

            # A checksum (a small integrity check value) helps detect corrupted
            # bytes before we try to interpret them as sensor data.
            if checksum != _compute_checksum(payload_size, command, payload):
                raise MspError(
                    f"Checksum mismatch for MSP command {command}: received {checksum}"
                )

            if header == MSP_HEADER_ERR:
                raise MspError(f"Flight controller rejected MSP command {command}")

            # Ignore unrelated frames and keep reading until we find the response
            # for the command we just sent.
            if command == expected_command:
                return payload


def _compute_checksum(payload_size: int, command: int, payload: bytes) -> int:
    """Compute the MSP v1 XOR checksum."""

    # XOR (exclusive OR, a byte-wise operation) is the checksum rule used by
    # MSP v1. Each byte is folded into one running value.
    checksum = payload_size ^ command
    for byte in payload:
        checksum ^= byte
    return checksum
