from __future__ import annotations

import sqlite3
import threading
from datetime import datetime, timezone

from core.interfaces.i_data_logger import IDataLogger
from core.models.monitor_sample import MonitorSample
from core.models.log_session import LogSession
from core.models.command_log import CommandLog


_SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS sessions (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    label      TEXT    NOT NULL DEFAULT '',
    started_at TEXT    NOT NULL,
    ended_at   TEXT
);

CREATE TABLE IF NOT EXISTS samples (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id   INTEGER NOT NULL REFERENCES sessions(id),
    pid          INTEGER NOT NULL,
    name         TEXT    NOT NULL,
    value        REAL    NOT NULL,
    unit         TEXT    NOT NULL,
    monotonic_ts REAL    NOT NULL,
    wall_ts      TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS commands (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id   INTEGER NOT NULL REFERENCES sessions(id),
    command      TEXT    NOT NULL,
    request_hex  TEXT    NOT NULL,
    response_hex TEXT    NOT NULL,
    wall_ts      TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_samples_session ON samples(session_id, pid);
CREATE INDEX IF NOT EXISTS idx_commands_session ON commands(session_id);
"""

_SAMPLE_BUFFER_SIZE = 50  # flush cada N muestras


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class SqliteDataLogger(IDataLogger):
    """
    Implementación SQLite del logger de diagnóstico.

    Thread-safe: el monitor de live-data escribe muestras desde su hilo
    de fondo; los handlers REST/BT leen desde otro hilo. WAL mode permite
    lecturas y escrituras concurrentes sin bloqueos excesivos.
    """

    def __init__(self, db_path: str = "diagnostics.db") -> None:
        self._db_path = db_path
        self._lock = threading.Lock()
        self._sample_buffer: list[tuple] = []

        # Conexión dedicada para escrituras (check_same_thread=False + lock externo)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    # ── Ciclo de vida de sesión ────────────────────────────────────────

    def start_session(self, label: str = "") -> int:
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO sessions (label, started_at) VALUES (?, ?)",
                (label, _now_iso()),
            )
            self._conn.commit()
            return cur.lastrowid  # type: ignore[return-value]

    def end_session(self, session_id: int) -> None:
        with self._lock:
            self._flush_buffer()
            self._conn.execute(
                "UPDATE sessions SET ended_at = ? WHERE id = ?",
                (_now_iso(), session_id),
            )
            self._conn.commit()

    # ── Escritura ──────────────────────────────────────────────────────

    def log_sample(self, session_id: int, sample: MonitorSample) -> None:
        row = (
            session_id,
            sample.pid,
            sample.name,
            sample.value,
            sample.unit,
            sample.timestamp,
            _now_iso(),
        )
        with self._lock:
            self._sample_buffer.append(row)
            if len(self._sample_buffer) >= _SAMPLE_BUFFER_SIZE:
                self._flush_buffer()

    def log_command(
        self,
        session_id: int,
        command: str,
        request: bytes,
        response: bytes,
    ) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO commands (session_id, command, request_hex, response_hex, wall_ts)"
                " VALUES (?, ?, ?, ?, ?)",
                (
                    session_id,
                    command,
                    request.hex(),
                    response.hex(),
                    _now_iso(),
                ),
            )
            self._conn.commit()

    # ── Lectura ────────────────────────────────────────────────────────

    def get_sessions(self, limit: int = 50) -> list[LogSession]:
        cur = self._conn.execute(
            """
            SELECT s.id, s.label, s.started_at, s.ended_at,
                   COUNT(sa.id) AS sample_count
            FROM sessions s
            LEFT JOIN samples sa ON sa.session_id = s.id
            GROUP BY s.id
            ORDER BY s.id DESC
            LIMIT ?
            """,
            (limit,),
        )
        return [
            LogSession(
                session_id=row[0],
                label=row[1],
                started_at=row[2],
                ended_at=row[3],
                sample_count=row[4],
            )
            for row in cur.fetchall()
        ]

    def get_samples(
        self,
        session_id: int,
        pid: int | None = None,
        limit: int = 1000,
    ) -> list[MonitorSample]:
        if pid is None:
            cur = self._conn.execute(
                "SELECT pid, name, value, unit, monotonic_ts"
                " FROM samples WHERE session_id = ?"
                " ORDER BY monotonic_ts LIMIT ?",
                (session_id, limit),
            )
        else:
            cur = self._conn.execute(
                "SELECT pid, name, value, unit, monotonic_ts"
                " FROM samples WHERE session_id = ? AND pid = ?"
                " ORDER BY monotonic_ts LIMIT ?",
                (session_id, pid, limit),
            )
        return [
            MonitorSample(
                pid=row[0],
                name=row[1],
                value=row[2],
                unit=row[3],
                timestamp=row[4],
            )
            for row in cur.fetchall()
        ]

    def get_commands(self, session_id: int) -> list[CommandLog]:
        cur = self._conn.execute(
            "SELECT command, request_hex, response_hex, wall_ts"
            " FROM commands WHERE session_id = ? ORDER BY id",
            (session_id,),
        )
        return [
            CommandLog(
                command=row[0],
                request_hex=row[1],
                response_hex=row[2],
                timestamp=row[3],
            )
            for row in cur.fetchall()
        ]

    # ── Privado ────────────────────────────────────────────────────────

    def _flush_buffer(self) -> None:
        """Persiste el buffer acumulado. Debe llamarse bajo self._lock."""
        if not self._sample_buffer:
            return
        self._conn.executemany(
            "INSERT INTO samples"
            " (session_id, pid, name, value, unit, monotonic_ts, wall_ts)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            self._sample_buffer,
        )
        self._conn.commit()
        self._sample_buffer.clear()

    def close(self) -> None:
        """Flush pendiente y cierra la conexión."""
        with self._lock:
            self._flush_buffer()
        self._conn.close()

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass
