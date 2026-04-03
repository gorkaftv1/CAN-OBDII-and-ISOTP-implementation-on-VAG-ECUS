# ECU Simulator — SEAT Ibiza 6J 2012

Simulador de ECU de motor (1.4 MPI BXW) para Arduino MKR con CAN Shield.
Responde a peticiones OBD-II estándar sobre CAN bus (ISO-TP ISO 15765-2).

## Hardware

- Arduino MKR + CAN Shield
- CAN bus a 500 kbps, IDs 0x7E0 (request) / 0x7E8 (response)

## Modos soportados

| Modo | Descripción |
|------|-------------|
| 0x01 | 18 PIDs en tiempo real |
| 0x03 | Leer DTCs almacenados |
| 0x04 | Borrar DTCs |
| 0x09 | VIN (multi-frame) |

## Comandos serial (115200 baud)

Envía comandos ASCII terminados en `\n` desde el Monitor Serial del IDE o desde la Raspberry Pi:

| Comando | Descripción |
|---------|-------------|
| `THR <0-100>` | Fijar posición del acelerador (%) |
| `SPD <0-255>` | Override directo de velocidad (km/h) |
| `IGN <1\|0>` | Arrancar / apagar motor |
| `DTC ADD <hex4>` | Añadir DTC (ej: `DTC ADD 0171`) |
| `DTC CLR` | Borrar todos los DTCs |
| `STATUS` | Imprimir estado completo del vehículo |
| `RATE <ms>` | Cambiar intervalo de simulación (50–5000 ms) |
| `NOISE <0\|1>` | Activar/desactivar ruido CAN bus |
| `SCENARIO <name>` | Ciclo predefinido: `idle` / `drive` / `city` |

## Ruido CAN bus

Con `NOISE 1` activo el simulador inyecta:

- **Latencia variable** (1–15 ms) en cada respuesta
- **Drops** (~2 % de respuestas no se envían → timeout en el escáner)
- **NRC 0x22** esporádico (~1 %)
- **Tráfico de fondo** de otras ECUs VAG (0x280, 0x480, 0x320, 0x520)

## Dinámica del motor

- Throttle → RPM con inercia (lag de primer orden, τ ≈ 0.3 pasos)
- RPM + Load → Speed mediante modelo longitudinal simplificado
- Warmup: coolant 20 → 90 °C, aceite 20 → 95 °C
- Consumo: `fuelLevel` decrece proporcional a carga
