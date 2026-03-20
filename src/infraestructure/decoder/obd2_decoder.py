"""Concrete OBD-II response decoder backed by the config PID registry.

Implements :class:`~core.interfaces.i_data_decoder.IDataDecoder`: validates
raw ECU frames and delegates all SAE J1979 math to the lambdas stored in
:data:`config.obd_pids.PIDS`.
"""

from __future__ import annotations

import config.can_config as _cfg
import config.obd_pids as _pids
from core.exceptions import InvalidResponseError, NrcException
from core.interfaces.i_data_decoder import IDataDecoder
from core.models.dtc import Dtc
from core.models.obd_response import ObdResponse


class Obd2DataDecoder(IDataDecoder):
    """Concrete implementation of :class:`~core.interfaces.i_data_decoder.IDataDecoder`.

    Validates raw ECU byte frames against the expected OBD-II positive-
    response pattern and converts payload bytes into engineering-unit values
    by delegating to the decode lambdas in :mod:`config.obd_pids`.  No
    inline numeric formulas appear in this class.
    """

    # ------------------------------------------------------------------ #
    # Validation                                                          #
    # ------------------------------------------------------------------ #

    def validate_response(self, raw: bytes, expected_mode: int) -> ObdResponse:
        """Validate a raw ECU response frame and return a typed value object.

        Args:
            raw: Complete raw bytes received from the ECU via ISO-TP.
            expected_mode: The OBD-II mode byte from the original request
                (e.g. ``0x01`` for Live Data).

        Returns:
            An :class:`~core.models.obd_response.ObdResponse` with
            ``is_positive=True``, ``mode`` set to ``expected_mode``,
            ``pid`` set to ``raw[1]``, and ``data`` set to ``raw[2:]``.

        Raises:
            NrcException: If ``raw[0] == 0x7F`` (negative response frame).
            InvalidResponseError: If the frame is shorter than 2 bytes or
                ``raw[0]`` does not match the expected positive mode echo.
        """
        if len(raw) < 1:  # Mode 0x04 positive ack is legitimately b'\x44' (1 byte, no PID echo)
            raise InvalidResponseError(
                f"Response too short: expected at least 1 byte, got {len(raw)}"
            )
        if raw[0] == _cfg.OBD_NEGATIVE_PREFIX:
            if len(raw) < 3:
                raise InvalidResponseError(
                    f"NRC frame too short: expected 3 bytes, got {len(raw)}"
                )
            raise NrcException(mode=raw[1], nrc_code=raw[2])
        expected_echo = expected_mode + _cfg.OBD_POSITIVE_OFFSET
        if raw[0] != expected_echo:
            raise InvalidResponseError(
                f"Unexpected mode echo: got 0x{raw[0]:02X}, expected 0x{expected_echo:02X}"
            )
        return ObdResponse(
            mode=expected_mode,
            pid=raw[1] if len(raw) >= 2 else 0x00,
            data=raw[2:],
            is_positive=True,
        )

    # ------------------------------------------------------------------ #
    # Mode 0x01 decoders — Live Data                                     #
    # ------------------------------------------------------------------ #

    def decode_rpm(self, raw: bytes) -> float:
        """Decode Engine RPM using the SAE J1979 formula for PID 0x0C.

        Args:
            raw: Complete positive response bytes from the ECU
                (``raw[0]`` = 0x41, ``raw[1]`` = 0x0C, data at ``raw[2:]``).

        Returns:
            Engine speed in revolutions per minute as a ``float``.
        """
        return _pids.PIDS[0x0C].decode(raw)

    def decode_coolant_temp(self, raw: bytes) -> float:
        """Decode Engine Coolant Temperature using the SAE J1979 formula for PID 0x05.

        Args:
            raw: Complete positive response bytes from the ECU
                (``raw[0]`` = 0x41, ``raw[1]`` = 0x05, data at ``raw[2:]``).

        Returns:
            Coolant temperature in degrees Celsius as a ``float``.
        """
        return _pids.PIDS[0x05].decode(raw)

    def decode_vehicle_speed(self, raw: bytes) -> float:
        """Decode Vehicle Speed using the SAE J1979 formula for PID 0x0D.

        Args:
            raw: Complete positive response bytes from the ECU
                (``raw[0]`` = 0x41, ``raw[1]`` = 0x0D, data at ``raw[2:]``).

        Returns:
            Vehicle speed in kilometres per hour as a ``float``.
        """
        return _pids.PIDS[0x0D].decode(raw)

    def decode_throttle_position(self, raw: bytes) -> float:
        """Decode Throttle Position using the SAE J1979 formula for PID 0x11.

        Args:
            raw: Complete positive response bytes from the ECU
                (``raw[0]`` = 0x41, ``raw[1]`` = 0x11, data at ``raw[2:]``).

        Returns:
            Throttle opening as a percentage (0.0–100.0) as a ``float``.
        """
        return _pids.PIDS[0x11].decode(raw)

    def decode_engine_load(self, raw: bytes) -> float:
        """Decode Calculated Engine Load using the SAE J1979 formula for PID 0x04.

        Args:
            raw: Complete positive response bytes from the ECU
                (``raw[0]`` = 0x41, ``raw[1]`` = 0x04, data at ``raw[2:]``).

        Returns:
            Calculated engine load as a percentage (0.0–100.0) as a ``float``.
        """
        return _pids.PIDS[0x04].decode(raw)

    # ------------------------------------------------------------------ #
    # Mode 0x03 decoder — Diagnostic Trouble Codes                       #
    # ------------------------------------------------------------------ #

    def decode_dtcs(self, raw: bytes) -> list[Dtc]:
        """Decode stored DTCs from a Mode 0x03 positive response.

        Args:
            raw: Complete positive response bytes from the ECU.
                ``raw[0]`` = 0x43, ``raw[1]`` = number of DTCs,
                followed by ``raw[1] * 2`` data bytes (2 bytes per DTC).

        Returns:
            A ``list`` of :class:`~core.models.dtc.Dtc` instances in the
            order they appear in the response. Returns an empty list when
            no faults are stored (``raw[1] == 0x00``).
        """
        dtc_count = raw[1]
        if dtc_count == 0:
            return []
        dtcs: list[Dtc] = []
        for i in range(dtc_count):
            offset = 2 + i * 2
            pair = raw[offset : offset + 2]
            if pair == b"\x00\x00":
                continue
            dtcs.append(Dtc.from_raw(pair))
        return dtcs

    # ------------------------------------------------------------------ #
    # Mode 0x09 decoder — Vehicle Information                            #
    # ------------------------------------------------------------------ #

    def decode_vin(self, raw: bytes) -> str:
        """Decode the Vehicle Identification Number from a Mode 0x09 response.

        Args:
            raw: Complete reassembled positive response bytes from the ECU.
                ``raw[0]`` = 0x49, ``raw[1]`` = 0x02, ``raw[2]`` = 0x01
                (item count), ``raw[3:20]`` = 17 ASCII VIN bytes.

        Returns:
            The 17-character VIN string decoded from ASCII.

        Raises:
            InvalidResponseError: If the decoded VIN is not exactly 17
                characters long.
        """
        vin = raw[3:20].decode("ascii")
        if len(vin) != 17:
            raise InvalidResponseError(
                f"VIN length invalid: expected 17 characters, got {len(vin)}"
            )
        return vin
