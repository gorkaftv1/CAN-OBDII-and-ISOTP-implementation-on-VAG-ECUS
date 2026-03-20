"""Interactive OBD-II diagnostic CLI for the SEAT Ibiza 6J (2012).

Run directly:
    python scripts/cli.py

The menu operates against MockTransport by default, which faithfully
replicates the Arduino ECU simulator without requiring physical CAN hardware.
"""

from __future__ import annotations

import sys
import os
import time

# Allow running from the project root without installing as a package.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config.obd_pids import PIDS
from core.exceptions import DiagnosticTimeoutError, InvalidResponseError, NrcException
from core.models.monitor_sample import MonitorSample
from infraestructure.decoder.obd2_decoder import Obd2DataDecoder
from infraestructure.protocol.obd2_builder import Obd2ProtocolBuilder
from infraestructure.transport.isotp_transport import IsoTpTransport
from monitor.live_data_monitor import LiveDataMonitor
from session.diagnostic_session import DiagnosticSession

_BANNER = """\
╔══════════════════════════════════════════════╗
║  SEAT Ibiza 6J 2012 — OBD-II Diagnostic Tool ║
║  Mode: SIMULATOR (MockTransport)             ║
╚══════════════════════════════════════════════╝"""

_SEP = "─" * 48

_MENU = """\
  [1]  Live data          (5 core PIDs, single snapshot)
  [2]  Extended live data (all 18 PIDs, single snapshot)
  [3]  Read DTCs
  [4]  Clear DTCs
  [5]  Read VIN
  [6]  Live monitor       (5 core PIDs, continuous)
  [0]  Exit"""

# PIDs polled by the live monitor, in display order.
_MONITOR_PIDS = [0x05, 0x04, 0x0C, 0x0D, 0x11]
_MONITOR_PID_SET = frozenset(_MONITOR_PIDS)


# ---------------------------------------------------------------------------
# Menu option handlers
# ---------------------------------------------------------------------------

def _option_live_data(session: DiagnosticSession) -> None:
    rows = [
        ("RPM",          session.get_engine_rpm(),          "rpm"),
        ("Coolant Temp", session.get_coolant_temp(),        "°C"),
        ("Speed",        session.get_vehicle_speed(),       "km/h"),
        ("Throttle Pos", session.get_throttle_position(),   "%"),
        ("Engine Load",  session.get_engine_load(),         "%"),
    ]
    print(_SEP)
    for label, value, unit in rows:
        print(f"  {label:<22} : {value:>8.2f} {unit}")


def _option_extended_live_data(session: DiagnosticSession) -> None:
    print(_SEP)
    transport = session._transport
    for pid_def in PIDS.values():
        transport.send(pid_def.request)
        raw = transport.receive()
        value = pid_def.decode(raw)
        print(f"  {pid_def.name:<30} : {value:>8.2f} {pid_def.unit}")


def _option_read_dtcs(session: DiagnosticSession) -> None:
    dtcs = session.get_dtcs()
    print(_SEP)
    if not dtcs:
        print("  No DTCs stored.")
    else:
        for dtc in dtcs:
            print(f"  [{dtc.code}]  {dtc.description}")


def _option_clear_dtcs(session: DiagnosticSession) -> None:
    print(_SEP)
    answer = input("  Clear all DTCs? (y/N): ")
    if answer.strip().lower() == "y":
        session.clear_dtcs()
        print("  DTCs cleared successfully.")
    else:
        print("  Cancelled.")


def _option_read_vin(session: DiagnosticSession) -> None:
    vin = session.get_vin()
    print(_SEP)
    print(f"  VIN: {vin}")


def _option_live_monitor(session: DiagnosticSession) -> None:
    import threading

    latest: dict[int, MonitorSample] = {}
    lock = threading.Lock()
    samples_this_cycle = [0]

    def _print_frame() -> None:
        ts = time.strftime("%H:%M:%S")
        print(f"\n{_SEP}  {ts}")
        for pid in _MONITOR_PIDS:
            s = latest[pid]
            print(f"  {s.name:<30} : {s.value:>8.2f} {s.unit}")
        print(_SEP)
        sys.stdout.flush()

    def on_sample(s: MonitorSample) -> None:
        with lock:
            latest[s.pid] = s
            samples_this_cycle[0] += 1
            if samples_this_cycle[0] >= len(_MONITOR_PIDS):
                samples_this_cycle[0] = 0
                _print_frame()

    def on_error(pid: int, exc: Exception) -> None:
        print(f"  [WARN] PID 0x{pid:02X}: {exc}")

    monitor = LiveDataMonitor(
        transport=session._transport,
        decoder=Obd2DataDecoder(),
        pid_ids=_MONITOR_PID_SET,
        interval_ms=500,
        on_sample=on_sample,
        on_error=on_error,
    )
    print("  Live monitor started — press Enter to stop.")
    with monitor:
        input()
    print("  Live monitor stopped.")


# ---------------------------------------------------------------------------
# Main menu loop
# ---------------------------------------------------------------------------

_HANDLERS = {
    "1": _option_live_data,
    "2": _option_extended_live_data,
    "3": _option_read_dtcs,
    "4": _option_clear_dtcs,
    "5": _option_read_vin,
    "6": _option_live_monitor,
}


def run_menu(session: DiagnosticSession) -> None:
    """Run the interactive menu loop until the user selects 0.

    Args:
        session: An open :class:`~session.diagnostic_session.DiagnosticSession`
            to use for all diagnostic operations.
    """
    while True:
        print()
        print(_MENU)
        choice = input("\n  Select option: ").strip()

        if choice == "0":
            print("  Goodbye.")
            break

        handler = _HANDLERS.get(choice)
        if handler is None:
            print("  Unknown option — please enter a number between 0 and 6.")
            continue

        try:
            handler(session)
        except (NrcException, DiagnosticTimeoutError, InvalidResponseError) as e:
            print(f"  [ERROR] {e}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print(_BANNER)

    transport = IsoTpTransport(channel="can0", tx_id=0x7E0, rx_id=0x7E8)
    session = DiagnosticSession(transport, Obd2ProtocolBuilder(), Obd2DataDecoder())

    with session:
        run_menu(session)
