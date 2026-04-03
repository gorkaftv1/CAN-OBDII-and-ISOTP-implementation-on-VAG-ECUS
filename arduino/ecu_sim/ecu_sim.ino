/*
  Simulador ECU - SEAT Ibiza 6J 2012
  
  Este código simula el comportamiento de una ECU de motor para un SEAT Ibiza 6J 2012
  Compatible con Arduino MKR con CAN Shield
  
  Características:
  - Responde a peticiones OBD-II estándar (Modo 01, 03, 04, 09)
  - Simula parámetros realistas del motor
  - Genera DTCs de ejemplo
  - Compatible con Raspberry Pi 4 con CAN HAT
  
  ============================================================
  CAMBIOS ISO-TP (ISO 15765-2) — v2.0
  ============================================================
  
  1. RECEPCIÓN — Single Frame con PCI
     ─────────────────────────────────
     Antes: data[0]=Modo, data[1]=PID (raw, sin capa de transporte)
     Ahora: processCANMessages() lee el byte PCI (data[0]):
       - Nibble alto 0x0 → Single Frame (SF)
       - Nibble bajo    → longitud del payload (N bytes)
       - data[1]        → Modo OBD-II
       - data[2]        → PID OBD-II
     Tramas cuyo PCI no sea SF (FF/CF/FC entrantes) se ignoran
     en esta implementación porque los escáneres estándar sólo
     envían SFs en sus peticiones.
  
  2. ENVÍO — Single Frame con padding 0xAA
     ──────────────────────────────────────
     Antes: sendResponse() volcaba responseBuffer tal cual,
            sin PCI y con longitud variable (sin padding).
     Ahora: sendResponse() construye una trama CAN de exactamente
            8 bytes con el formato:
              Byte 0   : PCI = 0x0N  (N = responseLength, máx 7)
              Bytes 1…N: payload (responseBuffer[0..N-1])
              Bytes N+1…7: 0xAA (padding ISO-TP estándar)
     sendNegativeResponse() aplica el mismo esquema:
            [0x03, 0x7F, mode, errorCode, 0xAA, 0xAA, 0xAA, 0xAA]
  
  3. MODO 09 VIN — Segmentación Multi-Frame
     ─────────────────────────────────────────
     El VIN tiene 17 chars. El payload de respuesta es:
       [0x49, 0x02, 0x01, V, S, S, Z, Z, Z, 6, J, Z, C, R, 1, 2, 3, 4, 5, 6]
       ↑ 3 bytes cabecera OBD-II  +  17 bytes VIN  = 20 bytes en total.
     20 bytes no caben en un SF (máx 7), por lo que se usa segmentación:
  
     a) First Frame (FF):
          [0x10, 0x14, payload[0..5]]
           ↑                ↑ los 6 primeros bytes del payload
           └ 0x1H 0xLL → longitud total = 0x0014 = 20 dec
  
     b) Espera del Flow Control (FC) del escáner:
          waitForFlowControl() hace polling del bus CAN durante
          ISOTP_FC_TIMEOUT_MS ms. Si recibe una trama con
          PCI nibble = 0x3 (FC), continúa. Si se agota el timeout
          emite un WARNING por serie y continúa igualmente
          (comportamiento tolerante, útil en banco de pruebas).
  
     c) Consecutive Frames (CF):
          CF1: [0x21, payload[6..12]]   ← SN=1
          CF2: [0x22, payload[13..19]]  ← SN=2 (+ padding 0xAA al final)
          Entre CFs se respeta ISOTP_CF_SEP_MS de separación.
          El número de secuencia sigue el ciclo 1→2→…→F→0→1→…
  
  Autor: Simulador ECU VAG
  Fecha: 2025
*/

#include <CAN.h>
#include "ECU_protocol.h"
#include "serial_commands.h"

// ---------- VARIABLES GLOBALES ----------
VehicleData vehicle;
DTC dtcList[8];
uint8_t numStoredDTCs = 0;

// Estado de simulación
unsigned long lastUpdate = 0;
unsigned long engineStartTime = 0;
bool engineRunning = false;

// Botón de arranque (interrupt)
volatile bool ignitionPressed = false;  // Seteado en ISR, consumido en loop()
unsigned long lastDebounceTime = 0;     // Timestamp del último flanco válido (ms)
bool keyOn = false;                     // Estado actual del contacto (true = ON)

// Buffer de respuesta — almacena ÚNICAMENTE el payload OBD-II
// (sin PCI). sendResponse() añade el PCI y el padding.
uint8_t responseBuffer[7];   // máx 7 bytes: límite de payload en un SF ISO-TP
uint8_t responseLength = 0;

// ---------- VARIABLES DE CONTROL RUNTIME ----------
bool     canNoiseEnabled  = false;               // Ruido CAN bus (activar con NOISE 1)
uint16_t updateInterval   = SIM_UPDATE_INTERVAL_DEFAULT; // Intervalo simulación (ms)
ScenarioState activeScenario = SCENARIO_NONE;    // Escenario de conducción activo
SerialCmdContext serialCtx;                       // Contexto del parser serial

// ---------- PROTOTIPOS PRIVADOS ----------
void     handleIgnitionButton();
void     generateBackgroundTraffic();
void     sendResponse();
void     sendNegativeResponse(uint8_t mode, uint8_t errorCode);
void     sendVINMultiFrame();
bool     waitForFlowControl();
void     logCANFrame(const char* tag, uint32_t id, const uint8_t* data, uint8_t len);

// ---------- ISR: BOTÓN DE ARRANQUE ----------
// Mínima: sólo activa el flag. Nada de Serial, delay ni CAN aquí.
void onIgnitionButton() {
  ignitionPressed = true;
}

