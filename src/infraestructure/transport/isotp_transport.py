"""ISO-TP transport implementation for a physical CAN bus.

Uses the ``python-can`` and ``can-isotp`` libraries to communicate with
the ECU over the ``socketcan`` interface exposed by the Waveshare RS485
CAN HAT (MCP2515, 12 MHz, 500 kbps).
"""

from __future__ import annotations

import time
from types import TracebackType

import can
import isotp

from config.can_config import (
    CAN_RX_ID,
    CAN_TX_ID,
    ISOTP_CF_SEPARATION_MS,
    ISOTP_PADDING_BYTE,
)
from core.exceptions import DiagnosticTimeoutError
from core.interfaces.i_transport import ITransport


class IsoTpTransport(ITransport):
    """Concrete ITransport backed by a physical CAN socket via ISO-TP.

    Wraps ``python-can`` and ``can-isotp`` to provide ISO 15765-2
    compliant framing over the ``socketcan`` kernel interface.  The
    class supports the context-manager protocol so the CAN bus is
    always shut down cleanly even when an exception is raised.

    Args:
        channel: SocketCAN network interface name (e.g. ``"can0"``).
        tx_id: 11-bit CAN ID used for requests (scanner → ECU).
        rx_id: 11-bit CAN ID used for responses (ECU → scanner).
        timeout: Maximum time in seconds to wait for a complete ISO-TP
            response before raising :class:`~core.exceptions.DiagnosticTimeoutError`.

    Example::

        with IsoTpTransport(channel="can0") as t:
            t.send(b"\\x01\\x0C")
            raw = t.receive()
    """

    def __init__(
        self,
        channel: str = "can0",
        tx_id: int = CAN_TX_ID,
        rx_id: int = CAN_RX_ID,
        timeout: float = 2.0,
    ) -> None:
        """Prepare the ISO-TP address and parameters without opening the socket.

        Args:
            channel: SocketCAN interface name (default ``"can0"``).
            tx_id: CAN ID for outgoing frames (default :data:`~config.can_config.CAN_TX_ID`).
            rx_id: CAN ID for incoming frames (default :data:`~config.can_config.CAN_RX_ID`).
            timeout: Response timeout in seconds (default ``2.0``).
        """
        self._channel = channel
        self._timeout = timeout

        self._address = isotp.Address(
            addressing_mode=isotp.AddressingMode.Normal_11bits,
            txid=tx_id,
            rxid=rx_id,
        )

        self._params: dict = {
            "stmin": ISOTP_CF_SEPARATION_MS,    # separation time between Consecutive Frames (ms)
            "blocksize": 0,                      # accept all frames without issuing a Flow Control
            "tx_padding": ISOTP_PADDING_BYTE,    # pad outgoing CAN frames to 8 bytes with 0xAA
        }

        self._stack: isotp.CanStack | None = None
        self._bus: can.BusABC | None = None

    # ------------------------------------------------------------------ #
    # ITransport — lifecycle                                              #
    # ------------------------------------------------------------------ #

    def connect(self) -> None:
        """Open the SocketCAN bus and initialise the ISO-TP stack.

        Raises:
            ConnectionError: If the transport is already connected.
            can.CanError: If the SocketCAN interface cannot be opened
                (e.g. ``can0`` is not up or the HAT is unavailable).
        """
        if self._stack is not None:
            raise ConnectionError("IsoTpTransport is already connected.")
        self._bus = can.Bus(channel=self._channel, interface="socketcan")
        # Drain stale frames that may linger in the kernel socket buffer
        # from a previous session before handing the bus to the ISO-TP stack.
        while self._bus.recv(timeout=0) is not None:
            pass
        self._stack = isotp.CanStack(
            self._bus,
            address=self._address,
            params=self._params,
        )

    def disconnect(self) -> None:
        """Shut down the CAN bus and release all associated resources.

        No-op when the transport is already disconnected; does not raise.
        """
        if self._stack is None:
            return
        self._bus.shutdown()
        self._stack = None
        self._bus = None

    # ------------------------------------------------------------------ #
    # ITransport — I/O                                                    #
    # ------------------------------------------------------------------ #

    def send(self, payload: bytes) -> None:
        """Transmit *payload* via ISO-TP and pump the stack until sent.

        Blocks until the ISO-TP layer has finished transmitting all frames
        (Single Frame or First Frame + Consecutive Frames) for *payload*.

        Args:
            payload: OBD-II application payload bytes (no ISO-TP framing).
                For a Mode 0x01 RPM request this is ``b'\\x01\\x0C'``.

        Raises:
            RuntimeError: If the transport is not connected.
        """
        if self._stack is None:
            raise RuntimeError("Cannot send: IsoTpTransport is not connected.")
        self._stack.send(payload)
        while self._stack.transmitting():
            self._stack.process()
            time.sleep(0.001)

    def receive(self) -> bytes:
        """Poll the ISO-TP stack until a complete response frame is available.

        Reassembles multi-frame responses transparently.  Raises
        :class:`~core.exceptions.DiagnosticTimeoutError` if no complete
        payload arrives within ``self._timeout`` seconds.

        Returns:
            The fully reassembled ISO-TP payload bytes with all framing
            stripped (ready for :class:`~core.interfaces.i_data_decoder.IDataDecoder`).

        Raises:
            RuntimeError: If the transport is not connected.
            DiagnosticTimeoutError: If the ECU does not respond within
                the configured timeout window.
        """
        if self._stack is None:
            raise RuntimeError("Cannot receive: IsoTpTransport is not connected.")
        deadline = time.monotonic() + self._timeout
        while time.monotonic() < deadline:
            self._stack.process()
            if self._stack.available():
                return self._stack.recv()
            time.sleep(0.001)
        raise DiagnosticTimeoutError(
            f"No response received within {self._timeout:.1f}s timeout."
        )

    # ------------------------------------------------------------------ #
    # ITransport — context manager                                        #
    # ------------------------------------------------------------------ #

    def __enter__(self) -> IsoTpTransport:
        """Connect the transport and return ``self`` for use in a ``with`` block.

        Returns:
            This ``IsoTpTransport`` instance, ready for I/O.

        Raises:
            ConnectionError: Propagated from :meth:`connect`.
            can.CanError: If the CAN interface cannot be opened.
        """
        self.connect()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool | None:
        """Disconnect the transport unconditionally on context-manager exit.

        Args:
            exc_type: Exception class raised inside the ``with`` block, or
                ``None`` if no exception occurred.
            exc_val: Exception instance, or ``None``.
            exc_tb: Traceback object, or ``None``.

        Returns:
            ``None`` — exceptions are never suppressed by this implementation.
        """
        self.disconnect()
        return None
