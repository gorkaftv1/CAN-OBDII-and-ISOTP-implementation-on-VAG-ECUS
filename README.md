# CAN OBD-II and ISO-TP Implementation on VAG ECUs

**University final project (TFT) — ULPGC**
**Vehicle**: SEAT Ibiza 6J 2012 — 1.4 MPI BXW, 70 kW (85 CV), petrol, naturally aspirated

A full-stack automotive diagnostic system: an Arduino ECU simulator paired with a Python OBD-II scanner, communicating over CAN bus using ISO-TP (ISO 15765-2).

---

## Components

| Component | Location | Description |
|-----------|----------|-------------|
| ECU Simulator | [`arduino/`](arduino/) | Arduino firmware emulating a SEAT Ibiza 6J 2012 ECU |
| Python Scanner | [`src/`](src/) | OBD-II diagnostic tool with ISO-TP transport |

## Hardware Setup

```
Arduino MKR + CAN Shield  ←── CAN bus (500 kbps) ──→  Raspberry Pi 4 + CAN HAT
  ECU Simulator (TX: 0x7E8)                             Python Scanner (TX: 0x7E0)
```

| Parameter | Value |
|-----------|-------|
| CAN bitrate | 500 kbps |
| Scanner CAN ID (TX) | `0x7E0` |
| ECU CAN ID (RX/TX) | `0x7E8` |
| ISO-TP padding byte | `0xAA` |

## Quick Start

### Python scanner (no hardware required)

```bash
pip install -r Requirements.txt
python src/scripts/cli.py
```

The CLI defaults to `MockTransport` — no CAN hardware needed.

### Arduino ECU simulator

1. Open `arduino/ecu_sim.ino` in Arduino IDE and upload to an **Arduino MKR** board.
2. Wire a momentary push-button between pin **D7** and **GND** (ignition simulation).
3. Open Serial Monitor at **115200 baud**.

### Real hardware (Raspberry Pi + CAN HAT)

```bash
sudo ip link set can0 type can bitrate 500000
sudo ip link set can0 up
python src/scripts/cli.py          # edit cli.py to use IsoTpTransport
```

---

## Protocol Reference

The sections below document the full protocol stack used by this project, from the physical CAN layer up to the OBD-II application layer. Each section maps directly to the constants and logic in `src/config/can_config.py` and `src/config/obd_pids.py`.

---

## CAN Bus — ISO 11898

### What is CAN?

Controller Area Network (CAN) is a multi-master, differential serial bus developed by Bosch in 1986 \[1\]. It uses two wires (CANH and CANL) operating at a differential voltage — typically ±2 V — and supports bit rates up to 1 Mbps. CAN is the dominant in-vehicle network for powertrain, chassis, and body ECUs \[2\].

### Frame Structure

A standard CAN 2.0A data frame (11-bit identifier) consists of the following fields \[1\]\[2\]:

| Field | Bits | Description |
|-------|------|-------------|
| SOF | 1 | Start Of Frame — dominant (0) bit marks frame start |
| Arbitration ID | 11 | Node address; lower numeric value = higher priority |
| RTR | 1 | Remote Transmission Request (0 = data frame) |
| IDE | 1 | Identifier Extension (0 = standard 11-bit) |
| DLC | 4 | Data Length Code — number of payload bytes (0–8) |
| Data | 0–64 | Payload bytes |
| CRC | 15+1 | Cyclic Redundancy Check + delimiter |
| ACK | 2 | Any receiver drives ACK slot dominant to confirm receipt |
| EOF | 7 | End Of Frame — seven recessive bits |

### Bus Arbitration

All nodes transmit simultaneously. When a node writes a recessive (1) bit but observes a dominant (0) bit on the bus, it loses arbitration and backs off immediately — no collision, no data corruption \[2\]. Lower CAN IDs always win.

### Constants Used in This Project