// ---------- GESTIÓN DEL BOTÓN (DEBOUNCE + LÓGICA) ----------
/*
  Llamada al principio de cada loop(). Comprueba la bandera seteada por la ISR,
  aplica el debounce de IGNITION_DEBOUNCE_MS ms y alterna el estado keyOn.
  Cuando keyOn pasa a true se establece vehicle.rpm = 850 (ralentí de arranque);
  cuando pasa a false se pone vehicle.rpm = 0.
  La función updateVehicleSimulation() detecta ese cambio de RPM y actualiza
  engineRunning correctamente (lógica existente sin modificar).
*/
void handleIgnitionButton() {
  if (!ignitionPressed) return;
  ignitionPressed = false;  // consumir bandera cuanto antes

  unsigned long now = millis();
  if (now - lastDebounceTime < IGNITION_DEBOUNCE_MS) return;  // rebote
  lastDebounceTime = now;

  keyOn = !keyOn;

  if (keyOn) {
    vehicle.rpm = 850;  // arranque → ralentí
    Serial.println(F("[IGN] Contacto ON  — motor arrancando (850 RPM)"));
  } else {
    vehicle.rpm = 0;    // apagado
    Serial.println(F("[IGN] Contacto OFF — motor apagado"));
  }
}

// ---------- SETUP ----------
void setup() {
  Serial.begin(SERIAL_BAUDRATE);
  while (!Serial) { ; }

  Serial.println(F("==========================================="));
  Serial.println(F("  SIMULADOR ECU - SEAT Ibiza 6J 2012"));
  Serial.println(F("       ISO-TP (ISO 15765-2) v2.0"));
  Serial.println(F("==========================================="));
  
  // Inicializar CAN Bus
  if (!CAN.begin(CAN_SPEED)) {
    Serial.println(F("[ERROR]: No se pudo iniciar CAN Bus"));
    Serial.println(F("Verifica las conexiones del CAN Shield"));
    while (1) delay(1000);
  }
  
  Serial.print(F("[OK] CAN Bus inicializado a "));
  Serial.print(CAN_SPEED / 1000);
  Serial.println(F(" kbps"));
  
  // Inicializar datos del vehículo
  initVehicleData();

  // Inicializar DTCs de ejemplo
  initDTCs();

  // Inicializar contexto del parser de comandos serial
  initSerialCmdContext(&serialCtx);

  // Configurar botón de arranque con interrupción hardware
  // El botón conecta D7 a GND: flanco FALLING = pulsación
  pinMode(ENGINE_START_PIN, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(ENGINE_START_PIN),
                  onIgnitionButton, FALLING);
  Serial.print(F("[OK] Botón arranque configurado en pin D"));
  Serial.println(ENGINE_START_PIN);

  Serial.println(F("\n[INFO] ECU lista para recibir comandos"));
  Serial.println(F("[INFO] Comandos serial: THR|SPD|IGN|DTC ADD|DTC CLR|STATUS|RATE|NOISE|SCENARIO"));
  Serial.print(F("[INFO] VIN: "));
  Serial.println(vehicle.vin);
  Serial.print(F("[INFO] Escuchando en ID: 0x"));
  Serial.println(ECU_CAN_ID, HEX);
  Serial.print(F("[INFO] Respondiendo en ID: 0x"));
  Serial.println(ECU_RESPONSE_ID, HEX);
  Serial.println(F("===========================================\n"));
}

// ---------- LOOP PRINCIPAL ----------
void loop() {
  // 1. Procesar el botón de arranque
  handleIgnitionButton();

  // 2. Procesar comandos serial (PC/RPi → Arduino)
  processSerialCommands(&serialCtx, &vehicle, dtcList, &numStoredDTCs,
                        &keyOn, &canNoiseEnabled, &updateInterval, &activeScenario);

  // 3. Actualizar simulación de datos del vehículo
  updateVehicleSimulation();

  // 4. Inyectar tráfico CAN de fondo (si ruido activo)
  generateBackgroundTraffic();

  // 5. Procesar mensajes CAN entrantes
  processCANMessages();

  // Pequeño delay para no saturar el bus
  delay(10);
}

// ---------- INICIALIZACIÓN ----------

void initVehicleData() {
  // VIN típico SEAT Ibiza (17 caracteres)
  strcpy(vehicle.vin, "VSSZZZ6JZDR040608");
  
  vehicle.engineType = ENGINE_TYPE_MPI;  // 1.4 MPI (BXW)
  vehicle.odometer = 40608;   // km aproximados según bastidor DR=2013
  
  // Valores iniciales (motor apagado)
  vehicle.engineLoad = 0;
  vehicle.coolantTemp = 20;  // Temperatura ambiente
  vehicle.rpm = 0;
  vehicle.speed = 0;
  vehicle.timingAdvance = 0;
  vehicle.intakeTemp = 20;
  vehicle.mafFlow = 0;
  vehicle.throttlePos = 0;
  vehicle.fuelLevel = 70;      // 70% — valor neutro de prueba
  vehicle.fuelRailPressure = 0;
  vehicle.batteryVoltage = 12450;    // 12.45V — batería en reposo
  vehicle.oilTemp = 20;
  vehicle.ambientTemp = 22;          // Las Palmas de GC, temperatura media
  vehicle.barometricPressure = 101;  // kPa — nivel del mar (Las Palmas)
  
  vehicle.checkEngine = false;
  vehicle.numDTCs = 0;
  vehicle.runtimeSinceStart = 0;
  vehicle.distanceSinceClear = 1500;  // 1500 km desde último borrado
  
  vehicle.shortFuelTrim1 = 2;   // +2%
  vehicle.longFuelTrim1 = -1;   // -1%
  
  engineRunning = false;
  engineStartTime = 0;
}

