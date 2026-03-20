"""Abstract interface for the high-level OBD-II diagnostic session.

``IDiagnosticSession`` is the façade that callers interact with. It
coordinates ``ITransport``, ``IProtocolBuilder``, and ``IDataDecoder``
to expose a clean, intent-driven API: one method per diagnostic data point.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from types import TracebackType

from core.interfaces.i_data_decoder import IDataDecoder
from core.interfaces.i_protocol_builder import IProtocolBuilder
from core.interfaces.i_transport import ITransport
from core.models.dtc import Dtc


class IDiagnosticSession(ABC):
    """High-level orchestrator for OBD-II diagnostic operations.

    Concrete implementations coordinate the three collaborators injected
    via the constructor to implement the full request-validate-decode
    pipeline for each supported data point.

    Typical usage::

        with session:
            rpm   = session.get_engine_rpm()
            dtcs  = session.get_dtcs()
            vin   = session.get_vin()

    Attributes:
        _transport: The ISO-TP transport used for all CAN I/O.
        _builder: Builds raw OBD-II request frames.
        _decoder: Validates and decodes raw ECU responses.
    """

    def __init__(
        self,
        transport: ITransport,
        builder: IProtocolBuilder,
        decoder: IDataDecoder,
    ) -> None:
        """Inject the three collaborators required by the session.

        Args:
            transport: Concrete :class:`~core.interfaces.i_transport.ITransport`
                implementation that handles CAN socket I/O.
            builder: Concrete
                :class:`~core.interfaces.i_protocol_builder.IProtocolBuilder`
                implementation that constructs raw OBD-II request frames.
            decoder: Concrete
                :class:`~core.interfaces.i_data_decoder.IDataDecoder`
                implementation that validates responses and applies SAE J1979
                decoding formulas.
        """
        ...

    # ------------------------------------------------------------------ #
    # Session lifecycle                                                   #
    # ------------------------------------------------------------------ #

    @abstractmethod
    def open(self) -> None:
        """Open the diagnostic session by connecting the underlying transport.

        Must be called (or the context-manager protocol used) before any
        ``get_*`` / ``clear_*`` method is invoked.

        Raises:
            TransportError: If the underlying transport cannot be opened.
        """
        ...

    @abstractmethod
    def close(self) -> None:
        """Close the diagnostic session and release all transport resources.

        Must be idempotent — calling ``close`` on an already-closed session
        must not raise an exception.

        Raises:
            TransportError: If the underlying transport cannot be closed
                cleanly.
        """
        ...

    def __enter__(self) -> IDiagnosticSession:
        """Enter the runtime context by opening the session.

        Calls :meth:`open` and returns ``self`` so the session can be used
        directly inside the ``with`` block.

        Returns:
            This ``IDiagnosticSession`` instance.

        Raises:
            TransportError: Propagated from :meth:`open`.
        """
        ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool | None:
        """Exit the runtime context by closing the session.

        Calls :meth:`close` unconditionally, ensuring transport resources
        are released regardless of whether an exception was raised.

        Args:
            exc_type: The exception class, if an exception was raised
                inside the ``with`` block; ``None`` otherwise.
            exc_val: The exception instance; ``None`` if no exception.
            exc_tb: The traceback object; ``None`` if no exception.

        Returns:
            ``None`` (or ``False``) to propagate any exception raised
            inside the ``with`` block unchanged.
        """
        ...

    # ------------------------------------------------------------------ #
    # Mode 0x01 — Live Data                                               #
    # ------------------------------------------------------------------ #

    @abstractmethod
    def get_engine_rpm(self) -> float:
        """Request and decode the current Engine RPM.

        Sends a Mode 0x01 / PID 0x0C request and applies the SAE J1979
        formula ``((A * 256) + B) / 4`` to the two data bytes.

        Returns:
            Engine speed in revolutions per minute (rpm) as a ``float``.

        Raises:
            NrcException: If the ECU replies with a Negative Response Code.
            DiagnosticTimeoutError: If the ECU does not reply within the
                P2_max timeout window.
            TransportError: If a CAN-level error occurs during send or
                receive.
        """
        ...

    @abstractmethod
    def get_coolant_temp(self) -> float:
        """Request and decode the current Engine Coolant Temperature.

        Sends a Mode 0x01 / PID 0x05 request and applies the SAE J1979
        formula ``A - 40`` to the single data byte.

        Returns:
            Coolant temperature in degrees Celsius as a ``float``.

        Raises:
            NrcException: If the ECU replies with a Negative Response Code.
            DiagnosticTimeoutError: If the ECU does not reply in time.
            TransportError: If a CAN-level error occurs.
        """
        ...

    @abstractmethod
    def get_vehicle_speed(self) -> float:
        """Request and decode the current Vehicle Speed.

        Sends a Mode 0x01 / PID 0x0D request. The single data byte encodes
        speed directly in km/h (SAE J1979 formula: ``Speed = A``).

        Returns:
            Vehicle speed in kilometres per hour as a ``float``.

        Raises:
            NrcException: If the ECU replies with a Negative Response Code.
            DiagnosticTimeoutError: If the ECU does not reply in time.
            TransportError: If a CAN-level error occurs.
        """
        ...

    @abstractmethod
    def get_throttle_position(self) -> float:
        """Request and decode the current Throttle Position.

        Sends a Mode 0x01 / PID 0x11 request and applies the SAE J1979
        formula ``(A * 100) / 255`` to the single data byte.

        Returns:
            Throttle opening as a percentage (0.0 – 100.0) as a ``float``.

        Raises:
            NrcException: If the ECU replies with a Negative Response Code.
            DiagnosticTimeoutError: If the ECU does not reply in time.
            TransportError: If a CAN-level error occurs.
        """
        ...

    @abstractmethod
    def get_engine_load(self) -> float:
        """Request and decode the current Calculated Engine Load.

        Sends a Mode 0x01 / PID 0x04 request and applies the SAE J1979
        formula ``(A * 100) / 255`` to the single data byte.

        Returns:
            Calculated engine load as a percentage (0.0 – 100.0) as a
            ``float``.

        Raises:
            NrcException: If the ECU replies with a Negative Response Code.
            DiagnosticTimeoutError: If the ECU does not reply in time.
            TransportError: If a CAN-level error occurs.
        """
        ...

    # ------------------------------------------------------------------ #
    # Mode 0x03 / 0x04 — Diagnostic Trouble Codes                        #
    # ------------------------------------------------------------------ #

    @abstractmethod
    def get_dtcs(self) -> list[Dtc]:
        """Request and decode all stored Diagnostic Trouble Codes.

        Sends a Mode 0x03 request and delegates decoding of the response
        payload to ``IDataDecoder.decode_dtcs``.

        Returns:
            A ``list`` of :class:`~core.models.dtc.Dtc` instances in the
            order they appear in the ECU response.  Returns an empty list
            when no faults are currently stored.

        Raises:
            NrcException: If the ECU replies with a Negative Response Code.
            DiagnosticTimeoutError: If the ECU does not reply in time.
            TransportError: If a CAN-level error occurs.
        """
        ...

    @abstractmethod
    def clear_dtcs(self) -> None:
        """Send a Mode 0x04 request to clear all stored DTCs and freeze-frame data.

        The ECU performs the clear operation and responds with a positive
        acknowledgement (0x44). No data is returned.

        Raises:
            NrcException: If the ECU replies with a Negative Response Code
                (e.g. 0x22 = conditionsNotCorrect if the engine is running).
            DiagnosticTimeoutError: If the ECU does not reply in time.
            TransportError: If a CAN-level error occurs.
        """
        ...

    # ------------------------------------------------------------------ #
    # Mode 0x09 — Vehicle Information                                     #
    # ------------------------------------------------------------------ #

    @abstractmethod
    def get_vin(self) -> str:
        """Request and decode the Vehicle Identification Number.

        Sends a Mode 0x09 / InfoType 0x02 request. The ECU response
        typically spans multiple ISO-TP frames; reassembly is handled
        transparently by the transport layer. The 17-character VIN is then
        extracted by ``IDataDecoder.decode_vin``.

        Returns:
            The 17-character VIN string (ISO 3779 / SAE J1979 format).

        Raises:
            NrcException: If the ECU replies with a Negative Response Code.
            DiagnosticTimeoutError: If the ECU does not reply in time.
            TransportError: If a CAN-level error occurs.
            InvalidResponseError: If the decoded VIN is not exactly 17
                characters long.
        """
        ...