```python
CAN_TX_ID   = 0x7E0   # Scanner → ECU (functional address, SAE J1979 §5.3.2)
CAN_RX_ID   = 0x7E8   # ECU → Scanner (physical response address)
CAN_BITRATE = 500_000 # 500 kbps — standard OBD-II CAN rate
```

Source: `src/config/can_config.py`

---

## ISO-TP — ISO 15765-2

### Why ISO-TP?

A bare CAN frame carries at most 8 bytes of payload. Many OBD-II responses exceed that limit — for example, a VIN is 17 ASCII characters, and a DTC list can be dozens of bytes. ISO 15765-2 defines a **Transport Protocol** that segments and reassembles messages of up to 4095 bytes over CAN \[3\]\[8\].

### Frame Types

ISO-TP defines four frame types, distinguished by the upper nibble of the first byte (Protocol Control Information, PCI) \[3\]:

#### Single Frame (SF) — PCI `0x0_`

Used when the entire message fits in one CAN frame (≤ 7 bytes of data).

```
Byte 0: [0x0 | len]   — upper nibble = 0, lower nibble = payload length
Byte 1–7: data
```

#### First Frame (FF) — PCI `0x1_`

Starts a multi-frame message. Carries the total message length and the first 6 bytes of data.

```
Byte 0: [0x1 | len_high]  — upper nibble = 1, lower nibble = high 4 bits of total length
Byte 1: len_low            — low 8 bits of total length (12-bit length field)
Byte 2–7: first 6 bytes of data
```

#### Consecutive Frame (CF) — PCI `0x2_`

Each subsequent frame after the FF. Carries 7 bytes of data and a 4-bit sequence counter (1–F, then wraps to 0).

```
Byte 0: [0x2 | seq_num]  — upper nibble = 2, lower nibble = sequence number
Byte 1–7: next 7 bytes of data
```

#### Flow Control (FC) — PCI `0x3_`

Sent by the receiver after an FF to authorize transmission of CFs. Controls pacing.

```
Byte 0: [0x3 | flow_status]  — 0=ContinueToSend, 1=Wait, 2=Overflow
Byte 1: block_size            — 0 = no limit (send all remaining CFs)
Byte 2: STmin                 — minimum separation time between CFs (ms or µs encoding)
```

### Parameters Used in This Project

| Parameter | Value | Source constant |
|-----------|-------|-----------------|
| Padding byte | `0xAA` | `ISOTP_PADDING_BYTE` |
| Block size | `0` (no limit) | `ISOTP_CF_SEPARATION_MS` context |
| STmin | `25 ms` | `ISOTP_CF_SEPARATION_MS` |
| FC timeout | `1000 ms` | `ISOTP_FC_TIMEOUT_MS` |
| SF max payload | `7 bytes` | `ISOTP_SF_MAX_PAYLOAD` |
| FF data bytes | `6 bytes` | `ISOTP_FF_DATA_BYTES` |
| CF data bytes | `7 bytes` | `ISOTP_CF_DATA_BYTES` |

Source: `src/config/can_config.py`; python-can-isotp library \[10\] handles segmentation/reassembly.

---

## OBD-II — SAE J1979 / ISO 15031-5

### Background

OBD-II (On-Board Diagnostics, second generation) is mandated in all petrol cars sold in the US since 1996 and in the EU since 2001. It defines a standardised diagnostic interface that any scan tool can use to query engine and emissions data \[4\].

Over CAN bus, OBD-II messages are carried as ISO-TP payloads:

- **Request**: `[mode_byte, pid_byte]` sent from scanner to ECU.
- **Positive response**: `[mode + 0x40, pid_byte, data_A, data_B, ...]`
- **Negative response** (NRC frame): `[0x7F, mode_byte, NRC_code]`

The `+0x40` offset on positive responses means Mode `0x01` responses start with `0x41`, Mode `0x03` with `0x43`, etc.

### OBD-II Services Used in This Project

