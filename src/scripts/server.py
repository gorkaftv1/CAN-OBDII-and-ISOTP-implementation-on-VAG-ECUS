"""Entry point del servidor BLE OBD-II para Raspberry Pi.

Levanta un servidor BLE GATT (Nordic UART Service) que permite a la app
móvil React Native conectarse por Bluetooth Low Energy y recibir datos
diagnósticos en tiempo real del vehículo.

Uso:
    python scripts/server.py

Prerequisitos en la Raspberry Pi:
    sudo apt install libbluetooth-dev bluez
    pip install bless
"""

from __future__ import annotations

import asyncio
import sys
import os
import threading

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from infraestructure.decoder.obd2_decoder import Obd2DataDecoder
from infraestructure.logging.sqlite_logger import SqliteDataLogger
from infraestructure.protocol.obd2_builder import Obd2ProtocolBuilder
from infraestructure.transport.isotp_transport import IsoTpTransport
from infraestructure.transport.logging_transport import LoggingTransport
from session.diagnostic_session import DiagnosticSession
from session.logged_diagnostic_session import LoggedDiagnosticSession
from server.bluetooth_server import BLEDiagServer
from server.bt_command_handler import BtCommandHandler

_DB_PATH = "diagnostics.db"


async def main() -> None:
    print("╔══════════════════════════════════════════════╗")
    print("║  SEAT Ibiza 6J 2012 — BLE OBD-II Server      ║")
    print("╚══════════════════════════════════════════════╝")

    # ── Capa de transporte ─────────────────────────────────────────────
    raw_transport = IsoTpTransport(channel="can0", tx_id=0x7E0, rx_id=0x7E8)
    log_transport = LoggingTransport(raw_transport)
    transport_lock = threading.Lock()

    # ── Logger SQLite ──────────────────────────────────────────────────
    logger = SqliteDataLogger(_DB_PATH)
    session_id = logger.start_session("BLE server session")
    print(f"[LOG] Session #{session_id} → {_DB_PATH}")

    # ── Sesión diagnóstica ─────────────────────────────────────────────
    inner_session = DiagnosticSession(
        log_transport, Obd2ProtocolBuilder(), Obd2DataDecoder()
    )
    session = LoggedDiagnosticSession(
        inner_session, logger, session_id, log_transport
    )

    # ── Servidor BLE (se crea antes para poder pasar notify al handler) ─
    ble_server = BLEDiagServer.__new__(BLEDiagServer)

    handler = BtCommandHandler(
        session=session,
        logger=logger,
        session_id=session_id,
        transport=log_transport,
        transport_lock=transport_lock,
        push_callback=ble_server.notify,
    )

    # Inicializar el servidor con el handler ya construido
    BLEDiagServer.__init__(ble_server, handler)

    try:
        with session:
            await ble_server.start()  # blocking hasta Ctrl+C
    finally:
        logger.end_session(session_id)
        logger.close()
        print(f"[LOG] Session #{session_id} closed.")


if __name__ == "__main__":
    asyncio.run(main())
