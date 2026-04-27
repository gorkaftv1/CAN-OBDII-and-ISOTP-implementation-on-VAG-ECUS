# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Python-based automotive diagnostic tool for a SEAT Ibiza 6J (2012) with 1.4 MPI BXW engine (petrol, naturally aspirated). Communicates with vehicle ECUs via CAN bus using OBD-II (SAE J1979) and ISO-TP (ISO 15765-2) protocols. University final project (TFT) at ULPGC.

## Commands

```bash
# Install dependencies
pip install -r Requirements.txt

# Run the interactive CLI (uses MockTransport by default in demo mode)
python src/scripts/cli.py

# Run tests
pytest src/test/unit/ -v --cov=src
pytest src/test/integration/ -v --cov=src

# Run a single test file
pytest src/test/unit/test_foo.py -v
```

## Architecture

Clean architecture with four layers:

### Layer Structure

- **`src/core/`** — Domain layer. Abstract interfaces and value objects. No framework dependencies.
  - `interfaces/` — `ITransport`, `IProtocolBuilder`, `IDataDecoder`, `IDiagnosticSession`
  - `models/` — Immutable frozen dataclasses: `DTC`, `ObdResponse`
  - `exceptions.py` — `NrcException`, `TransportError`, `DiagnosticTimeoutError`, `InvalidResponseError`

- **`src/infraestructure/`** — Infrastructure layer. Concrete implementations of domain interfaces.
  - `transport/isotp_transport.py` — Real CAN hardware via `python-can` + `can-isotp` on `can0`
  - `transport/mock_transport.py` — In-memory mock with Arduino ECU simulator responses (for testing)
  - `protocol/obd2_builder.py` — Builds OBD-II request byte sequences (delegates to PID registry)
  - `decoder/obd2_decoder.py` — Validates ECU responses and applies SAE J1979 decode formulas

- **`src/config/`** — Configuration layer.
  - `can_config.py` — CAN constants: `CAN_TX_ID=0x7E0`, `CAN_RX_ID=0x7E8`, `CAN_BITRATE=500_000`, `ISOTP_PADDING_BYTE=0xAA`
  - `obd_pids.py` — Registry of 18 supported Mode 0x01 PIDs with decode lambdas (single source of truth for all OBD-II byte values)

- **`src/session/diagnostic_session.py`** — Application layer. `DiagnosticSession` orchestrates the three collaborators.

- **`src/scripts/cli.py`** — Interactive menu: live data, extended data, DTCs, clear DTCs, VIN.

### Key Design Decisions

- **Dependency injection**: `DiagnosticSession(transport, builder, decoder)` — swap `IsoTpTransport` for `MockTransport` to test without hardware.
- **All OBD-II bytes live in `src/config/obd_pids.py`** — never hardcode request/response bytes elsewhere.
- **Each diagnostic call follows**: build request → send → receive → validate → decode.
- **Context manager pattern** on all interfaces — always use `with session:` to ensure socket cleanup.

### Instantiation Pattern

```python
from infraestructure.transport.isotp_transport import IsoTpTransport
from infraestructure.protocol.obd2_builder import Obd2ProtocolBuilder
from infraestructure.decoder.obd2_decoder import Obd2DataDecoder
from session.diagnostic_session import DiagnosticSession

transport = IsoTpTransport(channel="can0", tx_id=0x7E0, rx_id=0x7E8)
session = DiagnosticSession(transport, Obd2ProtocolBuilder(), Obd2DataDecoder())
with session:
    rpm = session.get_engine_rpm()
```

Replace `IsoTpTransport` with `MockTransport` for testing — `MockTransport` ships with Arduino ECU simulator default responses (idle: RPM=850, Speed=0, Temp=56°C). Use `mock.inject_response(request_bytes, response_bytes)` to override ECU state.

## CAN/ISO-TP Hardware Notes

- Requires a SocketCAN-compatible interface (`can0`) on Linux for real hardware usage.
- ISO-TP parameters tuned to the Arduino ECU simulator: padding `0xAA`, blocksize 0, stmin 25ms.
- `cli.py` uses `sys.path.insert()` for imports — no package installation required.
