"""Abstract interface for the OBD-II protocol request builder.

``IProtocolBuilder`` is a pure factory: it constructs raw OBD-II request
byte sequences without performing any I/O. Separating frame construction
from transmission makes each component independently testable.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class IProtocolBuilder(ABC):
    """Defines the contract for building raw OBD-II request byte frames.

    Each method corresponds to a single OBD-II diagnostic request and
    returns the exact byte sequence that must be passed to
    ``ITransport.send()``. Implementations translate high-level intent
    (e.g. "give me the RPM frame") into low-level bytes without any
    knowledge of the transport or the response format.

    No I/O is performed by this interface — it is a pure builder / factory.

    Each method returns only the OBD-II application payload bytes (mode byte
    plus optional PID / InfoType byte). ISO-TP framing — including the
    Single Frame length nibble — is the exclusive responsibility of the
    transport layer and must not appear in the values returned here.
    """

    # ------------------------------------------------------------------ #
    # Mode 0x01 — Current Data (Live Data)                               #
    # ------------------------------------------------------------------ #

    @abstractmethod
    def build_read_rpm_request(self) -> bytes:
        """Build the Mode 0x01 / PID 0x0C request payload for Engine RPM.

        Returns:
            ``b'\\x01\\x0C'`` — mode byte 0x01 followed by PID 0x0C.
        """
        ...

    @abstractmethod
    def build_read_coolant_temp_request(self) -> bytes:
        """Build the Mode 0x01 / PID 0x05 request payload for Coolant Temperature.

        Returns:
            ``b'\\x01\\x05'`` — mode byte 0x01 followed by PID 0x05.
        """
        ...

    @abstractmethod
    def build_read_vehicle_speed_request(self) -> bytes:
        """Build the Mode 0x01 / PID 0x0D request payload for Vehicle Speed.

        Returns:
            ``b'\\x01\\x0D'`` — mode byte 0x01 followed by PID 0x0D.
        """
        ...

    @abstractmethod
    def build_read_throttle_position_request(self) -> bytes:
        """Build the Mode 0x01 / PID 0x11 request payload for Throttle Position.

        Returns:
            ``b'\\x01\\x11'`` — mode byte 0x01 followed by PID 0x11.
        """
        ...

    @abstractmethod
    def build_read_engine_load_request(self) -> bytes:
        """Build the Mode 0x01 / PID 0x04 request payload for Calculated Engine Load.

        Returns:
            ``b'\\x01\\x04'`` — mode byte 0x01 followed by PID 0x04.
        """
        ...

    # ------------------------------------------------------------------ #
    # Mode 0x03 — Request Stored Diagnostic Trouble Codes                #
    # ------------------------------------------------------------------ #

    @abstractmethod
    def build_read_dtcs_request(self) -> bytes:
        """Build the Mode 0x03 request payload for reading stored DTCs.

        Mode 0x03 carries no PID byte; the payload is the mode byte alone.

        Returns:
            ``b'\\x03'`` — mode byte 0x03 only.
        """
        ...

    # ------------------------------------------------------------------ #
    # Mode 0x04 — Clear / Reset Diagnostic Information                   #
    # ------------------------------------------------------------------ #

    @abstractmethod
    def build_clear_dtcs_request(self) -> bytes:
        """Build the Mode 0x04 request payload for clearing stored DTCs.

        Mode 0x04 carries no PID byte; the payload is the mode byte alone.

        Returns:
            ``b'\\x04'`` — mode byte 0x04 only.
        """
        ...

    # ------------------------------------------------------------------ #
    # Mode 0x09 — Request Vehicle Information                            #
    # ------------------------------------------------------------------ #

    @abstractmethod
    def build_read_vin_request(self) -> bytes:
        """Build the Mode 0x09 / InfoType 0x02 request frame for the VIN.

        InfoType 0x02 requests the 17-character Vehicle Identification
        Number. The ECU response may span multiple ISO-TP frames; the
        transport layer handles reassembly transparently.

        Returns:
            ``b'\\x09\\x02'`` — mode byte 0x09 followed by InfoType
            0x09 and InfoType 0x02.
        """
        ...
