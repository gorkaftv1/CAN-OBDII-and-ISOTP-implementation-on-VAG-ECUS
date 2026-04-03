// --------------------------------------------------------------------
// SERIAL COMMANDS — Simulador ECU SEAT Ibiza 6J 2012
//
// Permite controlar el simulador desde un PC/RPi por USB serial.
// Los comandos se envían como texto ASCII terminado en '\n'.
// El buffer máximo por comando es SERIAL_CMD_BUF_SIZE bytes.
//
// Comandos disponibles:
//   THR <0-100>           — Fijar posición del acelerador (%)
//   SPD <0-255>           — Override directo de velocidad (km/h)
//   IGN <1|0>             — Arrancar (1) o apagar (0) el motor
//   DTC ADD <hex4>        — Añadir DTC (ej: DTC ADD 0171)
//   DTC CLR               — Borrar todos los DTCs
//   STATUS                — Imprimir estado completo del vehículo
//   RATE <ms>             — Cambiar intervalo de actualización (ms)
//   NOISE <0|1>           — Desactivar (0) / activar (1) ruido CAN
//   SCENARIO <name>       — Ejecutar ciclo: idle | drive | city
// --------------------------------------------------------------------

#ifndef SERIAL_COMMANDS_H
#define SERIAL_COMMANDS_H

#include <Arduino.h>
#include "ECU_protocol.h"

// ---------- CONFIGURACIÓN ----------
#define SERIAL_CMD_BUF_SIZE   32   // Bytes máximos por comando (incluyendo '\0')
#define SERIAL_CMD_TIMEOUT_MS  5   // Tiempo máximo entre bytes de un mismo comando

// ---------- ESTADOS DEL ESCENARIO ----------
typedef enum {
  SCENARIO_NONE = 0,
  SCENARIO_IDLE,
  SCENARIO_DRIVE,
  SCENARIO_CITY
} ScenarioState;

// ---------- CONTEXTO DEL PARSER ----------
// Datos de estado que el sketch principal debe declarar como globales
// y pasar por puntero a processSerialCommands().
struct SerialCmdContext {
  char     buf[SERIAL_CMD_BUF_SIZE];  // Buffer acumulador
  uint8_t  len;                        // Bytes acumulados
  bool     overflow;                   // Línea demasiado larga (descartar)
};

// ---------- PROTOTIPOS ----------
void     initSerialCmdContext(SerialCmdContext* ctx);
void     processSerialCommands(SerialCmdContext* ctx,
                               VehicleData*     vehicle,
                               DTC*             dtcList,
                               uint8_t*         numStoredDTCs,
                               bool*            keyOn,
                               bool*            canNoiseEnabled,
                               uint16_t*        updateInterval,
                               ScenarioState*   scenario);

// ---------- IMPLEMENTACIÓN (inline para que todo esté en el .h) ----------

void initSerialCmdContext(SerialCmdContext* ctx) {
  ctx->len      = 0;
  ctx->overflow = false;
  memset(ctx->buf, 0, SERIAL_CMD_BUF_SIZE);
}

// Convierte string hex de 4 chars a uint16_t; devuelve 0xFFFF si inválido
static uint16_t _parseHex4(const char* s) {
  if (strlen(s) != 4) return 0xFFFF;
  char* end;
  long val = strtol(s, &end, 16);
  if (*end != '\0') return 0xFFFF;
  return (uint16_t)val;
}

