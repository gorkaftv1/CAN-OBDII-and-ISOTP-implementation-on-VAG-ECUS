import { getAdapter, USE_MOCK } from '../../infrastructure/adapterFactory';
import { VehicleService } from './VehicleService';
import { LogService } from './LogService';
import { useVehicleStore } from '../../stores/vehicleStore';

export class ConnectionService {
  static async connect(
    onPhase: (phase: 'scanning' | 'connecting') => void,
  ): Promise<string> {
    const adapter = getAdapter();
    const deviceName = USE_MOCK ? 'Mock OBD2 Adapter' : 'SEAT_DIAG';

    onPhase('scanning');
    LogService.add('info', USE_MOCK ? 'Starting mock connection...' : 'Scanning for SEAT_DIAG...');

    // Transition to "connecting" phase after a visual delay:
    // BLE scan can take several seconds before the device is found.
    const connectingTimer = setTimeout(() => {
      onPhase('connecting');
      LogService.add('info', `Connecting to ${deviceName}...`);
    }, USE_MOCK ? 1000 : 3000);

    try {
      await adapter.connect();
      clearTimeout(connectingTimer);
      LogService.add('info', `Connected to ${deviceName}`);
      VehicleService.fetchVin(); // fire-and-forget
      VehicleService.start();
      return deviceName;
    } catch (e) {
      clearTimeout(connectingTimer);
      throw e;
    }
  }

  static async disconnect(): Promise<void> {
    VehicleService.stop();
    await getAdapter().disconnect();
    useVehicleStore.getState().setVin(null);
    LogService.add('info', 'Disconnected');
  }
}
