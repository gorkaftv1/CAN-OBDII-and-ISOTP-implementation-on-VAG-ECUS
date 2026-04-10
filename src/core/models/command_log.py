from dataclasses import dataclass


@dataclass(frozen=True)
class CommandLog:
    command: str       # "get_dtcs", "clear_dtcs", "get_vin", etc.
    request_hex: str   # bytes de request en hex, ej. "0103"
    response_hex: str  # bytes de respuesta en hex
    timestamp: str     # ISO 8601 wall-clock
