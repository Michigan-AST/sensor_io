# M-AST sensor_io

Read Betaflight sensor data over Multiwii Serial Protocol (MSP).

## Code Structure

Start in this order:

1. `sensor_reader.py`
2. `sensor_io/reader.py`
3. `sensor_io/models.py`
4. `sensor_io/parsers.py`
5. `sensor_io/msp.py`


- Computer running script sends a small request over a serial connection
- the flight controller sends back a packet (small structured message)
- this code turns that packet into named Python fields
- the script prints those fields as text or JSON (or later sends to sim)

## Sensor_IO Package Sections

- `sensor_reader.py`: command-line entry point
- `sensor_io/msp.py`: MSP serial framing and checksum handling
- `sensor_io/parsers.py`: conversion from raw payload bytes into named fields
- `sensor_io/reader.py`: high-level "read one complete sensor snapshot" flow
- `sensor_io/output.py`: text and JSON formatting
- `sensor_io/models.py`: dataclasses that describe the sensor data shape


## Glossary

- Flight controller: the small onboard computer that runs the drone.
- Betaflight: the firmware (low-level software on the flight controller) used
  by many drones.
- MSP: MultiWii Serial Protocol. This is the message format used to ask
  Betaflight for data over a serial connection.
- Serial connection: a simple byte stream between devices, often over USB or a
  UART port.
- Serial: sending data one byte at a time over a communication link such as USB
  or UART.
- UART: a hardware serial port on the flight controller.
- Packet: a small chunk of structured bytes sent over the connection.
- Payload: the actual useful data inside a packet.
- Checksum: a small value used to catch corrupted data.
- Framing: the rules that define how a packet is wrapped so the receiver knows
  where it starts, how long it is, and how to interpret it.
- Checksum handling: the process of calculating and verifying the checksum so
  bad data can be rejected.
- MSP serial framing and checksum handling: the low-level code that builds MSP
  packets, reads MSP packets back from the serial connection, and verifies that
  the bytes were received correctly.
- IMU: Inertial Measurement Unit. In this project it means accelerometer plus
  gyroscope data.
- Accelerometer: sensor that measures acceleration (change in motion), which
  also lets you infer tilt relative to gravity.
- Gyroscope: sensor that measures rotational speed, meaning how fast the drone
  is turning around each axis.
- Magnetometer: sensor that measures magnetic field direction, often used like
  a compass.
- Barometer: sensor that estimates altitude by measuring air pressure.
- Variometer: vertical speed, meaning how fast the drone is moving up or down.
- GPS fix: a valid solved position from GPS satellites.
- Latitude/longitude: standard Earth coordinates for position.
- Ground course: the direction of travel over the ground.

- Accelerometer: "Which way is down?" and "am I accelerating?"
- Gyroscope: "How fast am I rotating?"
- Magnetometer: "Which compass direction am I facing?"
- Barometer: "About how high am I, based on air pressure?"
- GPS: "Where am I outdoors, and how fast am I moving over the ground?"

- IMU: accelerometer and gyro via `MSP_RAW_IMU`
- Magnetometer: raw magnetometer axes via `MSP_RAW_IMU`
- GPS: fix, satellite count, lat/lon, altitude, speed, course via `MSP_RAW_GPS`
- Barometer-derived data: estimated altitude and variometer via `MSP_ALTITUDE`

## Install

```bash
python3 -m pip install pyserial
```

## Usage

Read one sample:

```bash
python3 sensor_reader.py --port /dev/tty.usbmodem12301
```

Stream continuously:

```bash
python3 sensor_reader.py --port /dev/tty.usbmodem12301 --count 0 --rate 5
```

Emit JSON instead of text:

```bash
python3 sensor_reader.py --port /dev/tty.usbmodem12301 --count 0 --rate 5 --json
```

## Betaflight setup

- Enable `MSP` on the USB VCP or UART you plan to use.
- Connect this script to that same serial port.
- Make sure GPS and magnetometer support are enabled in Betaflight so the FC is
  populating those fields.

## Troubleshooting

1. Is the correct serial port selected?
2. Is MSP enabled on that port in Betaflight?
3. Does the flight controller actually have that sensor enabled and working?
