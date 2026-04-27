import { getAdapter } from '../../infrastructure/adapterFactory';
import { MonitorSample } from '../models/MonitorSample';
import { VehicleData } from '../models/VehicleData';
import { useVehicleStore } from '../../stores/vehicleStore';
import { useLogsStore } from '../../stores/logsStore';
import { LogService } from './LogService';

// OBD2 PIDs to request (decimal): 4=Engine Load, 5=Coolant, 12=RPM, 13=Speed,
// 17=Throttle, 47=Fuel Level, 66=Control Module Voltage
const MONITOR_PIDS = [4, 5, 12, 13, 17, 47, 66];
const INTERVAL_MS  = 500;

const PID_FIELD: Partial<Record<number, keyof Omit<VehicleData, 'timestamp'>>> = {
  12: 'rpm',
  13: 'speed',
  5:  'engineTemp',
  17: 'throttlePosition',
  47: 'fuelLevel',
  66: 'voltage',
};

let stopMonitor: (() => void) | null = null;
let lastDataLogAt = 0;

function fmtTime(ts: number): string {
  const d = new Date(ts);
  const p = (n: number, z = 2) => n.toString().padStart(z, '0');
  return `${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}.${p(d.getMilliseconds(), 3)}`;
}

function handleSample(sample: MonitorSample): void {
  const now = Date.now();

  if (sample.type === 'error') {
    useLogsStore.getState().addConsoleLine(
      `[${fmtTime(now)}] [ERR] pid:${sample.pid} ${sample.message ?? ''}`,
    );
    return;
  }

  useLogsStore.getState().addConsoleLine(
    `[${fmtTime(now)}] [RX] pid:${sample.pid} "${sample.name}" = ${sample.value} ${sample.unit ?? ''}`,
  );

  const field = PID_FIELD[sample.pid];
  if (field !== undefined && sample.value !== undefined) {
    useVehicleStore.getState().updatePartial({ [field]: sample.value, timestamp: now });
  }

  // Aggregate data log entry every 2 s
  if (now - lastDataLogAt >= 2000) {
    lastDataLogAt = now;
    const v = useVehicleStore.getState().latest;
    if (v) {
      LogService.add(
        'data',
        `RPM:${Math.round(v.rpm)} SPD:${Math.round(v.speed)}km/h ` +
          `TEMP:${v.engineTemp.toFixed(0)}°C FUEL:${v.fuelLevel.toFixed(0)}% ` +
          `VOLT:${v.voltage.toFixed(2)}V`,
      );
    }
  }
}

export class VehicleService {
  static start(): void {
    if (stopMonitor) return; // already running
    const adapter = getAdapter();
    stopMonitor = adapter.startMonitor(MONITOR_PIDS, INTERVAL_MS, handleSample);
    useVehicleStore.getState().setMonitoring(true);
    LogService.add('info', 'Monitor started');
  }

  static stop(): void {
    stopMonitor?.();
    stopMonitor = null;
    lastDataLogAt = 0;
    useVehicleStore.getState().clear();
    LogService.add('info', 'Monitor stopped');
  }

  static async fetchVin(): Promise<void> {
    try {
      const vin = await getAdapter().getVin();
      useVehicleStore.getState().setVin(vin);
      LogService.add('info', `VIN: ${vin}`);
    } catch {
      // VIN not available on all vehicles — ignore silently
    }
  }
}
