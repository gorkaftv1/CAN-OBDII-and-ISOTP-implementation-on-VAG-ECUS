"""Custom domain exceptions for the OBD-II diagnostic tool.

All exceptions are defined here to keep the domain layer self-contained
and free of framework dependencies.
"""


class NrcException(Exception):
    """Raised when the ECU returns a Negative Response Code (NRC).

    The ECU signals rejection by sending a frame whose first byte is
    0x7F, followed by the echoed mode byte and an NRC code that
    describes the reason for the refusal (e.g. 0x12 = subFunctionNotSupported).

    Attributes:
        mode: The OBD-II mode byte that triggered the negative response.
        nrc_code: The Negative Response Code byte returned by the ECU.

    Example::

        try:
            session.get_engine_rpm()
        except NrcException as exc:
            print(exc)  # "NRC for mode 0x01: code 0x22"
    """

    def __init__(self, mode: int, nrc_code: int) -> None:
        """Initialise the exception with mode and NRC code.

        Args:
            mode: The OBD-II mode byte from the request (e.g. 0x01).
            nrc_code: The NRC byte from the ECU response (e.g. 0x22).
        """
        self.mode = mode
        self.nrc_code = nrc_code
        super().__init__(
            f"NRC for mode 0x{mode:02X}: code 0x{nrc_code:02X}"
        )


class TransportError(Exception):
    """Raised for low-level CAN / ISO-TP communication failures.

    Covers socket errors, missing network interfaces, bus-off conditions,
    and any other failure that occurs below the OBD-II application layer.
    """


class DiagnosticTimeoutError(Exception):
    """Raised when a diagnostic operation exceeds its timeout threshold.

    Note:
        Deliberately inherits from ``Exception`` rather than the built-in
        ``TimeoutError`` to avoid shadowing the standard library symbol and
        to allow callers to distinguish CAN-level timeouts from generic ones.
    """


class InvalidResponseError(Exception):
    """Raised when a structurally malformed payload is received from the ECU.

    Examples of malformed payloads include frames that are too short to
    contain the expected mode echo, frames with an unexpected length for
    the requested PID, or a VIN payload whose decoded length is not 17.
    """
