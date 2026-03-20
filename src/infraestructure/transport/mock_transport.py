"""In-memory mock transport for unit and integration testing.

Implements :class:`~core.interfaces.i_transport.ITransport` using a
pre-loaded response map that mirrors the exact Arduino ECU simulator
behaviour extracted from ``ecu_sim.ino``.  No CAN socket or OS resources
are used — the class is safe to instantiate in any test environment.
"""

from __future__ import annotations

from types import TracebackType

from core.exceptions import DiagnosticTimeoutError
from core.interfaces.i_transport import ITransport

# ---------------------------------------------------------------------------
# Default response map — mirrors the Arduino simulator at idle (RPM=850)
# ---------------------------------------------------------------------------

ARDUINO_DEFAULT_RESPONSES: dict[bytes, bytes] = {
    # Mode 0x01 — Current Data
    b"\x01\x04": b"\x41\x04\x1A",          # Engine Load ~10 %
    b"\x01\x05": b"\x41\x05\x60",          # Coolant Temp 56 °C
    b"\x01\x06": b"\x41\x06\x82",          # Short Fuel Trim Bank 1 +2 %
    b"\x01\x07": b"\x41\x07\x7E",          # Long Fuel Trim Bank 1 -1 %
    b"\x01\x0C": b"\x41\x0C\x0D\x48",      # Engine RPM 850
    b"\x01\x0D": b"\x41\x0D\x00",          # Vehicle Speed 0 km/h
    b"\x01\x0E": b"\x41\x0E\x94",          # Timing Advance 10 °
    b"\x01\x0F": b"\x41\x0F\x3C",          # Intake Air Temp 20 °C
    b"\x01\x10": b"\x41\x10\x00\x00",      # MAF Air Flow Rate 0.0 g/s
    b"\x01\x11": b"\x41\x11\x00",          # Throttle Position 0 %
    b"\x01\x1F": b"\x41\x1F\x00\x00",      # Runtime Since Start 0 s
    b"\x01\x23": b"\x41\x23\x00\x00",      # Fuel Rail Pressure 0 kPa
    b"\x01\x2F": b"\x41\x2F\xA6",          # Fuel Level ~65 %
    b"\x01\x31": b"\x41\x31\x05\xDC",      # Distance Since DTC Clear 1500 km
    b"\x01\x33": b"\x41\x33\x65",          # Barometric Pressure 101 kPa
    b"\x01\x42": b"\x41\x42\x30\x9A",      # Control Module Voltage 12.442 V
    b"\x01\x46": b"\x41\x46\x3A",          # Ambient Air Temp 18 °C
    b"\x01\x5C": b"\x41\x5C\x3C",          # Engine Oil Temp 20 °C
    # Mode 0x03 — Read stored DTCs (none active)
    b"\x03":     b"\x43\x00",
    # Mode 0x04 — Clear DTCs
    b"\x04":     b"\x44",
    # Mode 0x09 — VIN (post ISO-TP reassembly, 20 bytes)
    b"\x09\x02": b"\x49\x02\x01VSSZZZ6JZCR123456",
    # Unsupported request — NRC 0x11 (service not supported)
    b"\x01\xFF": b"\x7F\x01\x11",
}


class MockTransport(ITransport):
    """In-memory ITransport implementation backed by a static response map.

    Replaces the physical CAN/ISO-TP socket during testing.  Each call to
    :meth:`send` stores the payload; the subsequent call to :meth:`receive`
    performs a dictionary look-up and returns the pre-loaded response.

    Args:
        response_map: Mapping from request payload bytes to response payload
            bytes.  When ``None`` the full :data:`ARDUINO_DEFAULT_RESPONSES`
            map is used, which replicates the Arduino ECU simulator at idle.
        default_timeout: Not used at runtime by this mock, but stored for
            API compatibility with production transport implementations.

    Example::

        with MockTransport() as t:
            t.send(b'\\x01\\x0C')
            raw = t.receive()   # → b'\\x41\\x0C\\x0D\\x48'
    """

    def __init__(
        self,
        response_map: dict[bytes, bytes] | None = None,
        default_timeout: float = 1.0,
    ) -> None:
        """Initialise the mock transport with an optional custom response map.

        Args:
            response_map: Custom request-to-response mapping.  Defaults to
                :data:`ARDUINO_DEFAULT_RESPONSES` when ``None``.
            default_timeout: Timeout value stored for API parity with
                production transports; not enforced by this mock.
        """
        self._responses: dict[bytes, bytes] = (
            dict(ARDUINO_DEFAULT_RESPONSES) if response_map is None else dict(response_map)
        )
        self.default_timeout: float = default_timeout
        self._connected: bool = False
        self._last_sent: bytes | None = None

    # ------------------------------------------------------------------ #
    # ITransport — lifecycle                                              #
    # ------------------------------------------------------------------ #

    def connect(self) -> None:
        """Mark the transport as connected.

        Raises:
            ConnectionError: If the transport is already connected.
        """
        if self._connected:
            raise ConnectionError("MockTransport is already connected.")
        self._connected = True

    def disconnect(self) -> None:
        """Mark the transport as disconnected.

        No-op when the transport is already disconnected; does not raise.
        """
        self._connected = False

    # ------------------------------------------------------------------ #
    # ITransport — I/O                                                    #
    # ------------------------------------------------------------------ #

    def send(self, payload: bytes) -> None:
        """Store *payload* as the pending request to be answered by :meth:`receive`.

        Args:
            payload: OBD-II application payload bytes (no ISO-TP framing).

        Raises:
            RuntimeError: If the transport has not been connected yet.
        """
        if not self._connected:
            raise RuntimeError("Cannot send: MockTransport is not connected.")
        self._last_sent = payload

    def receive(self) -> bytes:
        """Return the pre-loaded response for the last sent payload.

        Raises:
            RuntimeError: If the transport has not been connected.
            RuntimeError: If :meth:`receive` is called before :meth:`send`.
            DiagnosticTimeoutError: If the last sent payload has no entry
                in the response map (simulates an ECU that does not respond).
        """
        if not self._connected:
            raise RuntimeError("Cannot receive: MockTransport is not connected.")
        if self._last_sent is None:
            raise RuntimeError("Cannot receive: no request has been sent yet.")
        response = self._responses.get(self._last_sent)
        if response is None:
            hex_req = self._last_sent.hex(" ").upper()
            raise DiagnosticTimeoutError(
                f"No response for request: {hex_req}"
            )
        return response

    # ------------------------------------------------------------------ #
    # ITransport — context manager                                        #
    # ------------------------------------------------------------------ #

    def __enter__(self) -> MockTransport:
        """Connect the transport and return ``self`` for use in a ``with`` block.

        Returns:
            This ``MockTransport`` instance, ready for I/O.

        Raises:
            ConnectionError: Propagated from :meth:`connect`.
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

    # ------------------------------------------------------------------ #
    # Test helper                                                         #
    # ------------------------------------------------------------------ #

    def inject_response(self, request: bytes, response: bytes) -> None:
        """Add or override a single entry in the response map at runtime.

        Useful in tests that need to simulate a specific ECU state (e.g.
        injecting an NRC for a particular PID) without constructing an
        entirely new ``MockTransport``.

        Args:
            request: The request payload bytes to match.
            response: The response payload bytes to return when *request*
                is received.
        """
        self._responses[request] = response