void initDTCs() {
  // Inicializar sin códigos de error
  for (int i = 0; i < 8; i++) {
    dtcList[i].code = DTC_P0000;
    dtcList[i].active = false;
  }
  
  // Añadir algunos DTCs de ejemplo (descomentarlos para simular errores)
  dtcList[0].code = DTC_P0171;
  dtcList[0].active = true;
  numStoredDTCs = 1;
  vehicle.checkEngine = true;
  vehicle.numDTCs = 1;
}

// ---------- SIMULACIÓN DE DATOS ----------
/*
  updateVehicleSimulation() — llama a:
    1. advanceScenario()  → ajusta throttlePos según el escenario activo
    2. Dinámica throttle→RPM (lag primer orden, tau≈0.3 pasos)
    3. Dinámica RPM→Speed (modelo longitudinal simplificado)
    4. Resto de parámetros correlacionados (load, MAF, timing…)
    5. Ruido de sensor (mismos NOISE_*_MAX que antes)
    6. Clamps físicos

  Intervalo de actualización: variable 'updateInterval' (default 200ms).
*/

void updateVehicleSimulation() {
  static unsigned long lastSimUpdate = 0;
  unsigned long currentTime = millis();

  if (currentTime - lastSimUpdate < updateInterval) return;
  uint16_t dtMs = (uint16_t)(currentTime - lastSimUpdate);  // tiempo real transcurrido
  lastSimUpdate = currentTime;
  lastUpdate    = currentTime;  // compatibilidad con código existente

  // ── 1. Avance del escenario de conducción ──────────────────────────
  advanceScenario(&activeScenario, &vehicle, dtMs);

  // ── 2. Detectar estado motor ───────────────────────────────────────
  if (vehicle.rpm > 0 && !engineRunning) {
    engineRunning = true;
    engineStartTime = currentTime;
    Serial.println(F("[SIM] Motor arrancado"));
  } else if (vehicle.rpm == 0 && engineRunning) {
    engineRunning = false;
    Serial.println(F("[SIM] Motor apagado"));
  }

  if (engineRunning) {
    // ── 3. Dinámica Throttle → RPM (lag primer orden) ────────────────
    // tau ≈ 0.3 × (updateInterval/200ms) para mantener la misma respuesta
    // temporal independientemente del intervalo configurado.
    int16_t targetRpm = (int16_t)map(vehicle.throttlePos, 0, 100, 850, 5500);
    float alpha = 0.3f * ((float)dtMs / 200.0f);
    if (alpha > 1.0f) alpha = 1.0f;
    vehicle.rpm = (uint16_t)(vehicle.rpm + alpha * (targetRpm - (int16_t)vehicle.rpm));

    // ── 4. Dinámica RPM → Speed (modelo longitudinal simplificado) ───
    // Fuerza motriz proporcional a RPM y load; resistencia proporcional a v².
    // Coeficientes empíricos para velocidad máxima ~160 km/h a plena carga.
    // fuerza_neta [un/paso] = k_traccion*(rpm*load/100) - k_resistencia*v²
    float force = 0.00002f * (float)vehicle.rpm * (float)vehicle.engineLoad
                - 0.003f   * (float)vehicle.speed * (float)vehicle.speed;
    // Escalar por dt para independencia del intervalo (referencia: 200ms)
    force *= ((float)dtMs / 200.0f);
    int16_t newSpeed = (int16_t)vehicle.speed + (int16_t)force;
    vehicle.speed = (uint8_t)constrain(newSpeed, 0, 180);

    // ── 5. Parámetros correlacionados ─────────────────────────────────
    vehicle.engineLoad    = (uint8_t)map(vehicle.throttlePos, 0, 100, 15, 85);
    vehicle.mafFlow       = (uint16_t)((vehicle.rpm * vehicle.engineLoad) / 500);
    vehicle.timingAdvance = (int8_t)map(vehicle.rpm, 800, 6000, 8, 32);
    vehicle.fuelRailPressure = 30;  // MPI: 300 kPa regulada, constante

    // Calentamiento motor
    if (vehicle.coolantTemp < 90) {
      vehicle.coolantTemp += random(1, 4);
      if (vehicle.coolantTemp > 90) vehicle.coolantTemp = 90;
    }
    if (vehicle.oilTemp < 95) {
      vehicle.oilTemp += random(1, 3);
      if (vehicle.oilTemp > 95) vehicle.oilTemp = 95;
    }
    if (vehicle.intakeTemp < vehicle.ambientTemp + 15) {
      vehicle.intakeTemp++;
    }

    // Alternador
    if (vehicle.batteryVoltage < 13800) {
      vehicle.batteryVoltage += 50;
    }

    // Consumo combustible (decrece lentamente con carga)
    // ~1% cada 30 pasos a plena carga; a ralentí apenas consume
    static uint8_t fuelTick = 0;
    if (++fuelTick >= (uint8_t)(30 - vehicle.engineLoad / 5)) {
      fuelTick = 0;
      if (vehicle.fuelLevel > 0) vehicle.fuelLevel--;
    }

    // Tiempo de funcionamiento
    vehicle.runtimeSinceStart = (currentTime - engineStartTime) / 1000;

    // ── 6. Ruido de sensor ────────────────────────────────────────────
    vehicle.rpm            += random(-NOISE_RPM_MAX,       NOISE_RPM_MAX + 1);
    vehicle.coolantTemp    += random(-NOISE_COOLANT_MAX,   NOISE_COOLANT_MAX + 1);
    vehicle.oilTemp        += random(-NOISE_OIL_MAX,       NOISE_OIL_MAX + 1);
    vehicle.intakeTemp     += random(-NOISE_INTAKE_MAX,    NOISE_INTAKE_MAX + 1);
    vehicle.mafFlow        += random(-NOISE_MAF_MAX,       NOISE_MAF_MAX + 1);
    vehicle.batteryVoltage += random(-NOISE_VOLTAGE_MAX,   NOISE_VOLTAGE_MAX + 1);
    vehicle.shortFuelTrim1 += random(-NOISE_FUEL_TRIM_MAX, NOISE_FUEL_TRIM_MAX + 1);

    // ── 7. Clamps físicos ─────────────────────────────────────────────
    vehicle.rpm            = constrain(vehicle.rpm,            750,  6500);
    vehicle.coolantTemp    = constrain(vehicle.coolantTemp,    -40,   130);
    vehicle.oilTemp        = constrain(vehicle.oilTemp,        -40,   150);
    vehicle.intakeTemp     = constrain(vehicle.intakeTemp,     -40,    80);
    vehicle.batteryVoltage = constrain(vehicle.batteryVoltage, 13800, 14400);
    vehicle.throttlePos    = constrain(vehicle.throttlePos,    0,    100);
    vehicle.shortFuelTrim1 = constrain(vehicle.shortFuelTrim1, -100,  99);
    if ((int16_t)vehicle.mafFlow < 0) vehicle.mafFlow = 0;

  } else {
    // Motor apagado
    vehicle.runtimeSinceStart = 0;
    vehicle.rpm               = 0;
    vehicle.engineLoad        = 0;
    vehicle.mafFlow           = 0;
    vehicle.fuelRailPressure  = 0;
    vehicle.timingAdvance     = 0;

    // Deceleración cuando motor apagado (freno rodadura)
    if (vehicle.speed > 0) {
      vehicle.speed = (uint8_t)constrain((int16_t)vehicle.speed - 2, 0, 255);
    }

    // Enfriamiento lento
    if (vehicle.coolantTemp > vehicle.ambientTemp) {
      vehicle.coolantTemp -= random(0, 2);
    }
    if (vehicle.oilTemp > vehicle.ambientTemp) {
      vehicle.oilTemp -= random(0, 2);
    }
    if (vehicle.intakeTemp > vehicle.ambientTemp) {
      vehicle.intakeTemp--;
    }

    // Bajada gradual al voltaje de batería en reposo (~12.45V)
    if (vehicle.batteryVoltage > 12600) {
      vehicle.batteryVoltage -= 20;
    }
    vehicle.batteryVoltage = constrain(vehicle.batteryVoltage, 12200, 12600);
  }
}