// Ejecuta el comando ya acumulado en ctx->buf
static void _executeCommand(const char*    cmd,
                            VehicleData*   vehicle,
                            DTC*           dtcList,
                            uint8_t*       numStoredDTCs,
                            bool*          keyOn,
                            bool*          canNoiseEnabled,
                            uint16_t*      updateInterval,
                            ScenarioState* scenario) {

  // ── THR <0-100> ───────────────────────────────────────────────────
  if (strncmp(cmd, "THR ", 4) == 0) {
    int val = atoi(cmd + 4);
    val = constrain(val, 0, 100);
    vehicle->throttlePos = (uint8_t)val;
    Serial.print(F("[CMD] Throttle = "));
    Serial.print(val);
    Serial.println(F("%"));
    return;
  }

  // ── SPD <0-255> ───────────────────────────────────────────────────
  if (strncmp(cmd, "SPD ", 4) == 0) {
    int val = atoi(cmd + 4);
    val = constrain(val, 0, 255);
    vehicle->speed = (uint8_t)val;
    Serial.print(F("[CMD] Speed = "));
    Serial.print(val);
    Serial.println(F(" km/h"));
    return;
  }

  // ── IGN <1|0> ────────────────────────────────────────────────────
  if (strncmp(cmd, "IGN ", 4) == 0) {
    int val = atoi(cmd + 4);
    if (val == 1 && !(*keyOn)) {
      *keyOn = true;
      vehicle->rpm = 850;
      Serial.println(F("[CMD] Ignicion ON — motor arrancando"));
    } else if (val == 0 && *keyOn) {
      *keyOn = false;
      vehicle->rpm = 0;
      Serial.println(F("[CMD] Ignicion OFF — motor apagado"));
    }
    return;
  }

  // ── DTC ADD <hex4> ───────────────────────────────────────────────
  if (strncmp(cmd, "DTC ADD ", 8) == 0) {
    uint16_t code = _parseHex4(cmd + 8);
    if (code == 0xFFFF) {
      Serial.println(F("[CMD] Error: DTC ADD requiere 4 hex (ej: DTC ADD 0171)"));
      return;
    }
    if (*numStoredDTCs >= 8) {
      Serial.println(F("[CMD] Error: lista DTC llena (max 8)"));
      return;
    }
    // Buscar slot libre
    for (uint8_t i = 0; i < 8; i++) {
      if (!dtcList[i].active) {
        dtcList[i].code   = code;
        dtcList[i].active = true;
        (*numStoredDTCs)++;
        vehicle->numDTCs  = *numStoredDTCs;
        vehicle->checkEngine = true;
        Serial.print(F("[CMD] DTC P"));
        Serial.print(code, HEX);
        Serial.println(F(" añadido"));
        return;
      }
    }
    return;
  }

  // ── DTC CLR ──────────────────────────────────────────────────────
  if (strcmp(cmd, "DTC CLR") == 0) {
    for (uint8_t i = 0; i < 8; i++) {
      dtcList[i].code   = 0x0000;
      dtcList[i].active = false;
    }
    *numStoredDTCs       = 0;
    vehicle->numDTCs     = 0;
    vehicle->checkEngine = false;
    vehicle->distanceSinceClear = 0;
    Serial.println(F("[CMD] DTCs borrados"));
    return;
  }

  // ── STATUS ───────────────────────────────────────────────────────
  if (strcmp(cmd, "STATUS") == 0) {
    Serial.println(F("--- VEHICLE STATUS ---"));
    Serial.print(F("  RPM:        ")); Serial.println(vehicle->rpm);
    Serial.print(F("  Speed:      ")); Serial.print(vehicle->speed); Serial.println(F(" km/h"));
    Serial.print(F("  Throttle:   ")); Serial.print(vehicle->throttlePos); Serial.println(F("%"));
    Serial.print(F("  EngLoad:    ")); Serial.print(vehicle->engineLoad); Serial.println(F("%"));
    Serial.print(F("  Coolant:    ")); Serial.print(vehicle->coolantTemp); Serial.println(F(" C"));
    Serial.print(F("  OilTemp:    ")); Serial.print(vehicle->oilTemp); Serial.println(F(" C"));
    Serial.print(F("  MAF:        ")); Serial.print(vehicle->mafFlow); Serial.println(F(" raw"));
    Serial.print(F("  Battery:    ")); Serial.print(vehicle->batteryVoltage); Serial.println(F(" mV"));
    Serial.print(F("  FuelLevel:  ")); Serial.print(vehicle->fuelLevel); Serial.println(F("%"));
    Serial.print(F("  DTCs:       ")); Serial.println(*numStoredDTCs);
    Serial.print(F("  CheckEng:   ")); Serial.println(vehicle->checkEngine ? F("ON") : F("OFF"));
    Serial.print(F("  CAN Noise:  ")); Serial.println(*canNoiseEnabled ? F("ON") : F("OFF"));
    Serial.print(F("  UpdateRate: ")); Serial.print(*updateInterval); Serial.println(F(" ms"));
    Serial.println(F("----------------------"));
    return;
  }

  // ── RATE <ms> ────────────────────────────────────────────────────
  if (strncmp(cmd, "RATE ", 5) == 0) {
    int val = atoi(cmd + 5);
    if (val < 50 || val > 5000) {
      Serial.println(F("[CMD] Error: RATE debe estar entre 50 y 5000 ms"));
      return;
    }
    *updateInterval = (uint16_t)val;
    Serial.print(F("[CMD] Update rate = "));
    Serial.print(val);
    Serial.println(F(" ms"));
    return;
  }

  // ── NOISE <0|1> ──────────────────────────────────────────────────
  if (strncmp(cmd, "NOISE ", 6) == 0) {
    int val = atoi(cmd + 6);
    *canNoiseEnabled = (val != 0);
    Serial.print(F("[CMD] CAN noise = "));
    Serial.println(*canNoiseEnabled ? F("ON") : F("OFF"));
    return;
  }

  // ── SCENARIO <name> ──────────────────────────────────────────────
  if (strncmp(cmd, "SCENARIO ", 9) == 0) {
    const char* name = cmd + 9;
    if (strcmp(name, "idle") == 0) {
      *scenario = SCENARIO_IDLE;
      vehicle->throttlePos = 0;
      Serial.println(F("[CMD] Scenario: IDLE"));
    } else if (strcmp(name, "drive") == 0) {
      *scenario = SCENARIO_DRIVE;
      Serial.println(F("[CMD] Scenario: DRIVE (aceleracion sostenida)"));
    } else if (strcmp(name, "city") == 0) {
      *scenario = SCENARIO_CITY;
      Serial.println(F("[CMD] Scenario: CITY (stop & go urbano)"));
    } else {
      Serial.println(F("[CMD] Scenario desconocido. Usa: idle | drive | city"));
    }
    return;
  }

  // ── Comando desconocido ───────────────────────────────────────────
  Serial.print(F("[CMD] Desconocido: "));
  Serial.println(cmd);
  Serial.println(F("  Comandos: THR|SPD|IGN|DTC ADD|DTC CLR|STATUS|RATE|NOISE|SCENARIO"));
}

