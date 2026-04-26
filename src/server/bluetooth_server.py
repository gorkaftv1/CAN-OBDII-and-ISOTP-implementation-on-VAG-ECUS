"""Servidor BLE GATT para la Raspberry Pi.

Expone el bus CAN/OBD-II a la app móvil usando Bluetooth Low Energy (BLE)
con el perfil Nordic UART Service (NUS). Compatible con Android e iOS.

UUIDs NUS:
    Service : 6E400001-B5A3-F393-E0A9-E50E24DCCA9E
    RX char : 6E400002-B5A3-F393-E0A9-E50E24DCCA9E  (app → Pi, write)
    TX char : 6E400003-B5A3-F393-E0A9-E50E24DCCA9E  (Pi → app, notify)

Prerequisitos en la Raspberry Pi (una sola vez):
    sudo apt install libbluetooth-dev bluez
    pip install bless

Protocolo de aplicación: NDJSON (un objeto JSON por línea terminada en '\\n').
"""

from __future__ import annotations

import asyncio
import json
import logging
import time

try:
    from bless import (  # type: ignore[import]
        BlessServer,
        BlessGATTCharacteristic,
        GATTCharacteristicProperties,
        GATTAttributePermissions,
    )
    _BLESS_AVAILABLE = True
except ImportError:
    _BLESS_AVAILABLE = False

from server.bt_command_handler import BtCommandHandler

logger = logging.getLogger(__name__)

# ── UUIDs Nordic UART Service ──────────────────────────────────────────────
_NUS_SERVICE = "6E400001-B5A3-F393-E0A9-E50E24DCCA9E"
_NUS_RX      = "6E400002-B5A3-F393-E0A9-E50E24DCCA9E"  # app → Pi (write)
_NUS_TX      = "6E400003-B5A3-F393-E0A9-E50E24DCCA9E"  # Pi → app (notify)

_BLE_NAME           = "SEAT_DIAG"
_MTU                = 512   # bytes máx por notificación; se fragmenta si hay más
_CLIENT_TIMEOUT_S   = 15.0  # segundos sin actividad → conexión considerada caída
_WATCHDOG_INTERVAL  = 5.0   # con qué frecuencia comprueba el watchdog


