# Python OBD-II Scanner

Clean-architecture Python tool that queries an ECU (real or simulated) via ISO-TP over CAN bus and presents live diagnostic data interactively.

## Installation

```bash
pip install -r ../Requirements.txt
```

| Package | Version | Purpose |
|---------|---------|---------|
| python-can | 4.4.2 | SocketCAN bus abstraction |
| can-isotp | 2.0.3 | ISO 15765-2 framing |
| pytest | 8.3.5 | Test runner |
| pytest-cov | 6.0.0 | Coverage reporting |

`python-can` and `can-isotp` require Linux + SocketCAN. `MockTransport` works on any OS without them.

On Raspberry Pi, bring up the CAN interface before running:

```bash
sudo ip link set can0 type can bitrate 500000
sudo ip link set can0 up
```

## Running

```bash
python src/scripts/cli.py
```

| Menu option | Action |
|-------------|--------|
| `1` | Live data: RPM, coolant temp, speed, throttle, engine load |
| `2` | Extended live data: all 18 Mode 0x01 PIDs |
| `3` | Read stored DTCs |
| `4` | Clear DTCs |
| `5` | Read VIN |
| `0` | Exit |

## Testing Without Hardware

In `src/scripts/cli.py`, replace `IsoTpTransport` with `MockTransport`:

```python
from infraestructure.transport.mock_transport import MockTransport
transport = MockTransport()
```

`MockTransport` ships with Arduino ECU simulator default responses (idle: RPM=850, Speed=0, Coolant=56 °C). Use `mock.inject_response(request_bytes, response_bytes)` to override any PID.

```bash
pytest src/test/unit/ -v --cov=src
pytest src/test/integration/ -v --cov=src
pytest src/test/unit/test_foo.py -v      # single file
```

## Architecture

```
scripts/cli.py
    └── session/diagnostic_session.py          (DiagnosticSession)
            ├── ITransport        → IsoTpTransport / MockTransport
            ├── IProtocolBuilder  → Obd2ProtocolBuilder
            └── IDataDecoder      → Obd2DataDecoder
```

| Layer | Location | Responsibility |
|-------|----------|---------------|
| Domain | `core/` | Abstract interfaces, immutable models (`Dtc`, `ObdResponse`), exceptions |
| Infrastructure | `infraestructure/` | Concrete transport, decoder, builder — swap without touching business logic |
| Configuration | `config/obd_pids.py` | **Single source of truth** for all OBD-II byte values and SAE J1979 decode formulas |
| Application | `session/` | `DiagnosticSession` — build → send → receive → validate → decode |

Every diagnostic call follows the same fixed pipeline. All OBD-II byte literals live in `config/obd_pids.py` — never hardcode them in transport or session code. Always use `with session:` to guarantee CAN socket cleanup.
