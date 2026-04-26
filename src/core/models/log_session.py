from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LogSession:
    session_id: int
    label: str
    started_at: str       # ISO 8601 wall-clock timestamp
    ended_at: str | None  # None si la sesión sigue abierta
    sample_count: int
