// --------------------------------------------------------------------
// SIMULADOR ECU - SEAT Ibiza 6J 2012
// Protocolo basado en OBD-II y VAG Group específico
//
// [CAMBIOS ISO-TP v2.0]
//  - Añadida sección "ISO-TP (ISO 15765-2) Transport Layer"
//  - ISOTP_PADDING_BYTE  : byte de relleno para tramas de 8 bytes (0xAA)
//  - ISOTP_FC_TIMEOUT_MS : tiempo máximo esperando el Flow Control (ms)
//  - ISOTP_CF_SEP_MS     : separación mínima entre Consecutive Frames (ms)
//  - ISOTP_SF_MAX_PAYLOAD: payload máximo en un Single Frame (7 bytes)
//  - ISOTP_FF_DATA_BYTES : bytes de payload que caben en el First Frame (6 bytes)
//  - ISOTP_CF_DATA_BYTES : bytes de payload que caben en cada Consec. Frame (7 bytes)
// --------------------------------------------------------------------

#ifndef ECU_PROTOCOL_H
#define ECU_PROTOCOL_H

#include <Arduino.h>

// ---------- CONFIGURACIÓN CAN BUS ----------
#define CAN_SPEED          500E3  // 500 kbps (estándar para ECU VAG)
#define ECU_CAN_ID         0x7E0  // ID estándar OBD-II para peticiones ECU motor
#define ECU_RESPONSE_ID    0x7E8  // ID estándar OBD-II para respuestas ECU motor

// IDs adicionales para diferentes ECUs del vehículo
#define TCU_CAN_ID         0x7E1  // Transmisión
#define TCU_RESPONSE_ID    0x7E9  
#define ABS_CAN_ID         0x7E2  // ABS/ESP
#define ABS_RESPONSE_ID    0x7EA
#define AIRBAG_CAN_ID      0x7E3  // Airbag
#define AIRBAG_RESPONSE_ID 0x7EB

// ---------- ISO-TP (ISO 15765-2) Transport Layer ----------
// Tipos de PCI (Protocol Control Information) — nibble alto del byte 0
#define ISOTP_PCI_SF       0x00  // Single Frame     (0x0N, N = longitud payload)
#define ISOTP_PCI_FF       0x10  // First Frame      (0x1H 0xLL, H:L = longitud total)
#define ISOTP_PCI_CF       0x20  // Consecutive Frame(0x2N, N = número de secuencia)
#define ISOTP_PCI_FC       0x30  // Flow Control     (0x3F, F = flag: 0=CTS,1=Wait,2=Ovfl)

// Parámetros de temporización y tamaño
#define ISOTP_PADDING_BYTE   0xAA  // Byte de relleno hasta completar 8 bytes
#define ISOTP_FC_TIMEOUT_MS  1000  // Timeout esperando Flow Control del escáner (ms)
#define ISOTP_CF_SEP_MS      25    // Separación mínima entre Consecutive Frames (ms)
#define ISOTP_SF_MAX_PAYLOAD 7     // Payload máximo en un Single Frame
#define ISOTP_FF_DATA_BYTES  6     // Bytes de dato que caben en el First Frame
#define ISOTP_CF_DATA_BYTES  7     // Bytes de dato por Consecutive Frame

// ---------- MODOS OBD-II ----------
#define MODE_01_CURRENT_DATA       0x01  // Datos en tiempo real
#define MODE_02_FREEZE_FRAME       0x02  // Frame congelado
#define MODE_03_DTCS               0x03  // Códigos de error
#define MODE_04_CLEAR_DTCS         0x04  // Borrar códigos
#define MODE_05_O2_SENSOR          0x05  // Sensores O2
#define MODE_06_TEST_RESULTS       0x06  // Resultados de test
#define MODE_07_PENDING_DTCS       0x07  // Códigos pendientes
#define MODE_09_VEHICLE_INFO       0x09  // Información vehículo
#define MODE_22_VAG_SPECIFIC       0x22  // Lectura específica VAG

