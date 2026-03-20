"""OBD-II PID definitions derived from the Arduino ECU simulator.

Each entry in :data:`PIDS` describes one supported Mode 0x01 PID: the bytes
to send, the expected response size, and the SAE J1979 lambda that converts
the raw ECU response bytes into a typed engineering-unit value.

All values and formulas are taken verbatim from ``ecu_protocol.h`` and
``ecu_sim.ino``.  Do **not** modify them without first verifying the change
against the Arduino source.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class PidDefinition:
    """Immutable descriptor for a single OBD-II Mode 0x01 PID.

    Instances are frozen so they can be stored as dict values and shared
    safely across threads without risk of accidental mutation.

    Attributes:
        pid: The PID byte value (e.g. ``0x0C`` for Engine RPM).
        name: Human-readable name of the parameter (e.g. ``"Engine RPM"``).
        request: Exact byte sequence to send to the ECU — mode byte 0x01
            followed by the PID byte.  ISO-TP framing is added by the
            transport layer and must **not** appear here.
        unit: Physical unit of the decoded value (e.g. ``"rpm"``, ``"%"``,
            ``"°C"``).
        response_bytes: Total number of bytes in the positive ECU response,
            including the mode-echo byte (0x41) and the PID-echo byte.
            Typically 3 (one data byte) or 4 (two data bytes).
        decode: SAE J1979 lambda ``(raw: bytes) -> float`` that converts the
            full raw positive response into an engineering-unit value.
            ``raw[0]`` is the mode-echo byte (0x41), ``raw[1]`` is the
            PID echo, and payload data begins at ``raw[2]``.
    """

    pid: int
    name: str
    request: bytes
    unit: str
    response_bytes: int
    decode: Callable[[bytes], float]


# ────────────────────────────────────────────────────────────────────────────
# Additional request constants (non-Mode-01 operations)
# ────────────────────────────────────────────────────────────────────────────

VIN_PID_REQUEST: bytes = b"\x09\x02"   # Mode 0x09 / InfoType 0x02 — request the 17-char VIN
READ_DTCS_REQUEST: bytes = b"\x03"     # Mode 0x03 — request all stored DTCs (no PID byte)
CLEAR_DTCS_REQUEST: bytes = b"\x04"    # Mode 0x04 — clear stored DTCs and freeze-frame data

# ────────────────────────────────────────────────────────────────────────────
# Mode 0x01 PID registry
# ────────────────────────────────────────────────────────────────────────────

PIDS: dict[int, PidDefinition] = {
    0x04: PidDefinition(
        pid=0x04,
        name="Engine Load",
        request=b"\x01\x04",
        unit="%",
        response_bytes=3,
        decode=lambda raw: (raw[2] * 100) / 255,
    ),
    0x05: PidDefinition(
        pid=0x05,
        name="Coolant Temp",
        request=b"\x01\x05",
        unit="°C",
        response_bytes=3,
        decode=lambda raw: float(raw[2] - 40),
    ),
    0x06: PidDefinition(
        pid=0x06,
        name="Short Fuel Trim Bank 1",
        request=b"\x01\x06",
        unit="%",
        response_bytes=3,
        decode=lambda raw: (raw[2] * 100 / 128) - 100,
    ),
    0x07: PidDefinition(
        pid=0x07,
        name="Long Fuel Trim Bank 1",
        request=b"\x01\x07",
        unit="%",
        response_bytes=3,
        decode=lambda raw: (raw[2] * 100 / 128) - 100,
    ),
    0x0C: PidDefinition(
        pid=0x0C,
        name="Engine RPM",
        request=b"\x01\x0C",
        unit="rpm",
        response_bytes=4,
        decode=lambda raw: ((raw[2] << 8) | raw[3]) / 4,
    ),
    0x0D: PidDefinition(
        pid=0x0D,
        name="Vehicle Speed",
        request=b"\x01\x0D",
        unit="km/h",
        response_bytes=3,
        decode=lambda raw: float(raw[2]),
    ),
    0x0E: PidDefinition(
        pid=0x0E,
        name="Timing Advance",
        request=b"\x01\x0E",
        unit="°",
        response_bytes=3,
        decode=lambda raw: (raw[2] / 2) - 64,
    ),
    0x0F: PidDefinition(
        pid=0x0F,
        name="Intake Air Temp",
        request=b"\x01\x0F",
        unit="°C",
        response_bytes=3,
        decode=lambda raw: float(raw[2] - 40),
    ),
    0x10: PidDefinition(
        pid=0x10,
        name="MAF Air Flow Rate",
        request=b"\x01\x10",
        unit="g/s",
        response_bytes=4,
        decode=lambda raw: ((raw[2] << 8) | raw[3]) / 100,
    ),
    0x11: PidDefinition(
        pid=0x11,
        name="Throttle Position",
        request=b"\x01\x11",
        unit="%",
        response_bytes=3,
        decode=lambda raw: (raw[2] * 100) / 255,
    ),
    0x1F: PidDefinition(
        pid=0x1F,
        name="Runtime Since Start",
        request=b"\x01\x1F",
        unit="seconds",
        response_bytes=4,
        decode=lambda raw: float((raw[2] << 8) | raw[3]),
    ),
    0x23: PidDefinition(
        pid=0x23,
        name="Fuel Rail Pressure",
        request=b"\x01\x23",
        unit="kPa",
        response_bytes=4,
        decode=lambda raw: float(((raw[2] << 8) | raw[3]) * 10),
    ),
    0x2F: PidDefinition(
        pid=0x2F,
        name="Fuel Level",
        request=b"\x01\x2F",
        unit="%",
        response_bytes=3,
        decode=lambda raw: (raw[2] * 100) / 255,
    ),
    0x31: PidDefinition(
        pid=0x31,
        name="Distance Since DTC Clear",
        request=b"\x01\x31",
        unit="km",
        response_bytes=4,
        decode=lambda raw: float((raw[2] << 8) | raw[3]),
    ),
    0x33: PidDefinition(
        pid=0x33,
        name="Barometric Pressure",
        request=b"\x01\x33",
        unit="kPa",
        response_bytes=3,
        decode=lambda raw: float(raw[2]),
    ),
    0x42: PidDefinition(
        pid=0x42,
        name="Control Module Voltage",
        request=b"\x01\x42",
        unit="V",
        response_bytes=4,
        decode=lambda raw: ((raw[2] << 8) | raw[3]) / 1000,
    ),
    0x46: PidDefinition(
        pid=0x46,
        name="Ambient Air Temp",
        request=b"\x01\x46",
        unit="°C",
        response_bytes=3,
        decode=lambda raw: float(raw[2] - 40),
    ),
    0x5C: PidDefinition(
        pid=0x5C,
        name="Engine Oil Temp",
        request=b"\x01\x5C",
        unit="°C",
        response_bytes=3,
        decode=lambda raw: float(raw[2] - 40),
    ),
}
