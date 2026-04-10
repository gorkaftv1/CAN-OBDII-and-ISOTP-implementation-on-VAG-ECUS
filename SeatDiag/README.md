# SeatDiag — App React Native

App Android para diagnóstico OBD-II del SEAT Ibiza 6J 2012. Se conecta a la Raspberry Pi por Bluetooth Classic (SPP/RFCOMM) y muestra un dashboard en tiempo real con los datos del CAN bus.

---

## Requisitos previos

### PC de desarrollo

| Herramienta | Versión mínima |
|-------------|----------------|
| Node.js | 18 |
| React Native CLI | `npm install -g react-native-cli` |
| Android Studio | Hedgehog o superior |
| Android SDK | API 31+ |
| Java JDK | 17 |

### Dispositivo Android (físico, no emulador)

- Android 10 o superior
- Bluetooth activado
- La Raspberry Pi emparejada previamente desde Ajustes → Bluetooth

> Los emuladores no tienen hardware Bluetooth real. Se necesita un dispositivo físico.

---

## 1. Preparar la Raspberry Pi

Antes de arrancar la app, la Pi tiene que estar corriendo el servidor.

### 1.1 Configurar Bluetooth en la Pi (una sola vez)

```bash
sudo apt install libbluetooth-dev bluez
sudo systemctl enable bluetooth
sudo systemctl start bluetooth

# Hacer la Pi visible y ponerle nombre
sudo hciconfig hci0 piscan
sudo hciconfig hci0 name "SEAT_DIAG_PI"
```

### 1.2 Instalar dependencias Python

```bash
pip install PyBluez2
```

### 1.3 Arrancar el servidor

```bash
cd CAN-OBDII-and-ISOTP-implementation-on-VAG-ECUS/src
python scripts/server.py
```

El servidor imprime en consola:
```
[BT] Escuchando en RFCOMM canal 1 — servicio 'SEAT_DIAG'
[BT] Esperando conexión Bluetooth...
```

### 1.4 Emparejar la Pi con el móvil

En el móvil: **Ajustes → Bluetooth → Buscar dispositivos** → seleccionar `SEAT_DIAG_PI`. Solo hace falta hacerlo una vez.

---

## 2. Instalar y ejecutar la app

```bash
cd SeatDiag
npm install
npx react-native run-android
```

Esto compila la app y la instala directamente en el dispositivo conectado por USB. Asegúrate de tener habilitada la **depuración USB** en el móvil (Opciones de desarrollador).

---

## 3. Flujo de uso

### Pantalla 1 — Escanear

Al abrir la app aparece la pantalla de escaneo. Pulsa **Escanear** para buscar dispositivos Bluetooth.

- Los dispositivos ya emparejados aparecen inmediatamente.
- `SEAT_DIAG_PI` aparece resaltado en verde.
- Pulsa sobre él para pasar a la pantalla de conexión.

### Pantalla 2 — Conectando

Muestra un spinner mientras establece la conexión RFCOMM. Si falla (Pi apagada, fuera de rango) vuelve a la pantalla anterior con el error.

### Pantalla 3 — Dashboard

Una vez conectado:

- El monitor arranca automáticamente con 500 ms de intervalo.
- Se muestran 3 gauges principales y 8 valores secundarios actualizados en tiempo real.

| PID | Visualización |
|-----|--------------|
| RPM | Arco SVG circular (0–7000), gradiente verde→rojo |
| Velocidad | Número grande en km/h |
| Temp. refrigerante | Termómetro vertical, gradiente azul→rojo |
| Carga motor, Throttle, MAF… | Barras horizontales con porcentaje |

Desde el dashboard puedes navegar a:
- **DTCs** — leer y borrar códigos de error
- **Historial** — sesiones pasadas con gráficas

### Pantalla 4 — DTCs

- Pulsa **Leer DTCs** para consultar los fallos almacenados en el ECU.
- Si hay DTCs aparece la lista con código y descripción.
- **Borrar DTCs** pide confirmación antes de ejecutarse.

### Pantalla 5 — Historial

Lista de sesiones guardadas en la Raspberry Pi con fecha, duración y número de muestras. Pulsa cualquiera para ver el detalle.

### Pantalla 6 — Detalle de sesión

Gráfica temporal de los valores registrados. Usa el selector de PID para cambiar entre RPM, velocidad, temperatura, etc.

---

## 4. Verificar que la conexión funciona (desde PC)

Si quieres probar el servidor sin la app, desde otro Linux:

```bash
# Emparejar primero con la Pi
bluetoothctl
  scan on
  pair <MAC_PI>
  connect <MAC_PI>

# Conectar por RFCOMM
rfcomm connect hci0 <MAC_PI>

# En otra terminal, enviar un comando
echo '{"cmd": "snapshot"}' > /dev/rfcomm0
cat /dev/rfcomm0
```

---

## 5. Solución de problemas

| Síntoma | Causa probable | Solución |
|---------|---------------|----------|
| "No hay dispositivos" en el escaneo | Permisos BT no concedidos | Conceder permisos de Bluetooth y Ubicación en Ajustes → Aplicaciones → SeatDiag |
| La Pi no aparece en el escaneo | No emparejada o no visible | Ejecutar `sudo hciconfig hci0 piscan` en la Pi |
| Fallo de conexión RFCOMM | Servidor no arrancado | Comprobar que `python scripts/server.py` está corriendo |
| Dashboard sin datos | Monitor no arrancó | Reiniciar la app; el monitor arranca automáticamente al entrar al dashboard |
| Crash al abrir app | Falta `android/` nativo | Ver sección de compilación más abajo |

---

## 6. Estructura del proyecto

```
SeatDiag/
  index.js                  — Entry point React Native
  src/
    App.tsx                 — Registro de navegación
    navigation/
      AppNavigator.tsx      — Stack navigator (dark theme)
    screens/
      ScanScreen.tsx        — Descubrimiento BT
      ConnectingScreen.tsx  — Conexión RFCOMM
      DashboardScreen.tsx   — Dashboard live
      DtcScreen.tsx         — Lectura/borrado de DTCs
      HistoryScreen.tsx     — Historial de sesiones
      SessionDetailScreen.tsx — Gráficas por PID
    services/
      BluetoothService.ts   — Singleton RFCOMM + NDJSON
      DiagService.ts        — Comandos tipados sobre BluetoothService
    components/
      GaugeCard.tsx         — Gauges SVG/barras
      ConnectionBadge.tsx   — Badge estado BT
    hooks/
      useLiveData.ts        — Suscripción al monitor live
      useDiagnostics.ts     — DTCs y VIN con estado carga/error
    types/
      index.ts              — Tipos TS (MonitorSample, DtcItem, etc.)
```

---

## Dependencias principales

| Librería | Uso |
|---------|-----|
| `react-native-bluetooth-classic` | Bluetooth SPP/RFCOMM |
| `react-native-svg` | Gauges SVG |
| `react-native-chart-kit` | Gráficas históricas |
| `@react-navigation/native-stack` | Navegación entre pantallas |
