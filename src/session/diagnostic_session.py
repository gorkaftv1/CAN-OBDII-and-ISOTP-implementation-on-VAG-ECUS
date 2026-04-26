"""Concrete implementation of the high-level OBD-II diagnostic session.

Orchestrates :class:`~core.interfaces.i_transport.ITransport`,
:class:`~core.interfaces.i_protocol_builder.IProtocolBuilder`, and
:class:`~core.interfaces.i_data_decoder.IDataDecoder` to expose a clean,
intent-driven API for every supported OBD-II operation.
"""

from __future__ import annotations

import time
from types import TracebackType

from config.obd_pids import PIDS
from core.exceptions import InvalidResponseError
from core.interfaces.i_data_decoder import IDataDecoder
from core.interfaces.i_diagnostic_session import IDiagnosticSession
from core.interfaces.i_protocol_builder import IProtocolBuilder
from core.interfaces.i_transport import ITransport
from core.models.dtc import Dtc
from core.models.monitor_sample import MonitorSample


class DiagnosticSession(IDiagnosticSession):
    """Concrete implementation of :class:`~core.interfaces.i_diagnostic_session.IDiagnosticSession`.

    Coordinates the three collaborators injected via the constructor to
    implement the full send → receive → validate → decode pipeline for
    every supported OBD-II data point.  No exceptions are caught —
    ``NrcException``, ``DiagnosticTimeoutError``, and ``TransportError``
    propagate unchanged to the caller.

    Example::

        session = DiagnosticSession(transport, builder, decoder)
        with session:
            rpm  = session.get_engine_rpm()
            dtcs = session.get_dtcs()
            vin  = session.get_vin()
    """

    def __init__(
        self,
        transport: ITransport,
        builder: IProtocolBuilder,
        decoder: IDataDecoder,
    ) -> None:
        """Store the three collaborators required by the session.

        Args:
            transport: Concrete transport that handles CAN / ISO-TP I/O.
            builder: Concrete builder that constructs OBD-II request frames.
            decoder: Concrete decoder that validates and decodes ECU responses.
        """
        self._transport = transport
        self._builder = builder
        self._decoder = decoder

    # ------------------------------------------------------------------ #
    # Session lifecycle                                                   #
    # ------------------------------------------------------------------ #

    def open(self) -> None:
        """Open the diagnostic session by connecting the underlying transport.

        Raises:
            TransportError: If the transport cannot be opened.
        """
        self._transport.connect()

    def close(self) -> None:
        """Close the diagnostic session and release all transport resources.

        Raises:
            TransportError: If the transport cannot be closed cleanly.
        """
        self._transport.disconnect()

    def __enter__(self) -> DiagnosticSession:
        """Enter the runtime context by opening the session.

        Returns:
            This ``DiagnosticSession`` instance, ready for diagnostic calls.

        Raises:
            TransportError: Propagated from :meth:`open`.
        """
        self.open()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool | None:
        """Close the session unconditionally on context-manager exit.

        Args:
            exc_type: Exception class raised inside the ``with`` block, or
                ``None`` if no exception occurred.
            exc_val: Exception instance, or ``None``.
            exc_tb: Traceback object, or ``None``.

        Returns:
            ``None`` — exceptions are never suppressed.
        """
        self.close()
        return None

    # ------------------------------------------------------------------ #
    # Mode 0x01 — Live Data                                               #
    # ------------------------------------------------------------------ #

    def get_engine_rpm(self) -> float:
        """Request and decode the current Engine RPM.

        Returns:
            Engine speed in revolutions per minute as a ``float``.

        Raises:
            NrcException: If the ECU returns a Negative Response Code.
            DiagnosticTimeoutError: If the ECU does not reply in time.
            TransportError: If a CAN-level error occurs.
        """
        payload = self._builder.build_read_rpm_request()
        self._transport.send(payload)
        raw = self._transport.receive()
        self._decoder.validate_response(raw, expected_mode=0x01)
        return self._decoder.decode_rpm(raw)

    def get_coolant_temp(self) -> float:
        """Request and decode the current Engine Coolant Temperature.

        Returns:
            Coolant temperature in degrees Celsius as a ``float``.

        Raises:
            NrcException: If the ECU returns a Negative Response Code.
            DiagnosticTimeoutError: If the ECU does not reply in time.
            TransportError: If a CAN-level error occurs.
        """
        payload = self._builder.build_read_coolant_temp_request()
        self._transport.send(payload)
        raw = self._transport.receive()
        self._decoder.validate_response(raw, expected_mode=0x01)
        return self._decoder.decode_coolant_temp(raw)

    def get_vehicle_speed(self) -> float:
        """Request and decode the current Vehicle Speed.

        Returns:
            Vehicle speed in kilometres per hour as a ``float``.

        Raises:
            NrcException: If the ECU returns a Negative Response Code.
            DiagnosticTimeoutError: If the ECU does not reply in time.
            TransportError: If a CAN-level error occurs.
        """
        payload = self._builder.build_read_vehicle_speed_request()
        self._transport.send(payload)
        raw = self._transport.receive()
        self._decoder.validate_response(raw, expected_mode=0x01)
        return self._decoder.decode_vehicle_speed(raw)

    def get_throttle_position(self) -> float:
        """Request and decode the current Throttle Position.

        Returns:
            Throttle opening as a percentage (0.0–100.0) as a ``float``.

        Raises:
            NrcException: If the ECU returns a Negative Response Code.
            DiagnosticTimeoutError: If the ECU does not reply in time.
            TransportError: If a CAN-level error occurs.
        """
        payload = self._builder.build_read_throttle_position_request()
        self._transport.send(payload)
        raw = self._transport.receive()
        self._decoder.validate_response(raw, expected_mode=0x01)
        return self._decoder.decode_throttle_position(raw)

    def get_engine_load(self) -> float:
        """Request and decode the current Calculated Engine Load.

        Returns:
            Calculated engine load as a percentage (0.0–100.0) as a ``float``.

        Raises:
            NrcException: If the ECU returns a Negative Response Code.
            DiagnosticTimeoutError: If the ECU does not reply in time.
            TransportError: If a CAN-level error occurs.
        """
        payload = self._builder.build_read_engine_load_request()
        self._transport.send(payload)
        raw = self._transport.receive()
        self._decoder.validate_response(raw, expected_mode=0x01)
        return self._decoder.decode_engine_load(raw)

    # ------------------------------------------------------------------ #
    # Mode 0x03 / 0x04 — Diagnostic Trouble Codes                        #
    # ------------------------------------------------------------------ #

    def get_dtcs(self) -> list[Dtc]:
        """Request and decode all stored Diagnostic Trouble Codes.

        Returns:
            A ``list`` of :class:`~core.models.dtc.Dtc` instances.
            Returns an empty list when no faults are stored.

        Raises:
            NrcException: If the ECU returns a Negative Response Code.
            DiagnosticTimeoutError: If the ECU does not reply in time.
            TransportError: If a CAN-level error occurs.
        """
        self._transport.send(self._builder.build_read_dtcs_request())
        raw = self._transport.receive()
        self._decoder.validate_response(raw, expected_mode=0x03)
        return self._decoder.decode_dtcs(raw)

    def clear_dtcs(self) -> None:
        """Send a Mode 0x04 request to clear all stored DTCs.

        Raises:
            NrcException: If the ECU returns a Negative Response Code
                (e.g. 0x22 = conditionsNotCorrect).
            DiagnosticTimeoutError: If the ECU does not reply in time.
            TransportError: If a CAN-level error occurs.
        """
        self._transport.send(self._builder.build_clear_dtcs_request())
        raw = self._transport.receive()
        self._decoder.validate_response(raw, expected_mode=0x04)

    # ------------------------------------------------------------------ #
    # All Mode 0x01 PIDs — Snapshot                                       #
    # ------------------------------------------------------------------ #

    def get_snapshot(self) -> list[MonitorSample]:
        """Read all 18 registered Mode 0x01 PIDs in a single pass.

        Returns:
            Ordered list of :class:`~core.models.monitor_sample.MonitorSample`
            instances, one per PID, in PID-registry order.
        """
        _MAX_DRAIN = 10
        samples: list[MonitorSample] = []
        for pid_def in PIDS.values():
            self._transport.send(pid_def.request)
            raw = self._transport.receive()
            for _ in range(_MAX_DRAIN):
                if len(raw) < 2 or raw[1] == pid_def.pid:
                    break
                raw = self._transport.receive()
            self._decoder.validate_response(raw, expected_mode=0x01)
            if len(raw) >= 2 and raw[1] != pid_def.pid:
                raise InvalidResponseError(
                    f"PID echo mismatch for 0x{pid_def.pid:02X}: "
                    f"got 0x{raw[1]:02X} after draining — raw: {bytes(raw).hex(' ').upper()}"
                )
            if len(raw) < pid_def.response_bytes:
                raise InvalidResponseError(
                    f"Response for PID 0x{pid_def.pid:02X} too short: "
                    f"expected {pid_def.response_bytes} bytes, got {len(raw)}"
                    f" — raw: {bytes(raw).hex(' ').upper()}"
                )
            value = pid_def.decode(raw)
            samples.append(
                MonitorSample(
                    pid=pid_def.pid,
                    name=pid_def.name,
                    value=value,
                    unit=pid_def.unit,
                    timestamp=time.monotonic(),
                )
            )
        return samples

    # ------------------------------------------------------------------ #
    # Mode 0x09 — Vehicle Information                                     #
    # ------------------------------------------------------------------ #

    def get_vin(self) -> str:
        """Request and decode the Vehicle Identification Number.

        Returns:
            The 17-character VIN string.

        Raises:
            NrcException: If the ECU returns a Negative Response Code.
            DiagnosticTimeoutError: If the ECU does not reply in time.
            TransportError: If a CAN-level error occurs.
            InvalidResponseError: If the decoded VIN is not 17 characters.
        """
        self._transport.send(self._builder.build_read_vin_request())
        raw = self._transport.receive()
        self._decoder.validate_response(raw, expected_mode=0x09)
        return self._decoder.decode_vin(raw)
