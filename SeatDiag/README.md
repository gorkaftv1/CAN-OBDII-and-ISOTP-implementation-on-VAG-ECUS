# SeatDiag — App React Native

App móvil para Android que se conecta a la Raspberry Pi por Bluetooth Classic (SPP/RFCOMM) y muestra un dashboard de diagnóstico OBD-II en tiempo real para el SEAT Ibiza 6J 2012.

## Requisitos

- Node.js ≥ 18
- React Native CLI
- Android Studio + SDK
- Dispositivo/emulador Android con Bluetooth

## Instalación

```bash
npm install
npx react-native run-android
```

## Flujo de pantallas

```
ScanScreen       → Escanear dispositivos Bluetooth
ConnectingScreen → Conectar por RFCOMM a SEAT_DIAG_PI
DashboardScreen  → Dashboard con gauges en tiempo real
  ├── DtcScreen  → Leer y borrar códigos de error
  └── HistoryScreen → Historial de sesiones pasadas
        └── SessionDetailScreen → Gráficas temporales por PID
```

## Gauges

| Tipo de dato | Visualización |
|-------------|---------------|
| RPM | Arco SVG circular con gradiente verde→rojo |
| km/h | Número grande centrado |
| °C (temperaturas) | Barra vertical (termómetro) con gradiente azul→rojo |
| % (porcentajes) | Barra horizontal con color |

## Protocolo de comunicación

NDJSON sobre RFCOMM con el servidor Python de la Raspberry Pi. Ver [src/server/README.md](../src/server/README.md).

## Dependencias principales

| Librería | Uso |
|---------|-----|
| `react-native-bluetooth-classic` | Bluetooth SPP/RFCOMM |
| `react-native-svg` | Gauges SVG |
| `react-native-chart-kit` | Gráficas históricas |
| `@react-navigation/native-stack` | Navegación entre pantallas |
