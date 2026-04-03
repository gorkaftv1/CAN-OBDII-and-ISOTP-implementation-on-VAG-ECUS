from core.interfaces.i_transport import ITransport


class LoggingTransport(ITransport):
    """
    Decorator sobre cualquier ITransport que almacena los últimos bytes
    enviados y recibidos para que LoggedDiagnosticSession pueda registrarlos.

    Uso:
        raw = IsoTpTransport(...)
        wrapped = LoggingTransport(raw)
        session = DiagnosticSession(wrapped, builder, decoder)
        # Después de cada operación:
        req = wrapped.last_sent    # bytes del último send()
        res = wrapped.last_received  # bytes del último receive()
    """

    def __init__(self, inner: ITransport) -> None:
        self._inner = inner
        self.last_sent: bytes = b""
        self.last_received: bytes = b""

    # ── ITransport ─────────────────────────────────────────────────────

    def connect(self) -> None:
        self._inner.connect()

    def disconnect(self) -> None:
        self._inner.disconnect()

    def send(self, payload: bytes) -> None:
        self.last_sent = payload
        self._inner.send(payload)

    def receive(self) -> bytes:
        data = self._inner.receive()
        self.last_received = data
        return data

    # ── Context manager ────────────────────────────────────────────────

    def __enter__(self) -> "LoggingTransport":
        self._inner.__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self._inner.__exit__(exc_type, exc_val, exc_tb)
