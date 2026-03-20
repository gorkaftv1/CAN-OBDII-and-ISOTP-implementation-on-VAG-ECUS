"""Interactive OBD-II diagnostic CLI for the SEAT Ibiza 6J (2012).

Run directly:
    python scripts/cli.py

The menu operates against MockTransport by default, which faithfully
replicates the Arduino ECU simulator without requiring physical CAN hardware.
"""

from __future__ import annotations

import sys
import os

# Allow running from the project root without installing as a package.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config.obd_pids import PIDS
from core.exceptions import DiagnosticTimeoutError, InvalidResponseError, NrcException
from infraestructure.decoder.obd2_decoder import Obd2DataDecoder
from infraestructure.protocol.obd2_builder import Obd2ProtocolBuilder
from infraestructure.transport.isotp_transport import IsoTpTransport
from session.diagnostic_session import DiagnosticSession

_BANNER = """\
╔══════════════════════════════════════════════╗
║  SEAT Ibiza 6J 2012 — OBD-II Diagnostic Tool ║
║  Mode: SIMULATOR (MockTransport)             ║
╚══════════════════════════════════════════════╝"""

_SEP = "─" * 48

_MENU = """\
  [1]  Live data          (5 core PIDs)
  [2]  Extended live data (all 18 PIDs)
  [3]  Read DTCs
  [4]  Clear DTCs
  [5]  Read VIN
  [0]  Exit"""


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


# ---------------------------------------------------------------------------
# Main menu loop
# ---------------------------------------------------------------------------

_HANDLERS = {
    "1": _option_live_data,
    "2": _option_extended_live_data,
    "3": _option_read_dtcs,
    "4": _option_clear_dtcs,
    "5": _option_read_vin,
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
            print("  Unknown option — please enter a number between 0 and 5.")
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