| Mode | Constant | Description |
|------|----------|-------------|
| `0x01` | `OBD_MODE_LIVE_DATA` | Current data — live powertrain PIDs |
| `0x03` | `OBD_MODE_READ_DTCS` | Read stored Diagnostic Trouble Codes |
| `0x04` | `OBD_MODE_CLEAR_DTCS` | Clear all stored DTCs and freeze-frame data |
| `0x09` | `OBD_MODE_VEHICLE_INFO` | Vehicle information (VIN = InfoType `0x02`) |

Source: `src/config/can_config.py`

---

## Mode 0x01 — Live Data PIDs

The table below lists all 18 PIDs implemented in `src/config/obd_pids.py`. Formulas are SAE J1979 \[4\] as indexed in \[6\].

In every formula: **A** = `raw[2]` and **B** = `raw[3]` in the positive-response frame `[0x41, PID, A, B, ...]`.

| PID | Name | Unit | Bytes | SAE J1979 Formula |
|-----|------|------|-------|-------------------|
| `0x04` | Engine Load | % | 1 | `A × 100 / 255` |
| `0x05` | Coolant Temp | °C | 1 | `A − 40` |
| `0x06` | Short Fuel Trim Bank 1 | % | 1 | `A × 100 / 128 − 100` |
| `0x07` | Long Fuel Trim Bank 1 | % | 1 | `A × 100 / 128 − 100` |
| `0x0C` | Engine RPM | rpm | 2 | `(256A + B) / 4` |
| `0x0D` | Vehicle Speed | km/h | 1 | `A` |
| `0x0E` | Timing Advance | ° | 1 | `A / 2 − 64` |
| `0x0F` | Intake Air Temp | °C | 1 | `A − 40` |
| `0x10` | MAF Air Flow Rate | g/s | 2 | `(256A + B) / 100` |
| `0x11` | Throttle Position | % | 1 | `A × 100 / 255` |
| `0x1F` | Runtime Since Start | s | 2 | `256A + B` |
| `0x23` | Fuel Rail Pressure | kPa | 2 | `(256A + B) × 10` |
| `0x2F` | Fuel Level | % | 1 | `A × 100 / 255` |
| `0x31` | Distance Since DTC Clear | km | 2 | `256A + B` |
| `0x33` | Barometric Pressure | kPa | 1 | `A` |
| `0x42` | Control Module Voltage | V | 2 | `(256A + B) / 1000` |
| `0x46` | Ambient Air Temp | °C | 1 | `A − 40` |
| `0x5C` | Engine Oil Temp | °C | 1 | `A − 40` |

The formulas in this table are verified against the `decode` lambdas in `src/config/obd_pids.py` (ground truth) and cross-checked against Wikipedia \[6\] / SAE J1979 Table A1 \[4\].

---

## DTCs — Mode 0x03 / 0x04

### DTC Format (SAE J1979 §6.3 / ISO 15031-6)

Each Diagnostic Trouble Code is encoded in two bytes. The upper two bits of byte 0 encode the system \[4\]:

| Bits `[15:14]` | System | Prefix |
|----------------|--------|--------|
| `00` | Powertrain | P |
| `01` | Chassis | C |
| `10` | Body | B |
| `11` | Network | U |

Bits `[13:12]` encode standard (`00`, `01`) or manufacturer-specific (`10`, `11`) codes. Bits `[11:0]` are the four-digit numeric fault code.

**Example**: raw bytes `0x03 0x01` → bits `[15:14]=00` (Powertrain) → **P0301** — Cylinder 1 misfire detected.

### Clear DTCs (Mode 0x04)

Sending `[0x04]` instructs the ECU to erase all stored DTCs, freeze-frame data, and readiness monitors. The ECU responds with `[0x44]` (positive response, no data bytes). In this project the clear operation requires the vehicle to be stationary (`NRC_CONDITIONS_NOT_CORRECT = 0x22` is returned otherwise).

---

## UDS NRC Codes — ISO 14229-1

When the ECU cannot service a request, it returns a **Negative Response** frame \[5\]:

