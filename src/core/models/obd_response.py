"""Domain model for OBD-II ECU response frames.

Provides an immutable value object that wraps the parsed fields of a
positive ECU response, making them available under clear, typed attributes.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ObdResponse:
    """Encapsulates a parsed positive response frame from the ECU.

    An ``ObdResponse`` is produced by ``IDataDecoder.validate_response``
    after it confirms that the raw frame is structurally valid and carries
    the expected mode echo (``raw[0] == expected_mode + 0x40``).

    Instances are immutable (``frozen=True``) so they can be safely passed
    between layers without risk of accidental mutation.

    Attributes:
        mode: The response mode byte as echoed by the ECU, i.e. the
            requested mode ``+ 0x40`` (e.g. ``0x41`` for a Mode 0x01 reply).
        pid: The Parameter ID (or InfoType) echoed in the response byte
            at index 1 (e.g. ``0x0C`` for Engine RPM).
        data: The raw data payload bytes that follow the mode and PID echo
            bytes, ready for formula-based decoding.
        is_positive: ``True`` when the frame is a positive acknowledgement;
            ``False`` is reserved for future use — callers should treat
            negative frames via ``NrcException`` instead.

    Example::

        resp = ObdResponse(mode=0x41, pid=0x0C, data=bytes([0x1A, 0xF0]), is_positive=True)
        print(len(resp))   # 2
        print(repr(resp))  # ObdResponse(mode=0x41, pid=0x0C, data=0x1AF0, is_positive=True)
    """

    mode: int
    pid: int
    data: bytes
    is_positive: bool

    def __len__(self) -> int:
        """Return the number of payload bytes in the data field.

        Returns:
            ``len(self.data)`` — the count of decoded data bytes, not
            counting the mode or PID echo bytes.
        """
        ...

    def __repr__(self) -> str:
        """Return a hex-notation developer representation of the response.

        All integer fields are shown with ``0x`` prefixes; ``data`` is
        rendered as a single hex string without spaces.

        Returns:
            A string of the form::

                ObdResponse(mode=0x41, pid=0x0C, data=0x1AF0, is_positive=True)

            When ``data`` is empty, the ``data`` field renders as ``0x``.
        """
        ...
