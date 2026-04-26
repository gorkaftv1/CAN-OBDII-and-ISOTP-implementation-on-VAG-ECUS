"""Dispatch de comandos JSON para el servidor Bluetooth.

Cada comando que llega por RFCOMM pasa por BtCommandHandler.handle(),
que ejecuta la operación diagnóstica correspondiente y devuelve un dict
listo para serializar como JSON.
"""

from __future__ import annotations

import threading

from config.obd_pids import PIDS
from core.interfaces.i_data_logger import IDataLogger
from core.interfaces.i_diagnostic_session import IDiagnosticSession
from core.interfaces.i_transport import ITransport
from core.models.monitor_sample import MonitorSample
from infraestructure.decoder.obd2_decoder import Obd2DataDecoder
from monitor.live_data_monitor import LiveDataMonitor


class BtCommandHandler:
    """
    Traduce comandos JSON a operaciones diagnósticas.

    Comandos soportados:
        auth              — Autenticación con PIN (obligatorio si se configuró auth_token)
        snapshot          — Lee 18 PIDs de golpe
        dtcs              — Lee DTCs almacenados
        clear_dtcs        — Borra DTCs
        vin               — Lee VIN
        monitor_start     — Arranca LiveDataMonitor, pushea samples por BT
        monitor_stop      — Para el monitor
        sessions          — Lista sesiones históricas
        session_samples   — Muestras de una sesión (filtrable por pid)
        session_commands  — Comandos registrados en una sesión
    """

    def __init__(
        self,
        session: IDiagnosticSession,
        logger: IDataLogger,
        session_id: int,
        transport: ITransport,
        transport_lock: threading.Lock,
        push_callback=None,   # Callable[[dict], None] — envía JSON al cliente BT
        auth_token: str | None = None,
    ) -> None:
        self._session = session
        self._logger = logger
        self._session_id = session_id
        self._transport = transport
        self._lock = transport_lock
        self._push = push_callback or (lambda _: None)

        # Auth: si auth_token es None la sesión BLE no requiere autenticación.
        self._auth_token = auth_token
        self._authenticated = auth_token is None

        self._monitor: LiveDataMonitor | None = None
        self._monitor_lock = threading.Lock()

    def set_push_callback(self, cb) -> None:
        """Inyectar el callback de notificación BLE tras construir el servidor."""
        self._push = cb

    # ── Dispatch ───────────────────────────────────────────────────────

    def handle(self, cmd: dict) -> dict:
        name = cmd.get("cmd", "")

        if not self._authenticated:
            if name != "auth":
                return {"status": "error", "message": "not authenticated — send {\"cmd\":\"auth\",\"token\":\"<PIN>\"}"}
            provided = cmd.get("token", "")
            if provided == self._auth_token:
                self._authenticated = True
                return {"status": "ok", "data": "authenticated"}
            return {"status": "error", "message": "invalid token"}

        dispatch = {
            "snapshot":        self._snapshot,
            "dtcs":            self._dtcs,
            "clear_dtcs":      self._clear_dtcs,
            "vin":             self._vin,
            "monitor_start":   self._monitor_start,
            "monitor_stop":    self._monitor_stop,
            "sessions":        self._sessions,
            "session_samples": self._session_samples,
            "session_commands": self._session_commands,
        }
        fn = dispatch.get(name)
        if fn is None:
            return {"status": "error", "message": f"Unknown command: {name!r}"}
        try:
            return fn(cmd)
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    # ── Handlers ───────────────────────────────────────────────────────

    def _snapshot(self, _cmd: dict) -> dict:
        data = {}
        with self._lock:
            for pid_def in PIDS.values():
                self._transport.send(pid_def.request)
                raw = self._transport.receive()
                value = pid_def.decode(raw)
                data[pid_def.name] = {"value": value, "unit": pid_def.unit}
        return {"status": "ok", "data": data}

    def _dtcs(self, _cmd: dict) -> dict:
        with self._lock:
            dtcs = self._session.get_dtcs()
        return {
            "status": "ok",
            "data": [{"code": d.code, "description": d.description} for d in dtcs],
        }

    def _clear_dtcs(self, _cmd: dict) -> dict:
        with self._lock:
            self._session.clear_dtcs()
        return {"status": "ok", "data": None}

    def _vin(self, _cmd: dict) -> dict:
        with self._lock:
            vin = self._session.get_vin()
        return {"status": "ok", "data": vin}

    def _monitor_start(self, cmd: dict) -> dict:
        pids = frozenset(cmd.get("pids", [0x05, 0x04, 0x0C, 0x0D, 0x11]))
        interval_ms = int(cmd.get("interval_ms", 500))

        with self._monitor_lock:
            if self._monitor is not None and self._monitor.is_running():
                return {"status": "ok", "data": "monitor already running"}

            def on_sample(s: MonitorSample) -> None:
                self._logger.log_sample(self._session_id, s)
                self._push({
                    "type":  "sample",
                    "pid":   s.pid,
                    "name":  s.name,
                    "value": s.value,
                    "unit":  s.unit,
                    "ts":    s.timestamp,
                })

            def on_error(pid: int, exc: Exception) -> None:
                self._push({"type": "error", "pid": pid, "message": str(exc)})

            self._monitor = LiveDataMonitor(
                transport=self._transport,
                decoder=Obd2DataDecoder(),
                pid_ids=pids,
                interval_ms=interval_ms,
                on_sample=on_sample,
                on_error=on_error,
                lock=self._lock,
            )
            self._monitor.start()

        return {"status": "ok", "data": "monitor started"}

    def _monitor_stop(self, _cmd: dict) -> dict:
        with self._monitor_lock:
            if self._monitor is not None:
                self._monitor.stop()
                self._monitor = None
        return {"status": "ok", "data": "monitor stopped"}

    def _sessions(self, cmd: dict) -> dict:
        limit = int(cmd.get("limit", 50))
        sessions = self._logger.get_sessions(limit=limit)
        return {
            "status": "ok",
            "data": [
                {
                    "session_id":   s.session_id,
                    "label":        s.label,
                    "started_at":   s.started_at,
                    "ended_at":     s.ended_at,
                    "sample_count": s.sample_count,
                }
                for s in sessions
            ],
        }

    def _session_samples(self, cmd: dict) -> dict:
        sid = int(cmd.get("session_id", 0))
        pid = cmd.get("pid")
        limit = int(cmd.get("limit", 1000))
        samples = self._logger.get_samples(
            session_id=sid,
            pid=int(pid) if pid is not None else None,
            limit=limit,
        )
        return {
            "status": "ok",
            "data": [
                {
                    "pid":   s.pid,
                    "name":  s.name,
                    "value": s.value,
                    "unit":  s.unit,
                    "ts":    s.timestamp,
                }
                for s in samples
            ],
        }

    def _session_commands(self, cmd: dict) -> dict:
        sid = int(cmd.get("session_id", 0))
        commands = self._logger.get_commands(session_id=sid)
        return {
            "status": "ok",
            "data": [
                {
                    "command":      c.command,
                    "request_hex":  c.request_hex,
                    "response_hex": c.response_hex,
                    "timestamp":    c.timestamp,
                }
                for c in commands
            ],
        }

    def stop_monitor(self) -> None:
        """Parar el monitor si está activo. Llamar al desconectar el cliente."""
        with self._monitor_lock:
            if self._monitor is not None:
                self._monitor.stop()
                self._monitor = None
