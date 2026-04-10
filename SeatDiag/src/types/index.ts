// Tipos TypeScript que mapean exactamente los modelos Python del servidor

export interface MonitorSample {
  pid: number;
  name: string;
  value: number;
  unit: string;
  ts: number; // monotonic timestamp
}

export interface DtcItem {
  code: string;
  description: string;
}

export interface PidSnapshot {
  [pidName: string]: {
    value: number;
    unit: string;
  };
}

export interface LogSession {
  session_id: number;
  label: string;
  started_at: string;
  ended_at: string | null;
  sample_count: number;
}

export interface CommandLog {
  command: string;
  request_hex: string;
  response_hex: string;
  timestamp: string;
}

// Tipos de mensajes del servidor
export type ServerMessage =
  | { status: 'ok'; data: unknown }
  | { status: 'error'; message: string }
  | { type: 'sample' } & MonitorSample
  | { type: 'error'; pid: number; message: string };

// Tipos de navegación
export type RootStackParamList = {
  Scan: undefined;
  Connecting: { deviceName: string; deviceId: string };
  Dashboard: undefined;
  Dtc: undefined;
  History: undefined;
  SessionDetail: { session: LogSession };
};
