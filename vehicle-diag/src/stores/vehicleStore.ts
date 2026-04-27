import { create } from 'zustand';
import { VehicleData } from '../domain/models/VehicleData';

const DEFAULTS: VehicleData = {
  rpm: 0,
  speed: 0,
  engineTemp: 0,
  fuelLevel: 0,
  voltage: 0,
  throttlePosition: 0,
  timestamp: 0,
};

interface VehicleState {
  latest: VehicleData | null;
  vin: string | null;
  monitoring: boolean;
  updatePartial: (data: Partial<VehicleData> & { timestamp: number }) => void;
  setVin: (vin: string | null) => void;
  setMonitoring: (v: boolean) => void;
  clear: () => void;
}

export const useVehicleStore = create<VehicleState>((set) => ({
  latest: null,
  vin: null,
  monitoring: false,

  updatePartial: (data) =>
    set((state) => ({
      latest: {
        ...DEFAULTS,
        ...state.latest,
        ...data,
      },
    })),

  setVin: (vin) => set({ vin }),
  setMonitoring: (v) => set({ monitoring: v }),

  clear: () => set({ latest: null, monitoring: false }),
}));
