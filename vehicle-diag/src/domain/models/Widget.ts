import { VehicleData } from './VehicleData';

export interface Widget {
  id: string;
  label: string;
  dataKey: keyof Omit<VehicleData, 'timestamp'>;
  unit: string;
  visible: boolean;
  order: number;
}

export const DEFAULT_WIDGETS: Widget[] = [
  { id: 'rpm', label: 'RPM', dataKey: 'rpm', unit: 'rpm', visible: true, order: 0 },
  { id: 'speed', label: 'Speed', dataKey: 'speed', unit: 'km/h', visible: true, order: 1 },
  { id: 'engineTemp', label: 'Eng. Temp', dataKey: 'engineTemp', unit: '°C', visible: true, order: 2 },
  { id: 'fuelLevel', label: 'Fuel', dataKey: 'fuelLevel', unit: '%', visible: true, order: 3 },
  { id: 'voltage', label: 'Voltage', dataKey: 'voltage', unit: 'V', visible: true, order: 4 },
  { id: 'throttle', label: 'Throttle', dataKey: 'throttlePosition', unit: '%', visible: true, order: 5 },
];
