# Servidor Bluetooth — SEAT Ibiza 6J Diagnostics

Servidor Bluetooth Classic SPP (Serial Port Profile) que expone el bus CAN/OBD-II a la app móvil React Native. Corre en la Raspberry Pi.

## Requisitos

```bash
# Sistema (una sola vez)
sudo apt install libbluetooth-dev bluez
sudo systemctl enable bluetooth
sudo hciconfig hci0 piscan
sudo hciconfig hci0 name "SEAT_DIAG_PI"

# Python
pip install PyBluez2
```

## Arrancar el servidor

```bash
cd src
python scripts/server.py
```

## Protocolo

NDJSON sobre RFCOMM (un objeto JSON por línea terminada en `\n`).

### Comandos disponibles

| Comando | Descripción |
|---------|-------------|
| `{"cmd": "snapshot"}` | Lee 18 PIDs de golpe |
| `{"cmd": "dtcs"}` | DTCs almacenados |
| `{"cmd": "clear_dtcs"}` | Borrar DTCs |
| `{"cmd": "vin"}` | Leer VIN |
| `{"cmd": "monitor_start", "pids": [...], "interval_ms": 500}` | Iniciar monitor live |
| `{"cmd": "monitor_stop"}` | Parar monitor |
| `{"cmd": "sessions"}` | Historial de sesiones |
| `{"cmd": "session_samples", "session_id": 1, "pid": 12}` | Muestras de sesión |
| `{"cmd": "session_commands", "session_id": 1}` | Comandos de sesión |

### Respuestas

```json
{"status": "ok", "data": {...}}
{"status": "error", "message": "..."}
```

### Push del monitor

Cuando el monitor está activo, el servidor envía sin solicitud:

```json
{"type": "sample", "pid": 12, "name": "Engine RPM", "value": 850.0, "unit": "rpm", "ts": 1234567.89}
```

## Probar desde PC

```bash
# Emparejar primero con la Pi desde el sistema operativo, luego:
rfcomm connect hci0 <MAC_PI>
# En otra terminal:
echo '{"cmd": "vin"}' | nc -q1 /dev/rfcomm0
```