// ---------- PIDs MODO 01 (Más comunes) ----------
#define PID_SUPPORTED_01_20        0x00  // PIDs soportados [01-20]
#define PID_MONITOR_STATUS         0x01  // Estado del monitor
#define PID_FREEZE_DTC             0x02  // DTC que causó freeze frame
#define PID_FUEL_SYSTEM_STATUS     0x03  // Estado sistema combustible
#define PID_ENGINE_LOAD            0x04  // Carga motor calculada
#define PID_COOLANT_TEMP           0x05  // Temperatura refrigerante
#define PID_SHORT_FUEL_TRIM_1      0x06  // Ajuste combustible corto B1
#define PID_LONG_FUEL_TRIM_1       0x07  // Ajuste combustible largo B1
#define PID_SHORT_FUEL_TRIM_2      0x08  // Ajuste combustible corto B2
#define PID_LONG_FUEL_TRIM_2       0x09  // Ajuste combustible largo B2
#define PID_FUEL_PRESSURE          0x0A  // Presión combustible
#define PID_INTAKE_MAP             0x0B  // Presión colector admisión
#define PID_ENGINE_RPM             0x0C  // RPM motor
#define PID_VEHICLE_SPEED          0x0D  // Velocidad vehículo
#define PID_TIMING_ADVANCE         0x0E  // Avance encendido
#define PID_INTAKE_TEMP            0x0F  // Temperatura aire admisión
#define PID_MAF_FLOW               0x10  // Flujo MAF
#define PID_THROTTLE_POS           0x11  // Posición acelerador
#define PID_O2_SENSORS_PRESENT     0x13  // Sensores O2 presentes
#define PID_O2_B1S1                0x14  // Sensor O2 banco 1 sensor 1
#define PID_OBD_STANDARDS          0x1C  // Estándar OBD
#define PID_RUNTIME_START          0x1F  // Tiempo desde arranque
#define PID_DISTANCE_MIL           0x21  // Distancia con MIL activado
#define PID_FUEL_RAIL_PRESSURE     0x23  // Presión rail combustible
#define PID_COMMANDED_EGR          0x2C  // EGR comandado
#define PID_EGR_ERROR              0x2D  // Error EGR
#define PID_FUEL_LEVEL             0x2F  // Nivel combustible
#define PID_DISTANCE_CLEAR         0x31  // Distancia desde borrado DTCs
#define PID_BAROMETRIC_PRESSURE    0x33  // Presión barométrica
#define PID_CONTROL_MODULE_VOLTAGE 0x42  // Voltaje módulo control
#define PID_ABSOLUTE_LOAD          0x43  // Carga absoluta
#define PID_AMBIENT_TEMP           0x46  // Temperatura ambiente
#define PID_THROTTLE_POS_B         0x47  // Posición acelerador B
#define PID_THROTTLE_POS_C         0x48  // Posición acelerador C
#define PID_FUEL_TYPE              0x51  // Tipo combustible
#define PID_ETHANOL_FUEL           0x52  // % Etanol
#define PID_ENGINE_OIL_TEMP        0x5C  // Temperatura aceite motor

// ---------- RESPUESTAS OBD-II ----------
#define RESPONSE_SUCCESS           0x40  // Offset para respuesta exitosa (Mode + 0x40)
#define NEGATIVE_RESPONSE          0x7F  // Respuesta negativa

// Códigos de error para respuestas negativas
#define NRC_SERVICE_NOT_SUPPORTED  0x11  // Servicio no soportado
#define NRC_SUBFUNCTION_NOT_SUPP   0x12  // Subfunción no soportada
#define NRC_INVALID_FORMAT         0x13  // Formato mensaje inválido
#define NRC_CONDITIONS_NOT_CORRECT 0x22  // Condiciones no correctas
#define NRC_REQUEST_OUT_OF_RANGE   0x31  // Petición fuera de rango
#define NRC_SECURITY_ACCESS_DENIED 0x33  // Acceso seguridad denegado

// ---------- CONSTANTES DEL SISTEMA ----------
#define SERIAL_BAUDRATE    115200
#define MAX_CAN_DATA_LEN   8

