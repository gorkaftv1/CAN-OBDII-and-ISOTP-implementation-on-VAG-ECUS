"""Immutable snapshot of a single OBD-II sensor reading produced by the monitor."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MonitorSample:
    """Immutable snapshot of a single OBD-II sensor reading.

    Attributes:
        pid: PID byte polled, e.g. 0x0C.
        name: Human-readable name from PID registry, e.g. "Engine RPM".
        value: Decoded engineering-unit value, e.g. 850.0.
        unit: Physical unit string, e.g. "rpm", "°C", "%".
        timestamp: time.monotonic() captured after transport.receive()
            returns — immune to system-clock adjustments.
    """

    pid: int
    name: str
    value: float
    unit: str
    timestamp: float