// ---------- TRÁFICO CAN DE FONDO ----------
/*
  Inyecta tramas CAN de otras ECUs del bus VAG PQ25 para simular
  el tráfico real que un escáner vería al conectarse al vehículo.
  Solo actúa cuando canNoiseEnabled == true.
  Probabilidad: CAN_NOISE_BG_TRAFFIC_PCT % de los ciclos de loop().
*/
void generateBackgroundTraffic() {
  if (!canNoiseEnabled) return;
  if (random(0, 100) >= CAN_NOISE_BG_TRAFFIC_PCT) return;

  uint8_t  idx  = (uint8_t)random(0, CAN_BG_ID_COUNT);
  uint32_t bgId = CAN_BG_IDS[idx];

  uint8_t frame[8];
  for (uint8_t i = 0; i < 8; i++) {
    frame[i] = (uint8_t)random(0, 256);
  }

  CAN.beginPacket(bgId);
  CAN.write(frame, 8);
  CAN.endPacket();
}

// ---------- PROCESAMIENTO CAN (ISO-TP) ----------
/*
  Estructura de una petición OBD-II con ISO-TP Single Frame:
  ┌────────┬──────────────────────────────────────────────┐
  │ Byte 0 │ PCI: 0x0N  (nibble alto=0→SF, bajo=N=longitud│
  │ Byte 1 │ Modo OBD-II (ej. 0x01, 0x03, 0x09…)          │
  │ Byte 2 │ PID  (si el modo lo requiere)                 │
  │ 3…7   │ 0x00 / 0x55 / 0xAA (padding del escáner)      │
  └────────┴──────────────────────────────────────────────┘
*/
void processCANMessages() {
  int packetSize = CAN.parsePacket();
  if (packetSize <= 0) return;
  
  uint32_t id = CAN.packetId();
  
  // Solo procesar mensajes dirigidos a esta ECU
  if (id != ECU_CAN_ID) return;
  
  // Leer datos crudos
  uint8_t data[8];
  uint8_t dataLen = 0;
  while (CAN.available() && dataLen < 8) {
    data[dataLen++] = (uint8_t)CAN.read();
  }
  
  if (dataLen < 1) return;

  // ── Decodificar byte PCI ──────────────────────────────────────────
  uint8_t pciType   = (data[0] & 0xF0);   // nibble alto × 16
  uint8_t pciLength = (data[0] & 0x0F);   // nibble bajo = N bytes de payload

  // Solo aceptamos Single Frames (PCI nibble alto = 0x00).
  // Un escáner OBD-II estándar SIEMPRE usa SF para sus peticiones.
  if (pciType != ISOTP_PCI_SF) {
    Serial.print(F("[WARN] PCI no SF recibido (0x"));
    Serial.print(data[0], HEX);
    Serial.println(F("), ignorado"));
    return;
  }

  // Necesitamos al menos PCI + Modo (+ PID para modos que lo requieran)
  if (pciLength < 1 || dataLen < 2) {
      Serial.println(F("[WARN] SF demasiado corto, ignorado"));
      return;
  }

  // ── Extraer Modo y PID desde posición ISO-TP ─────────────────────
  //    Antes: mode=data[0], pid=data[1]
  //    Ahora: mode=data[1], pid=data[2]  (data[0] es el PCI)
  uint8_t mode = data[1];
  uint8_t pid  = data[2];

  Serial.print(F("\n[RX] CAN ID: 0x"));
  Serial.print(id, HEX);
  Serial.print(F(" | PCI: 0x0"));
  Serial.print(pciLength, HEX);
  Serial.print(F(" | Mode: 0x"));
  Serial.print(mode, HEX);
  Serial.print(F(" | PID: 0x"));
  Serial.println(pid, HEX);

  // ── Ruido CAN bus: simula condiciones reales del bus ────────────────
  if (canNoiseEnabled) {
    // 1. Latencia de respuesta variable (jitter ECU real)
    delay(random(CAN_NOISE_LATENCY_MIN_MS, CAN_NOISE_LATENCY_MAX_MS + 1));

    // 2. Drop aleatorio: no enviar nada (~2%) → timeout en escáner
    if (random(0, 100) < CAN_NOISE_DROP_PCT) {
      Serial.println(F("[NOISE] Respuesta dropped (simulacion timeout)"));
      return;
    }

    // 3. NRC esporádico: condiciones no correctas (~1%)
    if (random(0, 100) < CAN_NOISE_NRC_PCT) {
      Serial.println(F("[NOISE] NRC 0x22 inyectado"));
      sendNegativeResponse(mode, NRC_CONDITIONS_NOT_CORRECT);
      return;
    }
  }

  // ── Despachar por modo ────────────────────────────────────────────
  bool handled = false;
  
  switch (mode) {
    case MODE_01_CURRENT_DATA:
      handled = handleMode01(pid);
      break;
      
    case MODE_03_DTCS:
      handled = handleMode03();
      break;
      
    case MODE_04_CLEAR_DTCS:
      handled = handleMode04();
      break;
      
    case MODE_09_VEHICLE_INFO:
      handled = handleMode09(pid);
      break;
      
    default:
      sendNegativeResponse(mode, NRC_SERVICE_NOT_SUPPORTED);
      handled = true;
      break;
  }
  
  if (!handled) {
    sendNegativeResponse(mode, NRC_SUBFUNCTION_NOT_SUPP);
  }
}

