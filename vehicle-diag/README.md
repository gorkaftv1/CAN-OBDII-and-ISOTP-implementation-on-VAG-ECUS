# vehicle-diag

React Native + Expo (TypeScript) mobile application for real-time vehicle OBD2 diagnostics over Bluetooth Low Energy. Connects to a Raspberry Pi running a BLE GATT server that forwards OBD2 data from the vehicle ECU.

---

## Table of contents

1. [Architecture overview](#architecture-overview)
2. [BLE module](#ble-module)
3. [Domain layer](#domain-layer)
4. [State management](#state-management)
5. [Screens](#screens)
6. [Storage](#storage)
7. [Mock adapter](#mock-adapter)
8. [Getting started](#getting-started)
9. [Configuration](#configuration)

---

## Architecture overview

The app follows a strict 4-layer architecture. Each layer only imports from the layer below it — never upward.

```
┌─────────────────────────────────────────────────────┐
│  Presentation  (src/screens/)                       │
│  5 screens, React Native core components only       │
├─────────────────────────────────────────────────────┤
│  State         (src/stores/)                        │
│  Zustand stores — single source of truth per domain │
├─────────────────────────────────────────────────────┤
│  Domain        (src/domain/)                        │
│  Services, models, business logic                   │
├─────────────────────────────────────────────────────┤
│  Infrastructure (src/infrastructure/)               │
│  BleAdapter, MockAdapter, IVehicleAdapter           │
└─────────────────────────────────────────────────────┘
```

```
src/
├── domain/
│   ├── models/
│   │   ├── VehicleData.ts       OBD2 live metrics
│   │   ├── DtcCode.ts           Diagnostic trouble code
│   │   ├── LogEntry.ts          Structured log entry
│   │   ├── MonitorSample.ts     Push sample from BLE server
│   │   └── Widget.ts            Dashboard widget config
│   ├── services/
│   │   ├── ConnectionService.ts Connect/disconnect orchestration
│   │   ├── VehicleService.ts    Monitor lifecycle + PID mapping
│   │   └── LogService.ts        Structured log writer
│   └── ProtocolParser.ts        OBD2 raw-frame parser (mock path)
├── infrastructure/
│   ├── IVehicleAdapter.ts       Shared adapter contract
│   ├── BleAdapter.ts            Real BLE — Nordic UART Service
│   ├── MockAdapter.ts           Simulated data for offline dev
│   └── adapterFactory.ts        Runtime adapter selector
├── stores/
│   ├── connectionStore.ts
│   ├── vehicleStore.ts
│   ├── dashboardStore.ts
│   ├── dtcStore.ts
│   └── logsStore.ts
├── screens/
│   ├── connection/
│   ├── dashboard/
│   ├── dtcs/
│   ├── console/
│   ├── customize/
│   └── logs/
├── navigation/
│   └── AppNavigator.tsx         Bottom-tab navigator
└── shared/
    └── theme.ts                 Colors, spacing, typography
```

---

## BLE module

### Hardware

The server is a Raspberry Pi running [`bless`](https://github.com/kevincar/bless) on BlueZ/Linux. It exposes a **Nordic UART Service (NUS)** GATT profile and advertises under the name **`SEAT_DIAG`**.

### GATT profile

| UUID | Name | Direction | Purpose |
|------|------|-----------|---------|
| `6E400001-B5A3-F393-E0A9-E50E24DCCA9E` | NUS Service | — | Service descriptor |
| `6E400002-B5A3-F393-E0A9-E50E24DCCA9E` | RX Characteristic | app → Pi | App writes JSON commands here |
| `6E400003-B5A3-F393-E0A9-E50E24DCCA9E` | TX Characteristic | Pi → app | Pi notifies responses here |

### Message protocol: NDJSON

All messages are **UTF-8 JSON terminated with `\n`**. Because BLE notifications are capped at the negotiated MTU (512 bytes), messages longer than that arrive as multiple consecutive notifications. The app reassembles them in a string buffer and parses only when a `\n` is found.

```
Notification 1: {"status":"ok","data":[{"code":"P017
Notification 2: 1","description":"System Too Lean"}]}\n
                                                      ↑ parse here
```

This reassembly logic lives entirely in `BleAdapter.feedBuffer()`.

### Connection flow

```
1. BleManager.startDeviceScan([NUS_SERVICE_UUID])
        │
        ▼ device.name === "SEAT_DIAG"
2. device.connect()
3. device.requestMTU(512)          ← negotiate larger payload size
4. device.discoverAllServicesAndCharacteristics()
5. device.monitorCharacteristicForService(TX_UUID, callback)
        │
        ▼ connection ready
6. writeRx({"cmd":"monitor_start", ...}\n)
        │
        ▼ push samples arrive via TX notify
7. feedBuffer(chunk) → split on \n → JSON.parse → dispatch()
```

### Commands (app → Pi)

```jsonc
// Stream live OBD2 PIDs
{"cmd": "monitor_start", "pids": [5, 12, 13, 17, 47, 66], "interval_ms": 500}
{"cmd": "monitor_stop"}

// Read all PIDs in one shot
{"cmd": "snapshot"}

// Diagnostic trouble codes
{"cmd": "dtcs"}
{"cmd": "clear_dtcs"}

// Vehicle identification
{"cmd": "vin"}

// Historical sessions (stored on the Pi)
{"cmd": "sessions", "limit": 50}
{"cmd": "session_samples", "session_id": 1, "pid": 12, "limit": 1000}
{"cmd": "session_commands", "session_id": 1}
```

### Responses (Pi → app)

**Standard response envelope:**
```json
{"status": "ok",    "data": { ... }}
{"status": "error", "message": "description"}
```

**Monitor push sample (no request needed, arrives continuously):**
```json
{"type": "sample", "pid": 12, "name": "Engine RPM", "value": 1200.0, "unit": "rpm", "ts": 1713520000.89}
{"type": "error",  "pid": 12, "message": "timeout"}
```

**DTC list:**
```json
{"status": "ok", "data": [{"code": "P0171", "description": "System Too Lean"}]}
```

### BleAdapter internals

```
BleAdapter
├── scanAndConnect()       Scans for SEAT_DIAG, negotiates MTU, discovers GATT
├── subscribeToTx()        Registers notify callback on TX characteristic
├── feedBuffer(chunk)      Appends chunk to rxBuf, splits on \n, parses JSON lines
├── dispatch(msg)          Routes: type=sample → sampleCbs | status=ok/error → queue
├── request(cmd)           Adds to FIFO queue, writes JSON+\n to RX, awaits response
├── writeRx(data)          Encodes UTF-8 → base64, writes in 500-byte chunks
└── drainQueue(err)        Rejects all pending requests (on disconnect)
```

**Request-response correlation:** The server processes commands sequentially and responds in FIFO order. The adapter maintains a `Pending[]` queue — each `request()` call pushes one entry, and `dispatch()` shifts the head when a `status` response arrives. Monitor push messages (`type: "sample"`) bypass the queue entirely.

**Write chunking:** Commands are encoded to UTF-8, then sliced into 500-byte chunks. Each chunk is base64-encoded and written with `writeCharacteristicWithResponseForService`. For typical JSON commands this is a single write; only very large payloads (e.g. bulk history requests) require multiple writes.

### OBD2 PID mapping

| PID (decimal) | OBD2 name | VehicleData field |
|:---:|---|---|
| 4 | Engine Load | *(console only)* |
| 5 | Coolant Temperature | `engineTemp` |
| 12 | Engine RPM | `rpm` |
| 13 | Vehicle Speed | `speed` |
| 17 | Throttle Position | `throttlePosition` |
| 47 | Fuel Level | `fuelLevel` |
| 66 | Control Module Voltage | `voltage` |

---

## Domain layer

### ConnectionService

Orchestrates the full connection lifecycle. Called by `connectionStore`.

1. Sets the `scanning` UI phase, logs the event.
2. Fires a timer to transition to `connecting` after 1 s (mock) / 3 s (BLE, to account for scan time).
3. Calls `adapter.connect()`.
4. On success, calls `VehicleService.start()` and returns the device name.
5. On failure, re-throws so `connectionStore` can update the error state.

### VehicleService

Manages the monitor subscription lifecycle.

- `start()` — calls `adapter.startMonitor(MONITOR_PIDS, 500, handleSample)`.
- `stop()` — calls the returned unsubscribe function, resets `vehicleStore`.
- `handleSample(sample)` — for each incoming sample:
  - Writes a raw line to `logsStore.consoleLines` (visible in Console screen).
  - Maps `sample.pid` → `VehicleData` field and calls `vehicleStore.updatePartial()`.
  - Every 2 seconds writes an aggregated `data` entry to `logsStore.entries`.

### LogService

Thin wrapper around `useLogsStore.getState().addEntry()`. Generates a UUID v4 for each entry. Used by all services and stores to record structured events.

---

## State management

All state is managed with **Zustand** stores. Outside React components, state is accessed via `useXxxStore.getState()` — no hooks, no context.

### connectionStore

```typescript
{
  status: 'disconnected' | 'scanning' | 'connecting' | 'connected'
  deviceName: string | null
  error: string | null
  connect()    // → ConnectionService.connect()
  disconnect() // → ConnectionService.disconnect()
}
```

### vehicleStore

Holds the latest known values for all OBD2 metrics. Fields are merged incrementally as samples arrive — no field is ever `undefined` after the first sample.

```typescript
{
  latest: VehicleData | null   // null when disconnected
  updatePartial(data)          // merges incoming PID value
  clear()                      // resets to null on disconnect
}
```

### dtcStore

```typescript
{
  codes: DtcCode[]
  loading: boolean
  clearing: boolean
  error: string | null
  lastFetched: number | null
  fetch()   // adapter.fetchDtcs()
  clear()   // adapter.clearDtcs()
}
```

### logsStore

Two independent collections with separate size caps:

| Collection | Cap | Used by |
|---|---|---|
| `entries: LogEntry[]` | 500 | Logs screen (filterable) |
| `consoleLines: string[]` | 1000 | Console screen (raw terminal) |

### dashboardStore

Manages the ordered, toggleable list of dashboard widgets. Automatically persists to AsyncStorage on every mutation.

```typescript
{
  widgets: Widget[]    // sorted by `order` field
  loaded: boolean
  toggleWidget(id)     // flip visible flag + save
  moveUp(id)           // swap order with previous + save
  moveDown(id)         // swap order with next + save
  loadFromStorage()    // called once on CustomizeScreen mount
  saveToStorage()      // called after every mutation
}
```

---

## Screens

### Connection

Displays the current connection status with an animated indicator:

| Status | Color | Animation |
|---|---|---|
| `disconnected` | gray | none |
| `scanning` | blue | pulsing scale loop |
| `connecting` | yellow | pulsing scale loop |
| `connected` | green | slow opacity breathe |

Connect/Disconnect button calls the corresponding store action. Shows the device name when connected and an error message if the last connection attempt failed.

### Dashboard

Displays live `vehicleStore.latest` values as a 2-column card grid. Widget visibility and order come from `dashboardStore`. Each card applies color-coded thresholds:

| Metric | Warning | Critical |
|---|---|---|
| RPM | > 3 500 | > 5 500 |
| Engine Temp | > 90 °C | > 100 °C |
| Fuel Level | < 30 % | < 15 % |
| Voltage | < 12.4 V | < 12.0 V |

Shows a "not connected" empty state when `connectionStore.status !== 'connected'`.

### DTCs (Fault Codes)

Sends `{"cmd":"dtcs"}` on demand and displays the result as a list with a severity sidebar bar (red = critical, yellow = warning). Offers a **Scan** button to refresh and a **Clear** button (guarded by an `Alert` confirmation) that sends `{"cmd":"clear_dtcs"}`.

### Console

Scrolling terminal view of `logsStore.consoleLines`. Lines are colour-coded:

- `[RX]` lines → green (incoming samples)
- `[ERR]` lines → red (PID errors from server)
- `[TX]` lines → yellow (commands sent)

Auto-scrolls to the bottom on every new line. Clear button wipes `consoleLines`.

### Customize

Lets the user reorder and toggle the visibility of dashboard widgets. Changes are written to AsyncStorage immediately via `dashboardStore`. Up/Down arrow buttons swap adjacent widget order.

### Logs

Flat list of `logsStore.entries` in reverse-chronological order (newest at top, via FlatList `inverted`). Filterable by type: **All / Data / Command / Error / Info**.

---

## Storage

### AsyncStorage — dashboard layout

`dashboardStore` persists the full `Widget[]` array to AsyncStorage under the key `@dashboard_widgets` every time the user toggles a widget or changes its order. On app start, `CustomizeScreen` calls `loadFromStorage()` once (guarded by the `loaded` flag) to restore the saved layout.

```
Key: @dashboard_widgets
Value: JSON-serialised Widget[]
[
  {"id":"rpm","label":"RPM","dataKey":"rpm","unit":"rpm","visible":true,"order":0},
  ...
]
```

If the key is absent (first launch) or the read fails, the store falls back to `DEFAULT_WIDGETS`.

### In-memory stores

All other state (`vehicleStore`, `connectionStore`, `dtcStore`, `logsStore`) is **ephemeral** — it resets when the app is closed. The console log and log entries are bounded ring buffers (1 000 and 500 entries respectively) that never grow beyond their cap.

### Pi-side historical data (future)

The Raspberry Pi server stores session history in its own SQLite database. The app can retrieve it via the `sessions` / `session_samples` / `session_commands` commands over BLE. This data is never persisted on the device — it is fetched on demand and displayed in the Logs screen (implementation pending).

---

## Mock adapter

`MockAdapter` implements the same `IVehicleAdapter` contract as `BleAdapter` but generates simulated data internally. It is useful for UI development without hardware.

The simulation models a vehicle that:
- Idles at ~800 RPM and accelerates with random throttle inputs (0–80 %).
- Starts cold (20 °C) and warms up toward 88 °C at 0.3 °C/tick.
- Consumes fuel at 0.005 %/tick.
- Has three pre-seeded DTCs (one critical, two warnings) that disappear after `clearDtcs()`.

Toggle mock mode in [`adapterFactory.ts`](src/infrastructure/adapterFactory.ts):

```typescript
export const USE_MOCK = true;   // simulated data
export const USE_MOCK = false;  // real BLE (SEAT_DIAG)
```

---

## Getting started

### Prerequisites

| Tool | Version | Notes |
|---|---|---|
| Node.js | 18+ | |
| npm | 9+ | comes with Node |
| Expo CLI | latest | `npm install -g expo-cli` |
| Android Studio | latest | for Android builds |
| Xcode | 15+ | macOS only, for iOS builds |
| JDK | 17 | required by Android Gradle |

For real BLE: a physical device with Bluetooth 4.0+. BLE **does not work on emulators/simulators**.

---

### 1. Install dependencies

```bash
cd vehicle-diag
npm install
npx expo install react-native-ble-plx
```

---

### 2. Choose a run mode

This app uses `react-native-ble-plx`, a native module. **Expo Go cannot run it.**
Two paths are available depending on whether you have the Pi hardware:

| Mode | `USE_MOCK` | Requires |
|---|---|---|
| Mock (offline) | `true` | Any device or emulator |
| Real BLE | `false` | Physical device + dev build |

Set the flag in [`src/infrastructure/adapterFactory.ts`](src/infrastructure/adapterFactory.ts):

```typescript
export const USE_MOCK = true;   // no hardware needed
export const USE_MOCK = false;  // connects to SEAT_DIAG over BLE
```

---

### 3a. Run on Android

#### Requirements
- Android Studio installed with an Android SDK (API 33+ recommended)
- A USB-connected physical device **or** an emulator (mock mode only)
- USB debugging enabled on the device (`Settings → Developer options → USB debugging`)

#### Local dev build

```bash
npx expo run:android
```

This compiles the native code, installs the APK on the connected device and starts Metro. The first build takes several minutes; subsequent builds are incremental.

If you have multiple devices connected, specify one:

```bash
npx expo run:android --device
```

#### Release APK (for distribution without Play Store)

```bash
cd android
./gradlew assembleRelease
# Output: android/app/build/outputs/apk/release/app-release.apk
```

#### EAS Build (cloud — no Android Studio needed)

```bash
npx eas build --profile development --platform android
# Scan the QR code to install the build on your device
```

#### Common Android issues

| Problem | Fix |
|---|---|
| `adb: device not found` | Enable USB debugging; try a different cable or port |
| `SDK location not found` | Create `android/local.properties` with `sdk.dir=/path/to/Android/Sdk` |
| Bluetooth permission denied at runtime | The app requests permissions on first Connect tap — allow them |
| BLE scan returns no devices | On Android 12+ location permission is required for BLE scan; also ensure Bluetooth and Location are enabled on the device |

---

### 3b. Run on iOS

#### Requirements
- macOS with Xcode 15+ installed
- Xcode Command Line Tools: `xcode-select --install`
- Apple Developer account (free is enough for device builds via Xcode)
- CocoaPods: `sudo gem install cocoapods`
- A USB-connected iPhone or iPad running iOS 16+

#### Install CocoaPods

```bash
cd ios
pod install
cd ..
```

#### Local dev build

```bash
npx expo run:ios
```

To target a specific device or simulator:

```bash
npx expo run:ios --device          # interactive picker
npx expo run:ios --simulator "iPhone 15 Pro"
```

#### Signing (physical device)

Expo manages signing automatically for development builds. If you see a signing error in Xcode:

1. Open `ios/vehiclediag.xcworkspace` in Xcode.
2. Select the `vehiclediag` target → **Signing & Capabilities**.
3. Set your Apple ID team and ensure **Automatically manage signing** is checked.
4. Re-run `npx expo run:ios`.

#### EAS Build (cloud — no macOS needed from other platforms)

```bash
npx eas build --profile development --platform ios
```

#### Common iOS issues

| Problem | Fix |
|---|---|
| `pod install` fails | Run `pod repo update` then `pod install` again |
| "Untrusted developer" on device | `Settings → General → VPN & Device Management` → trust your certificate |
| Bluetooth permission not shown | Clean build folder in Xcode (`Product → Clean Build Folder`) and rebuild |
| BLE scan finds nothing | Ensure Bluetooth is on; iOS requires the `NSBluetoothAlwaysUsageDescription` key (already set in `app.json`) |

---

### 4. Permissions

Both platforms require Bluetooth permissions to be granted at runtime on the first Connect tap. The app does not request them proactively at launch.

**Android** (declared in `AndroidManifest.xml` via the `react-native-ble-plx` Expo plugin):

```
BLUETOOTH, BLUETOOTH_ADMIN
BLUETOOTH_SCAN, BLUETOOTH_CONNECT   (API ≥ 31 / Android 12+)
ACCESS_FINE_LOCATION                (required for BLE scan on API < 31)
ACCESS_COARSE_LOCATION
```

**iOS** (`Info.plist` — set in `app.json → expo.ios.infoPlist`):

```
NSBluetoothAlwaysUsageDescription
NSBluetoothPeripheralUsageDescription
```

---

### 5. Development workflow

```
Mock mode (fast iteration, no hardware)
  npx expo start --clear          ← works with Expo Go if USE_MOCK=true
                                    and react-native-ble-plx is not imported
                                    (use adapterFactory lazy require)

Real BLE (hardware in the loop)
  npx expo run:android            ← native build, installs on device
  npx expo run:ios                ← native build, installs on device
  # Metro stays open — JS changes hot-reload without rebuilding native code
  # Native changes (e.g. new permissions) require a full rebuild
```

After the first `npx expo run:*` build, you only need to rerun it if you:
- Add or remove a native module
- Change `app.json` permissions or plugins
- Upgrade Expo SDK

---

## Configuration

| File | Key | Default | Effect |
|---|---|---|---|
| `src/infrastructure/adapterFactory.ts` | `USE_MOCK` | `false` | Switch between real BLE and simulated data |
| `src/domain/services/VehicleService.ts` | `MONITOR_PIDS` | `[4,5,12,13,17,47,66]` | OBD2 PIDs requested from the server |
| `src/domain/services/VehicleService.ts` | `INTERVAL_MS` | `500` | Monitor sampling interval |
| `src/infrastructure/BleAdapter.ts` | `SCAN_TIMEOUT_MS` | `20 000` | BLE scan timeout before error |
| `src/infrastructure/BleAdapter.ts` | `REQUEST_TIMEOUT_MS` | `10 000` | Per-command response timeout |
| `src/infrastructure/BleAdapter.ts` | `WRITE_CHUNK_BYTES` | `500` | Max bytes per BLE write operation |
