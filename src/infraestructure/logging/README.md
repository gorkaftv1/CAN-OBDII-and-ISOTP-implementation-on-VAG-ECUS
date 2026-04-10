# Logging — SQLite persistence layer

Persiste todas las muestras del monitor live y los comandos diagnósticos en una base de datos SQLite local (`diagnostics.db`).

## Arquitectura

```
IDataLogger (core/interfaces)
    └── SqliteDataLogger (infraestructure/logging)

ITransport
    └── LoggingTransport (decorator)  ← captura last_sent / last_received

IDiagnosticSession
    └── LoggedDiagnosticSession (decorator) ← llama a logger.log_command()
```

## Base de datos

Tres tablas en `diagnostics.db`:

| Tabla | Contenido |
|-------|-----------|
| `sessions` | Sesiones de diagnóstico con timestamps |
| `samples` | Muestras del monitor (pid, value, unit, timestamp) |
| `commands` | Comandos ejecutados (request/response en hex) |

- **WAL mode** para lecturas y escrituras concurrentes sin bloqueos.
- Buffer de 50 muestras antes de flush (reduce escrituras a disco).
- Thread-safe mediante `threading.Lock`.

## Uso rápido

```python
from infraestructure.logging.sqlite_logger import SqliteDataLogger
from infraestructure.transport.logging_transport import LoggingTransport
from session.logged_diagnostic_session import LoggedDiagnosticSession

logger = SqliteDataLogger("diagnostics.db")
session_id = logger.start_session("test")

log_transport = LoggingTransport(raw_transport)
inner = DiagnosticSession(log_transport, builder, decoder)
session = LoggedDiagnosticSession(inner, logger, session_id, log_transport)

with session:
    rpm = session.get_engine_rpm()   # se logea automáticamente

logger.end_session(session_id)
logger.close()
```

## Consultar datos

```bash
sqlite3 diagnostics.db "SELECT * FROM samples ORDER BY id DESC LIMIT 20;"
sqlite3 diagnostics.db "SELECT * FROM sessions;"
```
