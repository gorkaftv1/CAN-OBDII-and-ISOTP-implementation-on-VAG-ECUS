import { DtcCode } from '../domain/models/DtcCode';
import { MonitorSample } from '../domain/models/MonitorSample';

export interface IVehicleAdapter {
  connect(): Promise<void>;
  disconnect(): Promise<void>;
  isConnected(): boolean;

  startMonitor(
    pids: number[],
    intervalMs: number,
    onSample: (sample: MonitorSample) => void,
  ): () => void;

  fetchDtcs(): Promise<Array<Pick<DtcCode, 'code' | 'description' | 'severity'>>>;
  clearDtcs(): Promise<void>;

  getSnapshot(): Promise<Record<string, { value: number; unit: string }>>;
  getVin(): Promise<string>;
  getSessions(limit?: number): Promise<any[]>;
  getSessionSamples(sessionId: number, pid?: number, limit?: number): Promise<any[]>;
  getSessionCommands(sessionId: number): Promise<any[]>;
}
