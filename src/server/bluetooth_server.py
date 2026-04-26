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

# ── Configuración de estabilidad BLE ────────────────────────────────────────
_BLE_NAME              = "SEAT_DIAG"
_MTU                   = 240   # BLE estándar seguro (no 512, es demasiado)
_CLIENT_TIMEOUT_S      = 15.0  # segundos sin actividad → desconexión
_SERVER_TIMEOUT_S      = 20.0  # watchdog servidor: sin notificaciones exitosas
_WATCHDOG_INTERVAL     = 5.0   # con qué frecuencia comprueba el watchdog
_HEARTBEAT_INTERVAL    = 8.0   # enviar heartbeat cada 8s si no hay actividad
_RECV_BUFFER_MAX_SIZE  = 4096  # máximo tamaño del buffer para evitar memory leaks
_MAX_RECONNECT_RETRIES = 5     # reintentos de reconexión del servidor


class BLEDiagServer:
    """
    Servidor BLE GATT robusto basado en asyncio.

    Características:
    - Reconexión automática con exponential backoff
    - Watchdog bidireccional (cliente + servidor)
    - Heartbeat automático para keep-alive
    - Buffer con límite de seguridad
    - Logging detallado para debugging

    Uso::

        server = BLEDiagServer(handler)
        asyncio.run(server.start())   # blocking hasta Ctrl+C o fallo
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
        self._last_tx_time: float = 0.0
        self._client_connected: bool = False
        self._server_running: bool = False
        self._watchdog_task: asyncio.Task | None = None
        self._heartbeat_task: asyncio.Task | None = None
        self._reconnect_count: int = 0

    # ── Ciclo de vida con reconexión automática ─────────────────────────

    async def start(self) -> None:
        """Arrancar el servidor BLE. Reconecta automáticamente si falla."""
        self._loop = asyncio.get_event_loop()
        self._stop_event = asyncio.Event()

        try:
            while self._reconnect_count < _MAX_RECONNECT_RETRIES:
                try:
                    await self._start_server()
                    self._reconnect_count = 0  # Reset contador en éxito
                    await self._stop_event.wait()
                    break
                except Exception as exc:
                    self._reconnect_count += 1
                    if self._reconnect_count >= _MAX_RECONNECT_RETRIES:
                        logger.error(
                            f"[BLE] Máximo de reintentos alcanzado ({_MAX_RECONNECT_RETRIES}). "
                            "Servidor detenido."
                        )
                        raise
                    wait_time = min(2 ** self._reconnect_count, 30)  # backoff: 2, 4, 8, 16, 30s
                    logger.error(
                        f"[BLE] Error en servidor (intento {self._reconnect_count}/{_MAX_RECONNECT_RETRIES}): {exc}. "
                        f"Reintentando en {wait_time}s..."
                    )
                    await asyncio.sleep(wait_time)
        finally:
            await self._shutdown()

    async def _start_server(self) -> None:
        """Inicializa y arranca el servidor BLE."""
        self._last_rx_time = time.time()
        self._last_tx_time = time.time()

        assert self._loop is not None
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
        self._server_running = True
        logger.info(f"[BLE] Anunciando '{_BLE_NAME}' — esperando conexión...")
        print(f"[BLE] Anunciando '{_BLE_NAME}' — esperando conexión...")

        # Arrancar watchdog y heartbeat
        self._watchdog_task = asyncio.create_task(self._watchdog_loop())
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    async def _shutdown(self) -> None:
        """Detiene tareas y limpia recursos."""
        self._server_running = False

        # Cancelar tareas
        for task in [self._watchdog_task, self._heartbeat_task]:
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        # Detener servidor
        if self._server:
            try:
                await self._server.stop()
            except Exception as e:
                logger.error(f"[BLE] Error al detener servidor: {e}")

        self._handler.stop_monitor()
        logger.info("[BLE] Servidor detenido.")
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

        # Buffer con límite de seguridad
        if len(self._recv_buf) + len(chunk) > _RECV_BUFFER_MAX_SIZE:
            logger.warning(
                f"[BLE] Buffer de recepción excede límite ({_RECV_BUFFER_MAX_SIZE} bytes). "
                "Posible cliente maligno o corrupción de datos. Limpiando buffer."
            )
            self._recv_buf = ""
            self._notify_from_loop({
                "status": "error",
                "message": "Buffer overflow — conexión reseteada"
            })
            return

        self._recv_buf += chunk

        while "\n" in self._recv_buf:
            line, self._recv_buf = self._recv_buf.split("\n", 1)
            line = line.strip()
            if not line:
                continue
            try:
                cmd = json.loads(line)
            except json.JSONDecodeError as exc:
                logger.warning(f"[BLE] JSON inválido: {exc}")
                self._notify_from_loop({"status": "error", "message": f"JSON inválido: {exc}"})
                continue
            # handle() es bloqueante (acceso CAN) → ejecutar en executor
            assert self._loop is not None
            asyncio.ensure_future(self._dispatch_async(cmd), loop=self._loop)

    # ── Watchdog bidireccional (cliente + servidor) ─────────────────────

    async def _watchdog_loop(self) -> None:
        """Monitorea inactividad del cliente Y del servidor cada 5 segundos."""
        try:
            while True:
                await asyncio.sleep(_WATCHDOG_INTERVAL)

                now = time.time()

                # Monitoreo del servidor: ¿sigue enviando notificaciones? 
                # (SOLO si hay cliente conectado - de lo contrario puede estar inactivo)
                if self._server_running and self._client_connected:
                    elapsed_tx = now - self._last_tx_time
                    if elapsed_tx > _SERVER_TIMEOUT_S:
                        logger.error(
                            f"[Watchdog] Servidor sin enviar notificaciones en {elapsed_tx:.1f}s. "
                            "Posible fallo interno."
                        )
                        raise RuntimeError(
                            f"Servidor BLE sin actividad TX por {elapsed_tx:.1f}s"
                        )

                # Monitoreo del cliente: ¿sigue activo?
                if self._client_connected:
                    elapsed_rx = now - self._last_rx_time
                    if elapsed_rx > _CLIENT_TIMEOUT_S:
                        logger.warning(
                            f"[Watchdog] Cliente sin actividad RX por {elapsed_rx:.1f}s. "
                            "Desconectando."
                        )
                        await self._handle_disconnect()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"[Watchdog] Error: {e}")
            raise

    async def _heartbeat_loop(self) -> None:
        """Envía heartbeat cada 8s si no hay actividad."""
        try:
            while True:
                await asyncio.sleep(_HEARTBEAT_INTERVAL)
                if self._client_connected:
                    elapsed = time.time() - self._last_rx_time
                    # Si pasaron más de 8s sin recibir nada, enviar heartbeat
                    if elapsed > _HEARTBEAT_INTERVAL:
                        self._notify_from_loop({
                            "type": "heartbeat",
                            "timestamp": time.time()
                        })
                        logger.debug("[Heartbeat] Enviado")
        except asyncio.CancelledError:
            pass

    async def _handle_disconnect(self) -> None:
        """Maneja desconexión por timeout: limpia y notifica handler."""
        self._client_connected = False
        self._recv_buf = ""
        self._handler.on_disconnect()
        logger.info("[Watchdog] Cliente desconectado y estado reseteado")

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
        self._last_tx_time = time.time()  # Actualizar marca de envío

    def _send_chunks(self, chunks: list[bytes]) -> None:
        assert self._server is not None
        try:
            for chunk in chunks:
                char = self._server.get_characteristic(_NUS_TX)
                if char is None:
                    logger.warning("[BLE] Característica TX no disponible")
                    break
                char.value = bytearray(chunk)
                self._server.update_value(_NUS_SERVICE, _NUS_TX)
        except Exception as e:
            logger.error(f"[BLE] Error enviando notificación: {e}")
            raise


# Alias para compatibilidad con server.py
BluetoothDiagServer = BLEDiagServer
