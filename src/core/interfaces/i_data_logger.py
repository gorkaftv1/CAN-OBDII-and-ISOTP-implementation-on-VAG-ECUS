from __future__ import annotations

from abc import ABC, abstractmethod

from core.models.monitor_sample import MonitorSample
from core.models.log_session import LogSession
from core.models.command_log import CommandLog


class IDataLogger(ABC):
    """Persiste muestras del monitor y comandos diagnósticos en almacenamiento local."""

    @abstractmethod
    def start_session(self, label: str = "") -> int:
        """Abre una nueva sesión de diagnóstico. Devuelve session_id."""

    @abstractmethod
    def end_session(self, session_id: int) -> None:
        """Cierra la sesión indicada registrando la hora de fin."""

    @abstractmethod
    def log_sample(self, session_id: int, sample: MonitorSample) -> None:
        """Registra una muestra de un PID del monitor live."""

    @abstractmethod
    def log_command(
        self,
        session_id: int,
        command: str,
        request: bytes,
        response: bytes,
    ) -> None:
        """Registra un comando diagnóstico con sus bytes de request/response."""

    @abstractmethod
    def get_sessions(self, limit: int = 50) -> list[LogSession]:
        """Devuelve las últimas `limit` sesiones, ordenadas de más nueva a más antigua."""

    @abstractmethod
    def get_samples(
        self,
        session_id: int,
        pid: int | None = None,
        limit: int = 1000,
    ) -> list[MonitorSample]:
        """Devuelve muestras de una sesión, opcionalmente filtradas por PID."""

    @abstractmethod
    def get_commands(self, session_id: int) -> list[CommandLog]:
        """Devuelve todos los comandos registrados en una sesión."""