// ---------- MODO 01: DATOS EN TIEMPO REAL ----------

bool handleMode01(uint8_t pid) {
  responseLength = 0;
  
  switch (pid) {
    case PID_SUPPORTED_01_20:
      // Payload: [0x41, 0x00, b1, b2, b3, b4]  → 6 bytes → PCI = 0x06
      responseBuffer[0] = MODE_01_CURRENT_DATA + RESPONSE_SUCCESS;
      responseBuffer[1] = pid;
      responseBuffer[2] = 0xBE;
      responseBuffer[3] = 0x1F;
      responseBuffer[4] = 0xA8;
      responseBuffer[5] = 0x13;
      responseLength = 6;
      break;
      
    case PID_ENGINE_LOAD:
      // Payload: [0x41, 0x04, valor]  → 3 bytes → PCI = 0x03
      responseBuffer[0] = MODE_01_CURRENT_DATA + RESPONSE_SUCCESS;
      responseBuffer[1] = pid;
      responseBuffer[2] = encodePercent(vehicle.engineLoad);
      responseLength = 3;
      break;
      
    case PID_COOLANT_TEMP:
      responseBuffer[0] = MODE_01_CURRENT_DATA + RESPONSE_SUCCESS;
      responseBuffer[1] = pid;
      responseBuffer[2] = encodeTemp(vehicle.coolantTemp);
      responseLength = 3;
      break;
      
    case PID_ENGINE_RPM:
      // Payload: [0x41, 0x0C, RPM_H, RPM_L]  → 4 bytes → PCI = 0x04
      responseBuffer[0] = MODE_01_CURRENT_DATA + RESPONSE_SUCCESS;
      responseBuffer[1] = pid;
      encodeRPM(&responseBuffer[2], vehicle.rpm);
      responseLength = 4;
      break;
      
    case PID_VEHICLE_SPEED:
      responseBuffer[0] = MODE_01_CURRENT_DATA + RESPONSE_SUCCESS;
      responseBuffer[1] = pid;
      responseBuffer[2] = vehicle.speed;
      responseLength = 3;
      break;
      
    case PID_TIMING_ADVANCE:
      responseBuffer[0] = MODE_01_CURRENT_DATA + RESPONSE_SUCCESS;
      responseBuffer[1] = pid;
      responseBuffer[2] = (uint8_t)((vehicle.timingAdvance + 64) * 2);
      responseLength = 3;
      break;
      
    case PID_INTAKE_TEMP:
      responseBuffer[0] = MODE_01_CURRENT_DATA + RESPONSE_SUCCESS;
      responseBuffer[1] = pid;
      responseBuffer[2] = encodeTemp(vehicle.intakeTemp);
      responseLength = 3;
      break;
      
    case PID_MAF_FLOW:
      responseBuffer[0] = MODE_01_CURRENT_DATA + RESPONSE_SUCCESS;
      responseBuffer[1] = pid;
      responseBuffer[2] = (vehicle.mafFlow >> 8) & 0xFF;
      responseBuffer[3] = vehicle.mafFlow & 0xFF;
      responseLength = 4;
      break;
      
    case PID_THROTTLE_POS:
      responseBuffer[0] = MODE_01_CURRENT_DATA + RESPONSE_SUCCESS;
      responseBuffer[1] = pid;
      responseBuffer[2] = encodePercent(vehicle.throttlePos);
      responseLength = 3;
      break;
      
    case PID_RUNTIME_START:
      responseBuffer[0] = MODE_01_CURRENT_DATA + RESPONSE_SUCCESS;
      responseBuffer[1] = pid;
      responseBuffer[2] = (vehicle.runtimeSinceStart >> 8) & 0xFF;
      responseBuffer[3] = vehicle.runtimeSinceStart & 0xFF;
      responseLength = 4;
      break;
      
    case PID_FUEL_LEVEL:
      responseBuffer[0] = MODE_01_CURRENT_DATA + RESPONSE_SUCCESS;
      responseBuffer[1] = pid;
      responseBuffer[2] = encodePercent(vehicle.fuelLevel);
      responseLength = 3;
      break;
      
    case PID_DISTANCE_CLEAR:
      responseBuffer[0] = MODE_01_CURRENT_DATA + RESPONSE_SUCCESS;
      responseBuffer[1] = pid;
      responseBuffer[2] = (vehicle.distanceSinceClear >> 8) & 0xFF;
      responseBuffer[3] = vehicle.distanceSinceClear & 0xFF;
      responseLength = 4;
      break;
      
    case PID_BAROMETRIC_PRESSURE:
      responseBuffer[0] = MODE_01_CURRENT_DATA + RESPONSE_SUCCESS;
      responseBuffer[1] = pid;
      responseBuffer[2] = vehicle.barometricPressure;
      responseLength = 3;
      break;
      
    case PID_CONTROL_MODULE_VOLTAGE:
      responseBuffer[0] = MODE_01_CURRENT_DATA + RESPONSE_SUCCESS;
      responseBuffer[1] = pid;
      responseBuffer[2] = (vehicle.batteryVoltage >> 8) & 0xFF;
      responseBuffer[3] = vehicle.batteryVoltage & 0xFF;
      responseLength = 4;
      break;
      
    case PID_AMBIENT_TEMP:
      responseBuffer[0] = MODE_01_CURRENT_DATA + RESPONSE_SUCCESS;
      responseBuffer[1] = pid;
      responseBuffer[2] = encodeTemp(vehicle.ambientTemp);
      responseLength = 3;
      break;
      
    case PID_ENGINE_OIL_TEMP:
      responseBuffer[0] = MODE_01_CURRENT_DATA + RESPONSE_SUCCESS;
      responseBuffer[1] = pid;
      responseBuffer[2] = encodeTemp(vehicle.oilTemp);
      responseLength = 3;
      break;
      
    case PID_SHORT_FUEL_TRIM_1:
      responseBuffer[0] = MODE_01_CURRENT_DATA + RESPONSE_SUCCESS;
      responseBuffer[1] = pid;
      encodeFuelTrim(&responseBuffer[2], vehicle.shortFuelTrim1);
      responseLength = 3;
      break;
      
    case PID_LONG_FUEL_TRIM_1:
      responseBuffer[0] = MODE_01_CURRENT_DATA + RESPONSE_SUCCESS;
      responseBuffer[1] = pid;
      encodeFuelTrim(&responseBuffer[2], vehicle.longFuelTrim1);
      responseLength = 3;
      break;
      
    case PID_FUEL_RAIL_PRESSURE:
      responseBuffer[0] = MODE_01_CURRENT_DATA + RESPONSE_SUCCESS;
      responseBuffer[1] = pid;
      responseBuffer[2] = (vehicle.fuelRailPressure >> 8) & 0xFF;
      responseBuffer[3] = vehicle.fuelRailPressure & 0xFF;
      responseLength = 4;
      break;
      
    default:
      return false;  // PID no soportado
  }
  
  if (responseLength > 0) {
    sendResponse();
    return true;
  }
  
  return false;
}

