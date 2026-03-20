"""Concrete background-thread implementation of IDataMonitor."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable

from config.obd_pids import PIDS, PidDefinition
from core.interfaces.i_data_decoder import IDataDecoder
from core.interfaces.i_data_monitor import IDataMonitor
from core.interfaces.i_transport import ITransport
from core.models.monitor_sample import MonitorSample


class LiveDataMonitor(IDataMonitor):
    """Polls a fixed set of Mode 0x01 PIDs in a daemon thread and forwards
    each decoded sample to a caller-supplied callback.

    Example::

        monitor = LiveDataMonitor(
            transport=transport,
            decoder=decoder,
            pid_ids=frozenset({0x0C, 0x0D, 0x05}),
            interval_ms=500,
            on_sample=lambda s: print(f"{s.name}: {s.value} {s.unit}"),
        )
        with monitor:
            input("Press Enter to stop")
    """

    _JOIN_TIMEOUT_MULTIPLIER = 3.0

    def __init__(
        self,
        transport: ITransport,
        decoder: IDataDecoder,
        pid_ids: frozenset[int],
        interval_ms: int,
        on_sample: Callable[[MonitorSample], None],
        on_error: Callable[[int, Exception], None] | None = None,
    ) -> None:
        if not pid_ids:
            raise ValueError("pid_ids must not be empty")
        if interval_ms < 1:
            raise ValueError("interval_ms must be >= 1")

        # Eager validation — raises KeyError immediately for unknown PIDs
        self._pid_defs: list[PidDefinition] = [PIDS[p] for p in sorted(pid_ids)]

        self._transport = transport
        self._decoder = decoder
        self._interval_s = interval_ms / 1000.0
        self._on_sample = on_sample
        self._on_error = on_error

        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    # ------------------------------------------------------------------ #
    # Lifecycle                                                            #
    # ------------------------------------------------------------------ #

    def start(self) -> None:
        """Launch the background polling daemon thread.

        Raises:
            RuntimeError: If the monitor is already running.
        """
        if self.is_running:
            raise RuntimeError("LiveDataMonitor is already running")
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Signal the thread to exit and block until it terminates. No-op if not running."""
        if not self.is_running:
            return
        self._stop_event.set()
        timeout = self._interval_s * self._JOIN_TIMEOUT_MULTIPLIER + 1.0
        self._thread.join(timeout=timeout)  # type: ignore[union-attr]
        self._thread = None

    @property
    def is_running(self) -> bool:
        """True while the daemon thread is alive."""
        return self._thread is not None and self._thread.is_alive()

    # ------------------------------------------------------------------ #
    # Background thread                                                   #
    # ------------------------------------------------------------------ #

    def _poll_loop(self) -> None:
        while not self._stop_event.is_set():
            for pid_def in self._pid_defs:
                if self._stop_event.is_set():
                    return
                self._poll_single(pid_def)
            self._stop_event.wait(timeout=self._interval_s)

    def _poll_single(self, pid_def: PidDefinition) -> None:
        try:
            self._transport.send(pid_def.request)
            raw = self._transport.receive()
            ts = time.monotonic()
            self._decoder.validate_response(raw, expected_mode=0x01)
            value = pid_def.decode(raw)
            self._on_sample(
                MonitorSample(
                    pid=pid_def.pid,
                    name=pid_def.name,
                    value=value,
                    unit=pid_def.unit,
                    timestamp=ts,
                )
            )
        except Exception as exc:
            if self._on_error is not None:
                self._on_error(pid_def.pid, exc)
