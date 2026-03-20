# CAN OBD-II and ISO-TP Implementation on VAG ECUs

University final project (TFT) at ULPGC. A full-stack automotive diagnostic system consisting of an Arduino ECU simulator and a Python OBD-II scanner, communicating over CAN bus using ISO-TP (ISO 15765-2).

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

- **CAN bitrate**: 500 kbps
- **ISO-TP padding byte**: `0xAA`
- **ECU listens on**: `0x7E0`, responds on `0x7E8`

## Quick Start

### Python scanner (no hardware required)

```bash
pip install -r Requirements.txt
python src/scripts/cli.py
```

The CLI defaults to `MockTransport` for demo mode — no CAN hardware needed.

### Arduino ECU simulator

1. Open `arduino/ecu_sim.ino` in Arduino IDE and upload to an **Arduino MKR** board.
2. Wire a momentary push-button between pin **D7** and **GND** (ignition simulation).
3. Open the Serial Monitor at **115200 baud**.

### Real hardware (Raspberry Pi + CAN HAT)

```bash
sudo ip link set can0 type can bitrate 500000
sudo ip link set can0 up
python src/scripts/cli.py          # edit cli.py to use IsoTpTransport
```

## Supported OBD-II Services

| Mode | Service |
|------|---------|
| `0x01` | Live data — 18 PIDs (RPM, speed, temperatures, fuel, MAF, etc.) |
| `0x03` | Read stored DTCs |
| `0x04` | Clear DTCs |
| `0x09` | VIN via ISO-TP multi-frame |

## Simulated Vehicle

SEAT Ibiza 6J 2012 — 1.4 MPI (BXW), gasolina, aspirado natural, 70 kW (85 CV)
VIN: `VSSZZZ6JZCR123456` · Odometer: 85 000 km
Engine idles at **850 RPM**, warms to **90 °C** coolant / **95 °C** oil.

## Repository Layout

```
├── arduino/           # Arduino ECU simulator firmware
├── src/               # Python OBD-II diagnostic scanner
├── doc/               # LaTeX thesis document
├── Requirements.txt   # Python dependencies
└── CLAUDE.md          # Claude Code guidance
```
