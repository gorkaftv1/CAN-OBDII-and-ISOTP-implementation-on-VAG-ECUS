"""Abstract interface for the ISO-TP transport layer.

``ITransport`` is the sole gateway between the application and the
physical CAN bus. All socket management and ISO-TP framing details live
exclusively in concrete implementations (e.g. a ``CanIsoTpTransport``
backed by the ``can-isotp`` library).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from types import TracebackType


class ITransport(ABC):
    """Defines the contract for sending and receiving raw bytes over ISO-TP.

    Concrete implementations are responsible for managing the underlying
    CAN socket lifecycle (open, close) and delegating read/write operations
    to the ``can-isotp`` library. This interface is intentionally agnostic
    of the OBD-II application protocol — it handles only raw byte payloads.

    The class supports the context-manager protocol so callers can use it
    in a ``with`` statement and be guaranteed that the socket is closed
    even if an exception is raised inside the block::

        with transport:
            transport.send(b"\\x02\\x01\\x0C")
            raw = transport.receive()
    """

    @abstractmethod
    def connect(self) -> None:
        """Open the ISO-TP socket and prepare the transport for I/O.

        Binds to the configured CAN network interface, sets the TX ID
        (0x7E0) and RX ID (0x7E8), and applies any required socket
        options (e.g. padding byte 0xAA, 500 kbps bit rate).

        Raises:
            TransportError: If the socket cannot be opened or the CAN
                network interface is unavailable or in a bus-off state.
        """
        ...

    @abstractmethod
    def disconnect(self) -> None:
        """Close the ISO-TP socket and release all associated resources.

        Must be idempotent — calling ``disconnect`` on an already-closed
        transport must not raise an exception.

        Raises:
            TransportError: If the socket cannot be gracefully closed
                (e.g. OS-level error during ``close()``).
        """
        ...

    @abstractmethod
    def send(self, payload: bytes) -> None:
        """Transmit a raw byte payload to the ECU via ISO-TP.

        The method blocks until the ISO-TP layer has accepted the payload
        for transmission. For OBD-II Single Frames the payload must not
        exceed 7 bytes; the ISO-TP library handles segmentation for larger
        transfers (e.g. VIN multi-frame responses).

        Args:
            payload: Raw bytes to send. Example for an RPM request::

                transport.send(b"\\x02\\x01\\x0C")

        Raises:
            TransportError: If the transmission fails at the CAN layer
                (e.g. no acknowledgement from the bus, arbitration lost).
        """
        ...

    @abstractmethod
    def receive(self) -> bytes:
        """Block until a complete ISO-TP frame is received from the ECU.

        Waits for the ECU to transmit a response on RX ID 0x7E8. For
        multi-frame responses the ISO-TP layer performs frame reassembly
        transparently; this method always returns the fully reassembled
        payload.

        Returns:
            The reassembled payload bytes with ISO-TP framing stripped.
            Example positive RPM response payload::

                b"\\x04\\x41\\x0C\\x1A\\xF0"

        Raises:
            DiagnosticTimeoutError: If no frame arrives within the
                configured timeout window (typically P2_max = 50 ms for
                OBD-II).
            TransportError: If a CAN-layer error occurs during reception
                (e.g. socket read error, CAN error frame received).
        """
        ...

    @abstractmethod
    def __enter__(self) -> ITransport:
        """Enter the runtime context by opening the transport.

        Implementations define the exact setup sequence (e.g. calling
        :meth:`connect` and returning ``self``), so that subclasses such
        as ``IsoTpTransport`` and ``MockTransport`` can each control their
        own context-manager behaviour without being constrained by a
        concrete base-class implementation.

        Returns:
            This ``ITransport`` instance, ready for I/O.

        Raises:
            TransportError: If the transport cannot be initialised.
        """
        ...

    @abstractmethod
    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool | None:
        """Exit the runtime context by closing the transport.

        Calls :meth:`disconnect` unconditionally, ensuring the socket is
        released regardless of whether an exception was raised.

        Args:
            exc_type: The exception class, if an exception was raised
                inside the ``with`` block; ``None`` otherwise.
            exc_val: The exception instance; ``None`` if no exception.
            exc_tb: The traceback object; ``None`` if no exception.

        Returns:
            ``None`` (or ``False``) to propagate any exception raised
            inside the ``with`` block unchanged. Return ``True`` only if
            the implementation intentionally suppresses the exception.

        Note:
            Implementations must call the appropriate teardown logic
            (e.g. :meth:`disconnect`) unconditionally so that resources
            are released even when an exception is raised inside the
            ``with`` block.
        """
        ...