```
[0x7F, mode_byte, NRC_code]
```

NRC codes implemented in this project (`src/config/can_config.py`):

| Code | Constant | Meaning |
|------|----------|---------|
| `0x11` | `NRC_SERVICE_NOT_SUPPORTED` | ECU does not implement this OBD-II mode |
| `0x12` | `NRC_SUBFUNCTION_NOT_SUPPORTED` | PID or InfoType not supported by this ECU |
| `0x13` | `NRC_INVALID_MESSAGE_FORMAT` | Request frame is malformed or has wrong byte count |
| `0x22` | `NRC_CONDITIONS_NOT_CORRECT` | ECU state prevents servicing the request (e.g. engine running when clear-DTC is sent) |
| `0x31` | `NRC_REQUEST_OUT_OF_RANGE` | PID value outside the supported range |
| `0x33` | `NRC_SECURITY_ACCESS_DENIED` | Protected service requires authentication first |

Source: ISO 14229-1:2020 §11 \[5\]; `src/config/can_config.py`.

---

## Simulated Vehicle

| Parameter | Value |
|-----------|-------|
| Model | SEAT Ibiza 6J 2012 |
| Engine | 1.4 MPI BXW, 70 kW (85 CV), petrol, N/A |
| VIN | `VSSZZZ6JZCR123456` |
| Odometer | 85 000 km |
| Idle RPM | 850 rpm |
| Coolant temp (warm) | 90 °C |
| Oil temp (warm) | 95 °C |

The `MockTransport` ships with these idle-state default responses. Override them in tests with `mock.inject_response(request_bytes, response_bytes)`.

---

## Repository Layout

```
├── arduino/           # Arduino ECU simulator firmware (ecu_sim.ino, ecu_protocol.h)
├── src/
│   ├── core/          # Domain layer: interfaces, models, exceptions
│   ├── infraestructure/  # Transport (ISO-TP / mock), protocol builder, decoder
│   ├── config/        # CAN constants (can_config.py) and PID registry (obd_pids.py)
│   ├── session/       # DiagnosticSession — application-layer orchestrator
│   ├── scripts/       # cli.py — interactive diagnostic menu
│   └── test/          # Unit and integration tests (pytest)
├── doc/               # LaTeX thesis document
├── Requirements.txt   # Python dependencies
└── CLAUDE.md          # Claude Code guidance
```

---

## References

1. **Bosch CAN Specification 2.0** (1991) — Robert Bosch GmbH. Original protocol definition; available as PDF from Bosch archives.
2. **Wikipedia — CAN bus** <https://en.wikipedia.org/wiki/CAN_bus> — Frame structure, arbitration, error handling.
3. **ISO 15765-2:2016** — Road vehicles — Diagnostic communication over CAN — Part 2: Transport protocol and network layer services. ISO.org.
4. **SAE J1979:2012** — E/E Diagnostic Test Modes. Society of Automotive Engineers. Defines all OBD-II modes and PID decode formulas (Table A1).
5. **ISO 14229-1:2020** — Road vehicles — UDS — Part 1: Application layer. Defines Negative Response Codes.
6. **Wikipedia — OBD-II PIDs** <https://en.wikipedia.org/wiki/OBD-II_PIDs> — Community-maintained table of all Mode 0x01 PIDs with SAE J1979 formulas (matches \[4\]).
7. **ISO 11898-1:2015** — Road vehicles — CAN — Part 1: Data link layer and physical signalling. ISO.org.
8. **Wikipedia — ISO 15765-2** <https://en.wikipedia.org/wiki/ISO_15765-2> — Frame type diagrams and flow-control description.
9. **python-can library** <https://python-can.readthedocs.io/> — Python bindings for SocketCAN used in `IsoTpTransport`.
10. **python-can-isotp library** <https://can-isotp.readthedocs.io/> — ISO-TP segmentation/reassembly layer over python-can used for multi-frame messages.
