import { VehicleData } from './models/VehicleData';

export class ProtocolParser {
  static parseFrame(frame: string): Partial<Omit<VehicleData, 'timestamp'>> | null {
    const parts = frame.trim().split(' ');
    if (parts[0] !== '41' || parts.length < 3) return null;

    const pid = parts[1];
    const a = parseInt(parts[2], 16);
    const b = parts[3] ? parseInt(parts[3], 16) : 0;

    switch (pid) {
      case '0C': return { rpm: (a * 256 + b) / 4 };
      case '0D': return { speed: a };
      case '05': return { engineTemp: a - 40 };
      case '2F': return { fuelLevel: (a / 255) * 100 };
      case '42': return { voltage: (a * 256 + b) / 1000 };
      case '11': return { throttlePosition: (a / 255) * 100 };
      default: return null;
    }
  }
}
