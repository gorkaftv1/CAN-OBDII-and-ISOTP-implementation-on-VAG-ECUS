"""Servidor Bluetooth SPP (Serial Port Profile) para la Raspberry Pi.

Expone el bus CAN/OBD-II al móvil a través de Bluetooth Classic RFCOMM.
El protocolo de aplicación es NDJSON (un objeto JSON por línea).

Prerequisitos en la Raspberry Pi (una sola vez):
    sudo apt install libbluetooth-dev bluez
    sudo systemctl enable bluetooth
    sudo hciconfig hci0 piscan
    sudo hciconfig hci0 name "SEAT_DIAG_PI"

Dependencias Python:
    pip install PyBluez2
"""

from __future__ import annotations

import json
import threading
import socket as _socket

try:
    import bluetooth  # type: ignore[import]
    _BT_AVAILABLE = True
except ImportError:
    _BT_AVAILABLE = False

from core.interfaces.i_data_logger import IDataLogger
from core.interfaces.i_diagnostic_session import IDiagnosticSession
from core.interfaces.i_transport import ITransport
from server.bt_command_handler import BtCommandHandler

# UUID estándar del Serial Port Profile (SPP)
_SPP_UUID = "00001101-0000-1000-8000-00805F9B34FB"
_BT_PORT = bluetooth.PORT_ANY if _BT_AVAILABLE else 1
_SERVICE_NAME = "SEAT_DIAG"
_RECV_BUFFER = 4096


class BluetoothDiagServer:
    """
    Servidor Bluetooth que acepta una conexión RFCOMM a la vez.

    Al conectar un cliente:
      - Crea un BtCommandHandler con la sesión diagnóstica y el logger.
      - Lee NDJSON del socket, despacha al handler, envía la respuesta.
      - Al desconectar el cliente, para el monitor si estaba activo
        y vuelve a escuchar conexiones.

    Uso::

        server = BluetoothDiagServer(session, logger, session_id, transport, lock)
        server.start()   # blocking hasta Ctrl+C
    """

    def __init__(
        self,
        session: IDiagnosticSession,
        logger: IDataLogger,
        session_id: int,
        transport: ITransport,
        transport_lock: threading.Lock,
    ) -> None:
        if not _BT_AVAILABLE:
            raise RuntimeError(
                "PyBluez2 no está instalado. Ejecuta: pip install PyBluez2"
            )
        self._session = session
        self._logger = logger
        self._session_id = session_id
        self._transport = transport
        self._lock = transport_lock
        self._running = False

    # ── Ciclo de vida ──────────────────────────────────────────────────

    def start(self) -> None:
        """Bloquea hasta que se recibe KeyboardInterrupt."""
        server_sock = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
        server_sock.bind(("", _BT_PORT))
        server_sock.listen(1)

        port = server_sock.getsockname()[1]
        bluetooth.advertise_service(
            server_sock,
            _SERVICE_NAME,
            service_id=_SPP_UUID,
            service_classes=[_SPP_UUID, bluetooth.SERIAL_PORT_CLASS],
            profiles=[bluetooth.SERIAL_PORT_PROFILE],
        )

        print(f"[BT] Escuchando en RFCOMM canal {port} — servicio '{_SERVICE_NAME}'")
        print("[BT] Esperando conexión Bluetooth...")

        self._running = True
        try:
            while self._running:
                try:
                    client_sock, client_info = server_sock.accept()
                except OSError:
                    break
                print(f"[BT] Conexión desde {client_info}")
                self._handle_client(client_sock)
                print(f"[BT] Cliente desconectado. Esperando nueva conexión...")
        except KeyboardInterrupt:
            print("\n[BT] Servidor detenido.")
        finally:
            server_sock.close()

    def stop(self) -> None:
        self._running = False

    # ── Manejo de cliente ──────────────────────────────────────────────

    def _handle_client(self, sock) -> None:
        """Loop de lectura/escritura para un cliente conectado."""
        recv_buf = ""

        def push(data: dict) -> None:
            try:
                sock.send((json.dumps(data) + "\n").encode())
            except OSError:
                pass

        handler = BtCommandHandler(
            session=self._session,
            logger=self._logger,
            session_id=self._session_id,
            transport=self._transport,
            transport_lock=self._lock,
            push_callback=push,
        )

        try:
            while True:
                chunk = sock.recv(_RECV_BUFFER)
                if not chunk:
                    break
                recv_buf += chunk.decode(errors="replace")

                # Procesar todas las líneas completas del buffer
                while "\n" in recv_buf:
                    line, recv_buf = recv_buf.split("\n", 1)
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        cmd = json.loads(line)
                    except json.JSONDecodeError as e:
                        push({"status": "error", "message": f"JSON inválido: {e}"})
                        continue

                    response = handler.handle(cmd)
                    push(response)

        except OSError:
            pass
        finally:
            handler.stop_monitor()
            sock.close()
