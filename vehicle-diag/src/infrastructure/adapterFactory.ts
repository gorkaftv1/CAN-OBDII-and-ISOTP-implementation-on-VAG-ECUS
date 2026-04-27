import { IVehicleAdapter } from './IVehicleAdapter';

// Flip to true to use the simulated MockAdapter (offline / no hardware)
export const USE_MOCK = false;

export function getAdapter(): IVehicleAdapter {
  if (USE_MOCK) {
    const { MockAdapter } = require('./MockAdapter') as typeof import('./MockAdapter');
    return MockAdapter.getInstance();
  }
  const { BleAdapter } = require('./BleAdapter') as typeof import('./BleAdapter');
  return BleAdapter.getInstance();
}
