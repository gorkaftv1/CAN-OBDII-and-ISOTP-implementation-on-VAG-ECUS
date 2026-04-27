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
import logging
import os
import sys
import threading

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

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

# Fichero donde el usuario guarda su token personal (configurable una vez por SSH).
_TOKEN_FILE = os.path.expanduser("~/.seat_diag_token")
# Token de fallback si no se configura nada. Cámbialo antes de usar en producción.
_DEFAULT_TOKEN = "1234"


def _load_auth_token() -> str:
    """Prioridad: variable de entorno → fichero ~/.seat_diag_token → constante."""
    if token := os.environ.get("BLE_AUTH_TOKEN", "").strip():
        return token
    try:
        token = open(_TOKEN_FILE).read().strip()
        if token:
            return token
    except FileNotFoundError:
        pass
    return _DEFAULT_TOKEN


async def main() -> None:
    print("╔══════════════════════════════════════════════╗")
    print("║  SEAT Ibiza 6J 2012 — BLE OBD-II Server      ║")
    print("╚══════════════════════════════════════════════╝")

    # ── Token de autenticación BLE ─────────────────────────────────────
    auth_token = _load_auth_token()
    print(f"[BLE] Auth token activo (fuente: {'env' if os.environ.get('BLE_AUTH_TOKEN') else _TOKEN_FILE if os.path.exists(_TOKEN_FILE) else 'default'})")

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

    # ── Handler y servidor BLE ─────────────────────────────────────────
    # El handler se construye primero sin callback; se inyecta después de
    # crear el servidor para evitar la dependencia circular.
    handler = BtCommandHandler(
        session=session,
        logger=logger,
        session_id=session_id,
        transport=log_transport,
        transport_lock=transport_lock,
        auth_token=auth_token,
    )
    ble_server = BLEDiagServer(handler)
    handler.set_push_callback(ble_server.notify)

    try:
        with session:
            await ble_server.start()  # blocking hasta Ctrl+C
    finally:
        logger.end_session(session_id)
        logger.close()
        print(f"[LOG] Session #{session_id} closed.")


if __name__ == "__main__":
    asyncio.run(main())
