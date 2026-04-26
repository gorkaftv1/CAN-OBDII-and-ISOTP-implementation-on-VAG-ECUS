import threading

from core.interfaces.i_transport import ITransport


class LoggingTransport(ITransport):
    """
    Decorator sobre cualquier ITransport que almacena los últimos bytes
    enviados y recibidos para que LoggedDiagnosticSession pueda registrarlos.

    Thread-safe: cada hilo tiene su propio par last_sent/last_received via
    threading.local, evitando que el hilo del LiveDataMonitor sobreescriba
    los bytes que el hilo principal acaba de enviar/recibir.

    Uso:
        raw = IsoTpTransport(...)
        wrapped = LoggingTransport(raw)
        session = DiagnosticSession(wrapped, builder, decoder)
        # Después de cada operación (desde el mismo hilo):
        req = wrapped.last_sent    # bytes del último send() de este hilo
        res = wrapped.last_received  # bytes del último receive() de este hilo
    """

    def __init__(self, inner: ITransport) -> None:
        self._inner = inner
        self._local = threading.local()

    @property
    def last_sent(self) -> bytes:
        return getattr(self._local, "last_sent", b"")

    @property
    def last_received(self) -> bytes:
        return getattr(self._local, "last_received", b"")

    # ── ITransport ─────────────────────────────────────────────────────

    def connect(self) -> None:
        self._inner.connect()

    def disconnect(self) -> None:
        self._inner.disconnect()

    def send(self, payload: bytes) -> None:
        self._local.last_sent = payload
        self._inner.send(payload)

    def receive(self) -> bytes:
        data = self._inner.receive()
        self._local.last_received = data
        return data

    # ── Context manager ────────────────────────────────────────────────

    def __enter__(self) -> "LoggingTransport":
        self._inner.__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self._inner.__exit__(exc_type, exc_val, exc_tb)