// ---------- MODO 03: LEER DTCs ----------
/*
  NOTA ISO-TP: Con ≤ 2 DTCs activos el payload cabe en un SF (máx 7 bytes).
  Si se activan más de 2 DTCs simultáneamente se necesitaría segmentación
  multi-frame (no implementada para este modo; ampliar con sendMultiFrameRaw
  si se requiere).
  
  Formato payload SF: [0x43, numDTC, DTC1_H, DTC1_L, DTC2_H, DTC2_L]
                        → máx 6 bytes → PCI = 0x06  ✓
*/
bool handleMode03() {
  responseBuffer[0] = MODE_03_DTCS + RESPONSE_SUCCESS;  // 0x43
  responseBuffer[1] = numStoredDTCs;
  responseLength = 2;
  
  // Limitamos a 2 DTCs para no superar ISOTP_SF_MAX_PAYLOAD (7 bytes)
  uint8_t dtcsToSend = min(numStoredDTCs, (uint8_t)2);
  for (uint8_t i = 0; i < dtcsToSend; i++) {
    if (dtcList[i].active && responseLength <= ISOTP_SF_MAX_PAYLOAD - 2) {
      responseBuffer[responseLength++] = (dtcList[i].code >> 8) & 0xFF;
      responseBuffer[responseLength++] = dtcList[i].code & 0xFF;
    }
  }
  
  sendResponse();
  
  Serial.print(F("[INFO] Enviados "));
  Serial.print(dtcsToSend);
  Serial.println(F(" DTCs"));
  
  return true;
}