class BLEDiagServer:
    """
    Servidor BLE GATT basado en asyncio.

    Crea un peripheral con el perfil NUS. La app escribe comandos NDJSON
    en la característica RX y recibe respuestas por notificaciones en TX.

    Uso::

        server = BLEDiagServer(handler)
        asyncio.run(server.start())   # blocking hasta Ctrl+C
    """

    def __init__(self, handler: BtCommandHandler) -> None:
        if not _BLESS_AVAILABLE:
            raise RuntimeError(
                "bless no está instalado. Ejecuta: pip install bless"
            )
        self._handler = handler
        self._server: BlessServer | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._recv_buf: str = ""
        self._stop_event: asyncio.Event | None = None
        self._last_rx_time: float = 0.0
        self._client_connected: bool = False
        self._watchdog_task: asyncio.Task | None = None

    # ── Ciclo de vida ──────────────────────────────────────────────────

    async def start(self) -> None:
        """Arrancar el servidor BLE. Bloquea hasta KeyboardInterrupt o stop()."""
        self._loop = asyncio.get_event_loop()
        self._stop_event = asyncio.Event()
        self._last_rx_time = time.time()

        self._server = BlessServer(name=_BLE_NAME, loop=self._loop)
        self._server.read_request_func  = self._on_read
        self._server.write_request_func = self._on_write

        # Servicio NUS
        await self._server.add_new_service(_NUS_SERVICE)

        # RX: la app escribe aquí (comandos JSON)
        await self._server.add_new_characteristic(
            _NUS_SERVICE,
            _NUS_RX,
            GATTCharacteristicProperties.write
            | GATTCharacteristicProperties.write_without_response,
            None,
            GATTAttributePermissions.writeable,
        )

        # TX: la Pi notifica aquí (respuestas + samples en streaming)
        await self._server.add_new_characteristic(
            _NUS_SERVICE,
            _NUS_TX,
            GATTCharacteristicProperties.notify,
            None,
            GATTAttributePermissions.readable,
        )

        await self._server.start()
        print(f"[BLE] Anunciando '{_BLE_NAME}' — esperando conexión...")

        # Arrancar el watchdog de inactividad
        self._watchdog_task = asyncio.create_task(self._watchdog_loop())

        try:
            await self._stop_event.wait()
        except (KeyboardInterrupt, asyncio.CancelledError):
            pass
        finally:
            if self._watchdog_task:
                self._watchdog_task.cancel()
                try:
                    await self._watchdog_task
                except asyncio.CancelledError:
                    pass
            await self._server.stop()
            self._handler.stop_monitor()
            print("[BLE] Servidor detenido.")

    def stop(self) -> None:
        """Parar el servidor desde cualquier hilo."""
        if self._stop_event and self._loop:
            self._loop.call_soon_threadsafe(self._stop_event.set)

    # ── Callbacks GATT ────────────────────────────────────────────────

    def _on_read(self, characteristic: BlessGATTCharacteristic, **_) -> bytearray:
        return characteristic.value or bytearray()

    def _on_write(self, characteristic: BlessGATTCharacteristic, value: bytearray, **_) -> None:
        """Llamado desde el event loop cuando la app escribe en RX."""
        if characteristic.uuid.upper() != _NUS_RX.upper():
            return

        # Actualizar la marca de actividad del cliente
        self._last_rx_time = time.time()
        if not self._client_connected:
            self._client_connected = True
            logger.info("[Watchdog] Cliente conectado")

        chunk = bytes(value).decode("utf-8", errors="replace")
        self._recv_buf += chunk

        while "\n" in self._recv_buf:
            line, self._recv_buf = self._recv_buf.split("\n", 1)
            line = line.strip()
            if not line:
                continue
            try:
                cmd = json.loads(line)
            except json.JSONDecodeError as exc:
                self._notify_from_loop({"status": "error", "message": f"JSON inválido: {exc}"})
                continue
            # handle() es bloqueante (acceso CAN) → ejecutar en executor
            assert self._loop is not None
            asyncio.ensure_future(self._dispatch_async(cmd), loop=self._loop)

    # ── Watchdog de inactividad ───────────────────────────────────────

    async def _watchdog_loop(self) -> None:
        """Monitorea inactividad del cliente cada 5 segundos."""
        try:
            while True:
                await asyncio.sleep(_WATCHDOG_INTERVAL)
                if self._client_connected:
                    elapsed = time.time() - self._last_rx_time
                    if elapsed > _CLIENT_TIMEOUT_S:
                        logger.warning(
                            f"[Watchdog] Sin actividad por {elapsed:.1f}s — "
                            f"desconectando cliente"
                        )
                        await self._handle_disconnect()
        except asyncio.CancelledError:
            pass

    async def _handle_disconnect(self) -> None:
        """Maneja desconexión por timeout: limpia y notifica handler."""
        self._client_connected = False
        self._recv_buf = ""
        self._handler.on_disconnect()

    # ── Despacho y notificación ────────────────────────────────────────

    async def _dispatch_async(self, cmd: dict) -> None:
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, self._handler.handle, cmd)
        self._notify_from_loop(response)

    def notify(self, data: dict) -> None:
        """Notificar datos al cliente BLE. Puede llamarse desde cualquier hilo."""
        if self._server is None or self._loop is None:
            return
        payload = (json.dumps(data) + "\n").encode()
        chunks = [payload[i:i + _MTU] for i in range(0, len(payload), _MTU)]
        self._loop.call_soon_threadsafe(self._send_chunks, chunks)

    def _notify_from_loop(self, data: dict) -> None:
        """Notificar desde dentro del event loop."""
        payload = (json.dumps(data) + "\n").encode()
        chunks = [payload[i:i + _MTU] for i in range(0, len(payload), _MTU)]
        self._send_chunks(chunks)

    def _send_chunks(self, chunks: list[bytes]) -> None:
        assert self._server is not None
        for chunk in chunks:
            char = self._server.get_characteristic(_NUS_TX)
            if char is None:
                break
            char.value = bytearray(chunk)
            self._server.update_value(_NUS_SERVICE, _NUS_TX)


# Alias para compatibilidad con server.py
BluetoothDiagServer = BLEDiagServer
