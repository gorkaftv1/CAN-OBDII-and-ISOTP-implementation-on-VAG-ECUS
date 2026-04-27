import { DtcCode } from '../domain/models/DtcCode';
import { MonitorSample } from '../domain/models/MonitorSample';
import { IVehicleAdapter } from './IVehicleAdapter';

function clamp(val: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, val));
}

function fluctuate(current: number, delta: number, min: number, max: number): number {
  return clamp(current + (Math.random() - 0.5) * delta * 2, min, max);
}

interface SimState {
  rpm: number;
  speed: number;
  engineTemp: number;
  fuelLevel: number;
  voltage: number;
  throttle: number;
}

function delay(ms: number): Promise<void> {
  return new Promise<void>((r) => setTimeout(r, ms));
}

const INITIAL_DTCS: Array<Pick<DtcCode, 'code' | 'description' | 'severity'>> = [
  { code: 'P0171', description: 'System Too Lean (Bank 1)', severity: 'warning' },
  { code: 'P0300', description: 'Random/Multiple Cylinder Misfire Detected', severity: 'error' },
  { code: 'P0420', description: 'Catalyst System Efficiency Below Threshold (Bank 1)', severity: 'warning' },
];

export class MockAdapter implements IVehicleAdapter {
  private static instance: MockAdapter;
  private _connected = false;
  private mockDtcs = [...INITIAL_DTCS];

  private sim: SimState = {
    rpm: 800,
    speed: 0,
    engineTemp: 20,
    fuelLevel: 75,
    voltage: 12.6,
    throttle: 5,
  };

  static getInstance(): MockAdapter {
    if (!MockAdapter.instance) MockAdapter.instance = new MockAdapter();
    return MockAdapter.instance;
  }

  async connect(): Promise<void> {
    await delay(1200);
    await delay(800);
    this._connected = true;
  }

  async disconnect(): Promise<void> {
    this._connected = false;
  }

  isConnected(): boolean {
    return this._connected;
  }

  startMonitor(
    pids: number[],
    intervalMs: number,
    onSample: (sample: MonitorSample) => void,
  ): () => void {
    const timer = setInterval(() => {
      this.tick();
      const ts = Date.now() / 1000;
      for (const pid of pids) {
        const s = this.makeSample(pid, ts);
        if (s) onSample(s);
      }
    }, intervalMs);
    return () => clearInterval(timer);
  }

  async fetchDtcs(): Promise<Array<Pick<DtcCode, 'code' | 'description' | 'severity'>>> {
    if (!this._connected) throw new Error('Not connected');
    await delay(600);
    return [...this.mockDtcs];
  }

  async clearDtcs(): Promise<void> {
    if (!this._connected) throw new Error('Not connected');
    await delay(400);
    this.mockDtcs = [];
  }

  async getSnapshot(): Promise<Record<string, { value: number; unit: string }>> {
    if (!this._connected) throw new Error('Not connected');
    await delay(300);
    const s = this.sim;
    return {
      RPM:     { value: Math.round(s.rpm),          unit: 'rpm' },
      Speed:   { value: Math.round(s.speed),         unit: 'km/h' },
      Coolant: { value: parseFloat(s.engineTemp.toFixed(1)), unit: '°C' },
      Fuel:    { value: parseFloat(s.fuelLevel.toFixed(1)),  unit: '%' },
      Voltage: { value: parseFloat(s.voltage.toFixed(2)),    unit: 'V' },
      Throttle:{ value: parseFloat(s.throttle.toFixed(1)),   unit: '%' },
    };
  }

  async getVin(): Promise<string> {
    if (!this._connected) throw new Error('Not connected');
    await delay(400);
    return 'VSSKZZZ1KZW000001';
  }

  async getSessions(_limit = 50): Promise<any[]> {
    if (!this._connected) throw new Error('Not connected');
    await delay(200);
    return [];
  }

  async getSessionSamples(_sessionId: number, _pid?: number, _limit = 1000): Promise<any[]> {
    if (!this._connected) throw new Error('Not connected');
    await delay(200);
    return [];
  }

  async getSessionCommands(_sessionId: number): Promise<any[]> {
    if (!this._connected) throw new Error('Not connected');
    await delay(200);
    return [];
  }

  // ── Simulation ──────────────────────────────────────────────────────

  private tick(): void {
    const s = this.sim;
    s.throttle = fluctuate(s.throttle, 8, 0, 80);
    s.rpm = clamp(800 + s.throttle * 60 + (Math.random() - 0.5) * 200, 700, 6500);
    s.speed = clamp(s.throttle * 2.5 + (Math.random() - 0.5) * 5, 0, 200);
    if (s.engineTemp < 88) s.engineTemp += 0.3;
    s.engineTemp = fluctuate(s.engineTemp, 0.4, 20, 115);
    s.fuelLevel = Math.max(0, s.fuelLevel - 0.005);
    s.voltage = fluctuate(s.voltage, 0.05, 11.5, 14.8);
  }

  private makeSample(pid: number, ts: number): MonitorSample | null {
    const s = this.sim;
    const ok = (name: string, value: number, unit: string): MonitorSample => ({
      type: 'sample', pid, name, value, unit, ts,
    });
    switch (pid) {
      case 4:  return ok('Engine Load',              clamp(s.throttle * 1.2, 0, 100), '%');
      case 5:  return ok('Coolant Temp',             s.engineTemp,                    '°C');
      case 12: return ok('Engine RPM',               s.rpm,                           'rpm');
      case 13: return ok('Vehicle Speed',            s.speed,                         'km/h');
      case 17: return ok('Throttle Position',        s.throttle,                      '%');
      case 47: return ok('Fuel Level',               s.fuelLevel,                     '%');
      case 66: return ok('Control Module Voltage',   s.voltage,                       'V');
      default: return null;
    }
  }
}