// ---------- MODO 04: BORRAR DTCs ----------

bool handleMode04() {
  for (int i = 0; i < 8; i++) {
    dtcList[i].code = DTC_P0000;
    dtcList[i].active = false;
  }
  
  numStoredDTCs = 0;
  vehicle.numDTCs = 0;
  vehicle.checkEngine = false;
  vehicle.distanceSinceClear = 0;
  
  // Payload: [0x44]  → 1 byte → PCI = 0x01
  responseBuffer[0] = MODE_04_CLEAR_DTCS + RESPONSE_SUCCESS;  // 0x44
  responseLength = 1;
  sendResponse();
  
  Serial.println(F("[INFO] DTCs borrados"));
  
  return true;
}

// ---------- MODO 09: INFORMACIÓN DEL VEHÍCULO (VIN Multi-Frame) ----------
/*
  El VIN completo (17 bytes) más la cabecera OBD-II (3 bytes) suman 20 bytes.
  Eso excede el máximo de un SF (7 bytes), por lo que se usa segmentación:

  ┌────────────────────────────────────────────────────────────────────┐
  │ FF  │ 10 14 │ 49 02 01 56 53 53  ← [0x49,0x02,0x01,'V','S','S']  │
  │ CF1 │ 21    │ 5A 5A 5A 36 4A 5A 43  ← 'Z','Z','Z','6','J','Z','C'│
  │ CF2 │ 22    │ 52 31 32 33 34 35 36  ← 'R','1','2','3','4','5','6' │
  └────────────────────────────────────────────────────────────────────┘
  Total payload transmitido: 6 + 7 + 7 = 20 bytes ✓
*/
bool handleMode09(uint8_t pid) {
  switch (pid) {
    case 0x02:  // VIN
      Serial.print(F("[INFO] VIN solicitado: "));
      Serial.println(vehicle.vin);
      sendVINMultiFrame();
      return true;
      
    default:
      return false;
  }
}

// ---------- ENVÍO ISO-TP: SINGLE FRAME CON PADDING ----------
/*
  Construye y envía una trama CAN de 8 bytes con formato ISO-TP SF:

    Byte 0    : PCI = 0x0N  (nibble bajo = responseLength)
    Bytes 1…N : payload (responseBuffer[0..responseLength-1])
    Bytes N+1…7: ISOTP_PADDING_BYTE (0xAA)

  Precondición: responseLength está entre 1 y ISOTP_SF_MAX_PAYLOAD (7).
*/
void sendResponse() {
  if (responseLength == 0) return;
  if (responseLength > ISOTP_SF_MAX_PAYLOAD) {
    // Nunca debería ocurrir si los handlers están bien, pero lo protegemos
    Serial.println(F("[ERROR] Payload supera límite SF (7 bytes)"));
    return;
  }

  // Construir trama de 8 bytes
  uint8_t frame[8];
  frame[0] = (uint8_t)responseLength;            // PCI: 0x0N
  for (uint8_t i = 0; i < responseLength; i++) {
    frame[1 + i] = responseBuffer[i];             // payload
  }
  for (uint8_t i = responseLength + 1; i < 8; i++) {
    frame[i] = ISOTP_PADDING_BYTE;                // padding 0xAA
  }

  CAN.beginPacket(ECU_RESPONSE_ID);
  for (uint8_t i = 0; i < 8; i++) {
    CAN.write(frame[i]);
  }
  CAN.endPacket();

  // Log
  Serial.print(F("[TX SF] 0x"));
  Serial.print(ECU_RESPONSE_ID, HEX);
  Serial.print(F(" | "));
  for (uint8_t i = 0; i < 8; i++) {
    if (frame[i] < 0x10) Serial.print(F("0"));
    Serial.print(frame[i], HEX);
    Serial.print(F(" "));
  }
  Serial.println();
}

// ---------- ENVÍO ISO-TP: RESPUESTA NEGATIVA CON PADDING ----------
/*
  Payload NRC = [0x7F, mode, errorCode]  → 3 bytes → PCI = 0x03

  Trama resultante:
    [0x03, 0x7F, mode, errorCode, 0xAA, 0xAA, 0xAA, 0xAA]
*/
void sendNegativeResponse(uint8_t mode, uint8_t errorCode) {
  uint8_t frame[8];
  frame[0] = 0x03;               // PCI: SF, 3 bytes de payload
  frame[1] = NEGATIVE_RESPONSE;  // 0x7F
  frame[2] = mode;
  frame[3] = errorCode;
  for (uint8_t i = 4; i < 8; i++) {
    frame[i] = ISOTP_PADDING_BYTE;
  }

  CAN.beginPacket(ECU_RESPONSE_ID);
  for (uint8_t i = 0; i < 8; i++) {
    CAN.write(frame[i]);
  }
  CAN.endPacket();

  Serial.print(F("[TX NRC] Mode=0x"));
  Serial.print(mode, HEX);
  Serial.print(F(" Error=0x"));
  Serial.println(errorCode, HEX);
}

