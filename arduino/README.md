# Arduino ECU Simulator

Emulates a SEAT Ibiza 6J 2012 ECU **(1.4 MPI, BXW)** — gasolina, aspirado natural, 70 kW — on an **Arduino MKR** board with a **CAN Shield**. Responds to OBD-II modes 01, 03, 04, and 09 over ISO-TP (ISO 15765-2) at 500 kbps.

## Hardware

### CAN Shield

The Arduino MKR CAN Shield attaches directly on top of the MKR board. No extra wiring is needed for CAN — connect the shield's CANH/CANL terminals to the CAN bus.

### Ignition Button (D7)

```
Arduino D7 ──┤ momentary push-button ├── GND
```

- Internal `INPUT_PULLUP` enabled — no external resistor needed.
- A hardware interrupt on the **FALLING** edge (button press) toggles the engine state.

## Flashing

1. Open `ecu_sim.ino` in **Arduino IDE 2.x**.
2. Install the **CAN** library by Sandeep Mistry via Library Manager.
3. Select your Arduino MKR board and upload.
4. Open Serial Monitor at **115200 baud**.

## Ignition Button — How It Works

The simulator starts with `vehicle.rpm = 0` (engine off). The ignition button on **D7** breaks the deadlock:

| Button press | What happens |
|-------------|--------------|
| 1st press | `keyOn = true` → `vehicle.rpm = 850` → simulation detects RPM > 0 → `engineRunning = true` |
| 2nd press | `keyOn = false` → `vehicle.rpm = 0` → simulation detects RPM == 0 → `engineRunning = false` |

A 200 ms software debounce (`IGNITION_DEBOUNCE_MS`) prevents bounce artifacts. The ISR (`onIgnitionButton`) only sets a `volatile bool` flag; all logic runs in `handleIgnitionButton()` at the top of `loop()`.

## Engine Simulation

`updateVehicleSimulation()` fires every second:

### Engine running

| Parameter | Behaviour |
|-----------|-----------|
| RPM | Holds 850 idle ± 50 RPM random jitter |
| Coolant temp | Warms from ambient → 90 °C |
| Oil temp | Warms from ambient → 95 °C |
| Engine load | `map(throttlePos, 0, 100, 15, 85)` % |
| MAF flow | `(rpm × load) / 500` |
| Timing advance | `map(rpm, 800, 6000, 8, 32)` ° |
| Fuel rail pressure | Fixed 300 kPa (MPI: regulated by pressure regulator, not RPM-dependent) |
| Runtime since start | Increments every second |

### Engine off

RPM, load, MAF, timing advance, and fuel pressure are 0. Coolant and oil cool slowly toward ambient (18 °C).

## Pre-loaded DTC

**P0171** (System Too Lean, Bank 1) is active at startup. Clear it with OBD-II Mode 0x04.

## ISO-TP Framing

All frames are exactly 8 bytes. Unused bytes are padded with `0xAA`.

| Frame type | When used | Format |
|-----------|-----------|--------|
| Single Frame | All responses with payload ≤ 7 bytes | `[0x0N, payload…, 0xAA…]` |
| First Frame | VIN (20-byte payload) | `[0x10, 0x14, payload[0..5]]` |
| Consecutive Frame | VIN continuation | `[0x21, payload[6..12]]`, `[0x22, payload[13..19]]` |
| Negative Response | Unsupported mode/PID | `[0x03, 0x7F, mode, NRC, 0xAA×4]` |

Flow Control timeout: **1000 ms**. If no FC is received, Consecutive Frames are sent anyway (tolerant mode for test-bench use).

## Serial Log Tags

| Tag | Meaning |
|-----|---------|
| `[OK]` | Successful initialisation step |
| `[ERROR]` | Fatal error (halts) |
| `[WARN]` | Non-fatal anomaly (unexpected PCI, FC timeout) |
| `[INFO]` | Informational message |
| `[SIM]` | Engine simulation state change (RPM-based detection) |
| `[IGN]` | Ignition button event (keyOn toggled) |
| `[RX]` | Incoming CAN frame decoded |
| `[TX SF]` | Single Frame transmitted |
| `[TX FF]` | First Frame transmitted (VIN) |
| `[TX CF]` | Consecutive Frame transmitted (VIN) |
| `[TX NRC]` | Negative Response transmitted |
