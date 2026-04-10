/**
 * DiagService — API tipada sobre BluetoothService.
 *
 * Envía comandos y devuelve promesas que se resuelven con la primera
 * respuesta que coincide con el comando enviado.
 */

import { bluetoothService } from './BluetoothService';
import {
  DtcItem,
  LogSession,
  CommandLog,
  MonitorSample,
  PidSnapshot,
  ServerMessage,
} from '../types';

function waitForResponse<T>(timeoutMs = 5000): Promise<T> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      unsub();
      reject(new Error('Timeout esperando respuesta del servidor'));
    }, timeoutMs);

    const unsub = bluetoothService.onData((msg: ServerMessage) => {
      if ('type' in msg) return; // mensajes push del monitor — ignorar aquí
      clearTimeout(timer);
      unsub();
      if (msg.status === 'error') {
        reject(new Error(msg.message));
      } else {
        resolve(msg.data as T);
      }
    });
  });
}

export const DiagService = {
  // ── Snapshot ──────────────────────────────────────────────────────

  async snapshot(): Promise<PidSnapshot> {
    bluetoothService.send({ cmd: 'snapshot' });
    return waitForResponse<PidSnapshot>(10000);
  },

  // ── DTCs ──────────────────────────────────────────────────────────

  async getDtcs(): Promise<DtcItem[]> {
    bluetoothService.send({ cmd: 'dtcs' });
    return waitForResponse<DtcItem[]>();
  },

  async clearDtcs(): Promise<void> {
    bluetoothService.send({ cmd: 'clear_dtcs' });
    await waitForResponse<null>();
  },

  // ── VIN ───────────────────────────────────────────────────────────

  async getVin(): Promise<string> {
    bluetoothService.send({ cmd: 'vin' });
    return waitForResponse<string>();
  },

  // ── Monitor live ──────────────────────────────────────────────────

  startMonitor(
    pids: number[],
    intervalMs: number,
    onSample: (s: MonitorSample) => void,
  ): () => void {
    bluetoothService.send({ cmd: 'monitor_start', pids, interval_ms: intervalMs });
    const unsub = bluetoothService.onData((msg: ServerMessage) => {
      if ('type' in msg && msg.type === 'sample') {
        onSample(msg as unknown as MonitorSample);
      }
    });
    return unsub;
  },

  stopMonitor(): void {
    bluetoothService.send({ cmd: 'monitor_stop' });
  },

  // ── Historial ─────────────────────────────────────────────────────

  async getSessions(limit = 50): Promise<LogSession[]> {
    bluetoothService.send({ cmd: 'sessions', limit });
    return waitForResponse<LogSession[]>();
  },

  async getSessionSamples(
    sessionId: number,
    pid?: number,
    limit = 1000,
  ): Promise<MonitorSample[]> {
    bluetoothService.send({
      cmd: 'session_samples',
      session_id: sessionId,
      pid,
      limit,
    });
    return waitForResponse<MonitorSample[]>(15000);
  },

  async getSessionCommands(sessionId: number): Promise<CommandLog[]> {
    bluetoothService.send({ cmd: 'session_commands', session_id: sessionId });
    return waitForResponse<CommandLog[]>();
  },
};
