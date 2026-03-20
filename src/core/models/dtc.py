"""Domain model for Diagnostic Trouble Codes (DTCs).

Implements the full SAE J1979 / ISO 15031-6 two-byte DTC encoding so that
raw ECU bytes can be converted into the familiar P/C/B/U alphanumeric codes.
"""

from __future__ import annotations

from dataclasses import dataclass, field


# Mapping from bits 15-14 of the 2-byte DTC word to the DTC category prefix.
_DTC_PREFIX: dict[int, str] = {
    0b00: "P",  # Powertrain
    0b01: "C",  # Chassis
    0b10: "B",  # Body
    0b11: "U",  # Network / User-defined
}


@dataclass(frozen=True)
class Dtc:
    """Represents a single Diagnostic Trouble Code (DTC).

    Instances are immutable so they can be safely shared across threads
    and used as dictionary keys or set members.

    Attributes:
        code: Human-readable DTC string using the SAE J1979 format,
            e.g. ``"P0113"``.
        raw_bytes: The original 2-byte encoding as received from the ECU;
            preserved for logging and round-trip verification.
        description: Optional free-text description of the fault condition,
            e.g. ``"Intake Air Temperature Sensor Circuit High"``.

    Example::

        dtc = Dtc.from_raw(bytes([0x01, 0x13]))
        print(dtc)  # "P0113 - "
    """

    code: str
    raw_bytes: bytes
    description: str = field(default="")

    def __str__(self) -> str:
        """Return a human-readable representation of the DTC.

        Returns:
            String in the format ``"<code> - <description>"``,
            e.g. ``"P0113 - Sensor IAT"``. When description is empty
            the separator and trailing text are still included for a
            consistent format, e.g. ``"P0113 - "``.
        """
        return f"{self.code} - {self.description}"

    @classmethod
    def from_raw(cls, raw: bytes) -> Dtc:
        """Construct a ``Dtc`` instance from the 2-byte SAE J1979 encoding.

        The SAE J1979 / ISO 15031-6 DTC 2-byte encoding layout (big-endian)::

            Byte 0 (MSB)   Byte 1 (LSB)
            7  6  5  4     3  2  1  0
            |  |  |  |           |
            |  |  |  +--digit 2--+   bits 3-0  of byte 0 → second digit
            |  |  +-------------+    bits 7-4  of byte 0 → third digit... wait

        Correct bit layout for a 16-bit DTC word (MSB first)::

            Bit 15-14 : Category prefix  (00=P, 01=C, 10=B, 11=U)
            Bit 13-12 : First digit      (0–3, always decimal)
            Bit 11-8  : Second digit     (0x0–0xF, shown as hex nibble)
            Bit  7-4  : Third digit      (0x0–0xF, shown as hex nibble)
            Bit  3-0  : Fourth digit     (0x0–0xF, shown as hex nibble)

        Example — bytes ``[0x01, 0x13]`` decode as::

            word = 0x0113
            prefix  = (0x01 >> 6) & 0x03 = 0  → 'P'
            digit1  = (0x01 >> 4) & 0x03 = 0  → '0'
            digit2  = (0x01     ) & 0x0F = 1  → '1'
            digit3  = (0x13 >> 4) & 0x0F = 1  → '1'
            digit4  = (0x13     ) & 0x0F = 3  → '3'
            code    = "P0113"

        Args:
            raw: Exactly 2 bytes representing a single encoded DTC.

        Returns:
            A ``Dtc`` instance with the decoded ``code`` and the original
            ``raw_bytes`` preserved; ``description`` defaults to ``""``.

        Raises:
            ValueError: If ``raw`` does not contain exactly 2 bytes.
        """
        if len(raw) != 2:
            raise ValueError(f"DTC raw bytes must be exactly 2 bytes, got {len(raw)}")
        prefix = _DTC_PREFIX[(raw[0] >> 6) & 0x03]
        digit1 = (raw[0] >> 4) & 0x03
        digit2 = raw[0] & 0x0F
        digit3 = (raw[1] >> 4) & 0x0F
        digit4 = raw[1] & 0x0F
        code = f"{prefix}{digit1}{digit2:X}{digit3:X}{digit4:X}"
        return cls(code=code, raw_bytes=bytes(raw))