// ---------- ENVÍO ISO-TP: VIN MULTI-FRAME ----------
/*
  Payload completo (20 bytes):
    [0x49, 0x02, 0x01, vin[0]…vin[16]]
     ↑ modo resp  ↑PID  ↑items  ↑──17 chars──

  Secuencia de tramas:
    FF  → [0x10, 0x14, payload[0..5]]
    (esperar FC del escáner)
    CF1 → [0x21,  payload[6..12]]
    CF2 → [0x22,  payload[13..19]]  + padding si sobra
*/
void sendVINMultiFrame() {
  // Construir payload completo
  const uint8_t PAYLOAD_LEN = 3 + VIN_LENGTH;  // 20 bytes
  uint8_t payload[20];
  payload[0] = MODE_09_VEHICLE_INFO + RESPONSE_SUCCESS;  // 0x49
  payload[1] = 0x02;                                     // PID VIN
  payload[2] = 0x01;                                     // número de items
  for (uint8_t i = 0; i < VIN_LENGTH; i++) {
    payload[3 + i] = (uint8_t)vehicle.vin[i];
  }

  // ── 1. Enviar First Frame ─────────────────────────────────────────
  //    Byte 0 : 0x10 | (PAYLOAD_LEN >> 8)  → 0x10 (payload < 256 bytes)
  //    Byte 1 : PAYLOAD_LEN & 0xFF          → 0x14 (20 decimal)
  //    Bytes 2-7: primeros 6 bytes del payload
  uint8_t ff[8];
  ff[0] = ISOTP_PCI_FF | ((PAYLOAD_LEN >> 8) & 0x0F);  // 0x10
  ff[1] = PAYLOAD_LEN & 0xFF;                            // 0x14
  for (uint8_t i = 0; i < ISOTP_FF_DATA_BYTES; i++) {
    ff[2 + i] = payload[i];
  }

  CAN.beginPacket(ECU_RESPONSE_ID);
  for (uint8_t i = 0; i < 8; i++) CAN.write(ff[i]);
  CAN.endPacket();

  Serial.print(F("[TX FF] 0x"));
  Serial.print(ECU_RESPONSE_ID, HEX);
  Serial.print(F(" | "));
  for (uint8_t i = 0; i < 8; i++) {
    if (ff[i] < 0x10) Serial.print(F("0"));
    Serial.print(ff[i], HEX);
    Serial.print(F(" "));
  }
  Serial.println();

  // ── 2. Esperar Flow Control del escáner ──────────────────────────
  //    El escáner debe responder con una trama FC (byte PCI = 0x3x)
  //    antes de que enviemos los Consecutive Frames.
  if (!waitForFlowControl()) {
    Serial.println(F("[WARN] Timeout FC: enviando CFs de todas formas"));
    // Continuamos de todos modos (comportamiento tolerante para banco de pruebas)
  }

  // ── 3. Enviar Consecutive Frames ─────────────────────────────────
  //    SN empieza en 1, incrementa módulo 16 (0x0…0xF → 0x0…)
  uint8_t bytesSent = ISOTP_FF_DATA_BYTES;   // ya enviamos los primeros 6
  uint8_t sn = 1;

  while (bytesSent < PAYLOAD_LEN) {
    uint8_t cf[8];
    cf[0] = ISOTP_PCI_CF | (sn & 0x0F);     // 0x21, 0x22, …

    for (uint8_t i = 0; i < ISOTP_CF_DATA_BYTES; i++) {
      uint8_t payloadIdx = bytesSent + i;
      cf[1 + i] = (payloadIdx < PAYLOAD_LEN)
                    ? payload[payloadIdx]
                    : ISOTP_PADDING_BYTE;    // padding si el último CF no es completo
    }

    CAN.beginPacket(ECU_RESPONSE_ID);
    for (uint8_t i = 0; i < 8; i++) CAN.write(cf[i]);
    CAN.endPacket();

    Serial.print(F("[TX CF] SN=0x"));
    Serial.print(sn & 0x0F, HEX);
    Serial.print(F(" | "));
    for (uint8_t i = 0; i < 8; i++) {
      if (cf[i] < 0x10) Serial.print(F("0"));
      Serial.print(cf[i], HEX);
      Serial.print(F(" "));
    }
    Serial.println();

    bytesSent += ISOTP_CF_DATA_BYTES;
    sn = (sn + 1) & 0x0F;           // wrapping: …E→F→0→1→…

    // Respetar tiempo de separación mínimo entre CFs (STmin)
    if (bytesSent < PAYLOAD_LEN) {
      delay(ISOTP_CF_SEP_MS);
    }
  }

  Serial.println(F("[INFO] VIN multi-frame completado"));
}

// ---------- ESPERA DE FLOW CONTROL ─────────────────────────────────
/*
  Hace polling del bus CAN durante ISOTP_FC_TIMEOUT_MS milisegundos.
  Devuelve true si recibe una trama FC válida (PCI nibble alto = 0x3)
  procedente del escáner (ECU_CAN_ID = 0x7E0).
  Devuelve false si se agota el timeout.

  La trama FC estándar tiene el formato:
    [0x30, BlockSize, STmin, 0x00, 0x00, 0x00, 0x00, 0x00]
     ↑ PCI: FC, ContinueToSend (flag=0)
*/
bool waitForFlowControl() {
  unsigned long deadline = millis() + ISOTP_FC_TIMEOUT_MS;

  Serial.println(F("[INFO] Esperando Flow Control…"));

  while (millis() < deadline) {
    int pktSize = CAN.parsePacket();
    if (pktSize > 0) {
      uint32_t rxId = CAN.packetId();

      // Leer primer byte (PCI) y descartar el resto
      uint8_t pci = (uint8_t)CAN.read();
      while (CAN.available()) CAN.read();  // vaciar buffer

      if (rxId == ECU_CAN_ID && (pci & 0xF0) == ISOTP_PCI_FC) {
        uint8_t fcFlag = pci & 0x0F;
        Serial.print(F("[RX FC] flag=0x"));
        Serial.println(fcFlag, HEX);
        return true;  // ContinueToSend (0x00) u otro flag: continuamos
      }
    }
  }

  return false;  // timeout
}