// ---------- FUNCIÓN PRINCIPAL (llamar cada loop()) ----------
/*
  Lee bytes de Serial acumulando en el buffer ctx->buf.
  Al recibir '\n' (o '\r') ejecuta el comando y limpia el buffer.
  Si la línea supera SERIAL_CMD_BUF_SIZE bytes la descarta silenciosamente.
*/
void processSerialCommands(SerialCmdContext* ctx,
                           VehicleData*     vehicle,
                           DTC*             dtcList,
                           uint8_t*         numStoredDTCs,
                           bool*            keyOn,
                           bool*            canNoiseEnabled,
                           uint16_t*        updateInterval,
                           ScenarioState*   scenario) {
  while (Serial.available()) {
    char c = (char)Serial.read();

    if (c == '\r') continue;  // ignorar CR

    if (c == '\n') {
      if (!ctx->overflow && ctx->len > 0) {
        ctx->buf[ctx->len] = '\0';
        // Convertir a mayúsculas para comparación case-insensitive
        for (uint8_t i = 0; i < ctx->len; i++) {
          if (ctx->buf[i] >= 'a' && ctx->buf[i] <= 'z') {
            ctx->buf[i] -= 32;
          }
        }
        _executeCommand(ctx->buf, vehicle, dtcList, numStoredDTCs,
                        keyOn, canNoiseEnabled, updateInterval, scenario);
      }
      ctx->len      = 0;
      ctx->overflow = false;
      memset(ctx->buf, 0, SERIAL_CMD_BUF_SIZE);
      return;  // procesar un comando por iteración de loop()
    }

    if (ctx->len >= SERIAL_CMD_BUF_SIZE - 1) {
      ctx->overflow = true;
    } else if (!ctx->overflow) {
      ctx->buf[ctx->len++] = c;
    }
  }
}

// ---------- AVANCE DE ESCENARIO (llamar en updateVehicleSimulation()) ----------
/*
  Actualiza vehicle->throttlePos según el escenario activo.
  Debe llamarse ANTES de aplicar la dinámica throttle→RPM.
  stepMs: tiempo transcurrido desde la última llamada (ms).
*/
void advanceScenario(ScenarioState* scenario, VehicleData* vehicle, uint16_t stepMs) {
  static uint32_t scenarioTime = 0;
  scenarioTime += stepMs;

  switch (*scenario) {
    case SCENARIO_IDLE:
      vehicle->throttlePos = 0;
      break;

    case SCENARIO_DRIVE: {
      // Aceleración suave hasta 80 km/h, crucero, freno
      // Fase basada en scenarioTime (ms):
      //   0-5000:   aceleración (throttle 0→60%)
      //   5000-15000: crucero (throttle 25%)
      //   15000-20000: frenada (throttle 0%)
      //   20000+:   idle y reiniciar
      uint32_t t = scenarioTime % 20000UL;
      if (t < 5000) {
        vehicle->throttlePos = (uint8_t)map(t, 0, 5000, 0, 60);
      } else if (t < 15000) {
        vehicle->throttlePos = 25;
      } else {
        vehicle->throttlePos = 0;
      }
      break;
    }

    case SCENARIO_CITY: {
      // Stop & go urbano: arranque→50km/h→freno→parada → repetir
      // Ciclo de 12s:
      //   0-3000:   acelerar (throttle 40%)
      //   3000-6000: crucero 50 km/h (throttle 15%)
      //   6000-9000: freno (throttle 0%)
      //   9000-12000: parada (idle)
      uint32_t t = scenarioTime % 12000UL;
      if (t < 3000) {
        vehicle->throttlePos = 40;
      } else if (t < 6000) {
        vehicle->throttlePos = 15;
      } else {
        vehicle->throttlePos = 0;
      }
      break;
    }

    case SCENARIO_NONE:
    default:
      break;
  }
}

#endif // SERIAL_COMMANDS_H
