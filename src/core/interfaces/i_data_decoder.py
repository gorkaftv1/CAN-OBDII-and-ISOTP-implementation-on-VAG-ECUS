"""Abstract interface for OBD-II response validation and data decoding.

``IDataDecoder`` separates two concerns that must never be mixed:

1. **Validation** — detecting Negative Response Code (NRC) frames and
   confirming that the mode echo byte matches the requested mode.
2. **Decoding** — applying the SAE J1979 mathematical formulas to convert
   raw ECU bytes into typed engineering-unit values.

No I/O is performed by this interface.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from core.exceptions import InvalidResponseError, NrcException  # noqa: F401 (re-exported for type-checker)
from core.models.dtc import Dtc
from core.models.obd_response import ObdResponse


class IDataDecoder(ABC):
    """Defines the contract for validating ECU responses and decoding sensor data.

    Callers must call :meth:`validate_response` first to obtain a clean
    :class:`~core.models.obd_response.ObdResponse`, then pass the *raw*
    bytes to the appropriate ``decode_*`` method to extract the
    engineering-unit value.

    All ``decode_*`` methods document the exact SAE J1979 formula used
    so that implementations can be independently verified against the
    standard without reading source code.

    No I/O is performed by this interface — it is a pure value transformer.
    """

    # ------------------------------------------------------------------ #
    # Validation                                                          #
    # ------------------------------------------------------------------ #

    @abstractmethod
    def validate_response(self, raw: bytes, expected_mode: int) -> ObdResponse:
        """Validate a raw ECU response frame and return a typed value object.

        Checks that the first byte equals ``expected_mode + 0x40``, which
        is the SAE J1979 positive response indicator. If the frame starts
        with ``0x7F`` the ECU has sent a Negative Response; in that case
        ``raw[1]`` is the echoed mode and ``raw[2]`` is the NRC code.

        Args:
            raw: The complete raw bytes received from the ECU via ISO-TP,
                including the mode echo and all data bytes.  Must contain
                at least 2 bytes.
            expected_mode: The OBD-II mode byte from the original request,
                e.g. ``0x01`` for Live Data or ``0x03`` for Read DTCs.

        Returns:
            An :class:`~core.models.obd_response.ObdResponse` with
            ``is_positive=True``, ``mode`` set to the echoed byte,
            ``pid`` set to ``raw[1]``, and ``data`` set to ``raw[2:]``.

        Raises:
            NrcException: If ``raw[0] == 0x7F`` (negative response frame),
                constructed with ``mode=raw[1]`` and ``nrc_code=raw[2]``.
            InvalidResponseError: If the frame is structurally malformed —
                for example, fewer than 2 bytes, or ``raw[0]`` does not
                match either ``expected_mode + 0x40`` or ``0x7F``.
        """
        ...

    # ------------------------------------------------------------------ #
    # Mode 0x01 decoders — Live Data                                     #
    # ------------------------------------------------------------------ #

    @abstractmethod
    def decode_rpm(self, raw: bytes) -> float:
        """Decode Engine RPM from a Mode 0x01 / PID 0x0C positive response.

        SAE J1979 formula::

            RPM = ((raw[2] * 256) + raw[3]) / 4

        The two data bytes encode RPM in units of 0.25 rpm/bit, giving a
        theoretical range of 0 – 16 383.75 rpm.

        Args:
            raw: Complete positive response bytes from the ECU.
                ``raw[0]`` = 0x41, ``raw[1]`` = 0x0C,
                ``raw[2]`` and ``raw[3]`` are the data bytes (A and B).

        Returns:
            Engine speed in revolutions per minute (rpm) as a ``float``.
        """
        ...

    @abstractmethod
    def decode_coolant_temp(self, raw: bytes) -> float:
        """Decode Engine Coolant Temperature from a Mode 0x01 / PID 0x05 response.

        SAE J1979 formula::

            Temperature = raw[2] - 40   (unit: °C)

        The single data byte encodes temperature with an offset of -40 °C,
        giving a range of -40 °C to +215 °C.

        Args:
            raw: Complete positive response bytes from the ECU.
                ``raw[0]`` = 0x41, ``raw[1]`` = 0x05, ``raw[2]`` is data byte A.

        Returns:
            Coolant temperature in degrees Celsius as a ``float``.
        """
        ...

    @abstractmethod
    def decode_vehicle_speed(self, raw: bytes) -> float:
        """Decode Vehicle Speed from a Mode 0x01 / PID 0x0D positive response.

        SAE J1979 formula::

            Speed = raw[2]   (unit: km/h)

        The single data byte encodes speed directly in km/h (0 – 255 km/h).

        Args:
            raw: Complete positive response bytes from the ECU.
                ``raw[0]`` = 0x41, ``raw[1]`` = 0x0D, ``raw[2]`` is data byte A.

        Returns:
            Vehicle speed in kilometres per hour as a ``float``.
        """
        ...

    @abstractmethod
    def decode_throttle_position(self, raw: bytes) -> float:
        """Decode Throttle Position from a Mode 0x01 / PID 0x11 response.

        SAE J1979 formula::

            Throttle = (raw[2] * 100) / 255   (unit: %)

        The single data byte represents throttle opening as a fraction of
        255, giving a range of 0.0 % to 100.0 %.

        Args:
            raw: Complete positive response bytes from the ECU.
                ``raw[0]`` = 0x41, ``raw[1]`` = 0x11, ``raw[2]`` is data byte A.

        Returns:
            Throttle opening as a percentage (0.0 – 100.0) as a ``float``.
        """
        ...

    @abstractmethod
    def decode_engine_load(self, raw: bytes) -> float:
        """Decode Calculated Engine Load from a Mode 0x01 / PID 0x04 response.

        SAE J1979 formula::

            Load = (raw[2] * 100) / 255   (unit: %)

        The single data byte represents engine load as a fraction of 255,
        giving a range of 0.0 % to 100.0 %.

        Args:
            raw: Complete positive response bytes from the ECU.
                ``raw[0]`` = 0x41, ``raw[1]`` = 0x04, ``raw[2]`` is data byte A.

        Returns:
            Calculated engine load as a percentage (0.0 – 100.0) as a ``float``.
        """
        ...

    # ------------------------------------------------------------------ #
    # Mode 0x03 / 0x04 decoders                                          #
    # ------------------------------------------------------------------ #

    @abstractmethod
    def decode_dtcs(self, raw: bytes) -> list[Dtc]:
        """Decode a list of DTCs from a Mode 0x03 positive response.

        The payload after the mode echo byte (0x43) contains pairs of
        bytes, each encoding one DTC according to the SAE J1979 scheme
        (see :meth:`Dtc.from_raw <core.models.dtc.Dtc.from_raw>`).

        Args:
            raw: Complete positive response bytes from the ECU.
                ``raw[0]`` = 0x43, ``raw[1]`` = number of DTCs,
                followed by ``raw[1] * 2`` data bytes.

        Returns:
            A ``list`` of :class:`~core.models.dtc.Dtc` instances in the
            order they appear in the response.  Returns an empty list when
            no faults are stored (raw[1] == 0x00).
        """
        ...

    # ------------------------------------------------------------------ #
    # Mode 0x09 decoders                                                  #
    # ------------------------------------------------------------------ #

    @abstractmethod
    def decode_vin(self, raw: bytes) -> str:
        """Decode the Vehicle Identification Number from a Mode 0x09 response.

        The VIN is encoded as 17 consecutive ASCII bytes in the payload
        following the mode echo (0x49) and InfoType echo (0x02) bytes.
        Multi-frame ISO-TP reassembly is handled transparently by the
        transport layer before this method is called.

        Args:
            raw: Complete positive response bytes from the ECU.
                ``raw[0]`` = 0x49, ``raw[1]`` = 0x02, ``raw[2]`` =
                message count (typically 0x01), ``raw[3:]`` = VIN bytes.

        Returns:
            The 17-character VIN string decoded from ASCII bytes.

        Raises:
            InvalidResponseError: If the decoded string is not exactly
                17 characters long, indicating a malformed or truncated
                response.
        """
        ...
