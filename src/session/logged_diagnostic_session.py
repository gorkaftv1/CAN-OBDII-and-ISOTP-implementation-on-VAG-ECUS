from __future__ import annotations

from types import TracebackType

from core.interfaces.i_diagnostic_session import IDiagnosticSession
from core.interfaces.i_data_logger import IDataLogger
from core.interfaces.i_transport import ITransport
from core.interfaces.i_protocol_builder import IProtocolBuilder
from core.interfaces.i_data_decoder import IDataDecoder
from core.models.dtc import Dtc
from infraestructure.transport.logging_transport import LoggingTransport


class LoggedDiagnosticSession(IDiagnosticSession):
    """
    Decorator de IDiagnosticSession que registra cada comando en IDataLogger.

    Wrappea una sesión existente; delega cada operación a `inner` y luego
    llama a `logger.log_command()` con los bytes exactos de request/response
    leídos del LoggingTransport subyacente.

    Requiere que el transport inyectado sea un LoggingTransport (o al menos
    que exponga `last_sent` / `last_received`).

    Uso::

        transport = LoggingTransport(IsoTpTransport(...))
        inner = DiagnosticSession(transport, builder, decoder)
        session = LoggedDiagnosticSession(inner, logger, session_id, transport)
        with session:
            rpm = session.get_engine_rpm()
    """

    def __init__(
        self,
        inner: IDiagnosticSession,
        logger: IDataLogger,
        session_id: int,
        transport: LoggingTransport,
    ) -> None:
        # No llamamos a super().__init__() porque IDiagnosticSession es un ABC
        # cuyo __init__ no realiza nada concreto; el estado lo gestiona 'inner'.
        self._inner = inner
        self._logger = logger
        self._session_id = session_id
        self._transport = transport

    # ── Ciclo de vida ──────────────────────────────────────────────────

    def open(self) -> None:
        self._inner.open()

    def close(self) -> None:
        self._inner.close()

    def __enter__(self) -> "LoggedDiagnosticSession":
        self._inner.__enter__()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool | None:
        return self._inner.__exit__(exc_type, exc_val, exc_tb)

    # ── Helper ─────────────────────────────────────────────────────────

    def _log(self, command: str) -> None:
        self._logger.log_command(
            self._session_id,
            command,
            self._transport.last_sent,
            self._transport.last_received,
        )

    # ── Mode 0x01 ──────────────────────────────────────────────────────

    def get_engine_rpm(self) -> float:
        result = self._inner.get_engine_rpm()
        self._log("get_engine_rpm")
        return result

    def get_coolant_temp(self) -> float:
        result = self._inner.get_coolant_temp()
        self._log("get_coolant_temp")
        return result

    def get_vehicle_speed(self) -> float:
        result = self._inner.get_vehicle_speed()
        self._log("get_vehicle_speed")
        return result

    def get_throttle_position(self) -> float:
        result = self._inner.get_throttle_position()
        self._log("get_throttle_position")
        return result

    def get_engine_load(self) -> float:
        result = self._inner.get_engine_load()
        self._log("get_engine_load")
        return result

    # ── Mode 0x03 / 0x04 ──────────────────────────────────────────────

    def get_dtcs(self) -> list[Dtc]:
        result = self._inner.get_dtcs()
        self._log("get_dtcs")
        return result

    def clear_dtcs(self) -> None:
        self._inner.clear_dtcs()
        self._log("clear_dtcs")

    # ── Mode 0x09 ──────────────────────────────────────────────────────

    def get_vin(self) -> str:
        result = self._inner.get_vin()
        self._log("get_vin")
        return result