// ---------- HARDWARE — BOTÓN DE ENCENDIDO ----------
#define ENGINE_START_PIN     7    // Pin D7: botón de arranque (INPUT_PULLUP, activo LOW)
#define IGNITION_DEBOUNCE_MS 200  // Debounce mínimo entre flancos del botón (ms)

// ---------- PARÁMETROS ESPECÍFICOS SEAT IBIZA 6J 2012 ----------
// Motor: 1.4 MPI (BXW) — gasolina, aspirado natural, 70 kW (85 CV)
#define VIN_LENGTH         17
#define ENGINE_TYPE_MPI    0x01  // 1.4 MPI (BXW) — inyección multipunto, NA

// Valores simulados del vehículo
struct VehicleData {
  // Datos generales
  char vin[18];                    // VIN del vehículo
  uint8_t engineType;              // Tipo de motor
  uint16_t odometer;               // Odómetro en km
  
  // Datos del motor en tiempo real
  uint8_t engineLoad;              // 0-100%
  int16_t coolantTemp;             // -40 a +215 °C
  uint16_t rpm;                    // 0-16383 RPM
  uint8_t speed;                   // 0-255 km/h
  int8_t timingAdvance;            // -64 a +63.5°
  int16_t intakeTemp;              // -40 a +215 °C
  uint16_t mafFlow;                // 0-655.35 g/s
  uint8_t throttlePos;             // 0-100%
  uint8_t fuelLevel;               // 0-100%
  uint16_t fuelRailPressure;       // 0-65535 kPa
  uint16_t batteryVoltage;         // Voltios * 1000
  int16_t oilTemp;                 // -40 a +215 °C
  int16_t ambientTemp;             // -40 a +215 °C
  uint16_t barometricPressure;     // kPa
  
  // Estado del sistema
  bool checkEngine;                // MIL/Check Engine
  uint8_t numDTCs;                 // Número de DTCs almacenados
  uint32_t runtimeSinceStart;      // Segundos desde arranque
  uint16_t distanceSinceClear;     // km desde borrado DTCs
  
  // Ajustes de combustible
  int8_t shortFuelTrim1;           // -100% a +99.2%
  int8_t longFuelTrim1;            // -100% a +99.2%
};

// ---------- DTCs de ejemplo (P-codes) ----------
struct DTC {
  uint16_t code;                   // Código DTC
  bool active;                     // Si está activo
};

// Códigos DTC comunes SEAT Ibiza
#define DTC_P0000  0x0000  // Sin DTCs
#define DTC_P0016  0x0016  // Correlación cigüeñal/árbol levas
#define DTC_P0101  0x0101  // Rendimiento MAF
#define DTC_P0171  0x0171  // Sistema muy pobre banco 1
#define DTC_P0420  0x0420  // Catalizador bajo rendimiento
#define DTC_P0299  0x0299  // Turbo bajo rendimiento
#define DTC_P0401  0x0401  // Flujo EGR insuficiente

// ---------- Utilidades ----------
inline void encodeRPM(uint8_t* data, uint16_t rpm) {
  uint16_t encoded = rpm * 4;
  data[0] = (encoded >> 8) & 0xFF;
  data[1] = encoded & 0xFF;
}

inline uint16_t decodeRPM(uint8_t* data) {
  return ((uint16_t)data[0] << 8 | data[1]) / 4;
}

inline uint8_t encodeTemp(int16_t temp) {
  return (uint8_t)(temp + 40);
}

inline int16_t decodeTemp(uint8_t encoded) {
  return (int16_t)encoded - 40;
}

inline uint8_t encodePercent(uint8_t percent) {
  return (percent * 255) / 100;
}

inline uint8_t decodePercent(uint8_t encoded) {
  return (encoded * 100) / 255;
}

inline void encodeFuelTrim(uint8_t* data, int8_t trim) {
  *data = (uint8_t)((trim + 100) * 128 / 100);
}

inline int8_t decodeFuelTrim(uint8_t encoded) {
  return ((int16_t)encoded * 100 / 128) - 100;
}

#endif // ECU_PROTOCOL_H
