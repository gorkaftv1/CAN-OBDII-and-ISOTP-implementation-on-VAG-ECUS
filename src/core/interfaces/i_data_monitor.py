"""Abstract interface for continuous background OBD-II polling monitors."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from types import TracebackType

from core.interfaces.i_data_decoder import IDataDecoder
from core.interfaces.i_transport import ITransport
from core.models.monitor_sample import MonitorSample


class IDataMonitor(ABC):
    """Continuous background polling monitor for Mode 0x01 OBD-II PIDs.

    The monitor does NOT manage transport lifecycle. The caller connects
    the transport before start() and disconnects after stop().
    """

    def __init__(
        self,
        transport: ITransport,
        decoder: IDataDecoder,
        pid_ids: frozenset[int],
        interval_ms: int,
        on_sample: Callable[[MonitorSample], None],
        on_error: Callable[[int, Exception], None] | None = None,
    ) -> None:
        """Inject collaborators without starting any I/O.

        Args:
            transport: Already-connected transport. Monitor never calls connect/disconnect.
            decoder: Decoder for validate_response calls.
            pid_ids: Frozen set of Mode 0x01 PID bytes. Every value must be
                a key in config.obd_pids.PIDS.
            interval_ms: Milliseconds between end of one cycle and start of next.
            on_sample: Called on background thread for each successful MonitorSample.
                Must not block for longer than interval_ms.
            on_error: Optional. Called on background thread as (pid, exc) when a
                single PID poll fails. If None, per-PID errors are silently skipped.
        """
        ...

    @abstractmethod
    def start(self) -> None:
        """Launch the background polling daemon thread.

        Raises:
            RuntimeError: If already running.
        """
        ...

    @abstractmethod
    def stop(self) -> None:
        """Signal the thread to exit and block until it terminates. No-op if not running."""
        ...

    @property
    @abstractmethod
    def is_running(self) -> bool:
        """True while the daemon thread is alive."""
        ...

    # Concrete context-manager protocol (same pattern as IDiagnosticSession)
    def __enter__(self) -> "IDataMonitor":
        self.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.stop()
