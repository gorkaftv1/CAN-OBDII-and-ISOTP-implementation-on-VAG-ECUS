/**
 * BluetoothService — singleton que gestiona la conexión RFCOMM con la Raspberry Pi.
 *
 * Protocolo: NDJSON (un objeto JSON por línea terminada en '\n').
 * La Pi se anuncia como "SEAT_DIAG_PI" en el descubrimiento Bluetooth.
 */

import RNBluetoothClassic, {
  BluetoothDevice,
} from 'react-native-bluetooth-classic';
import { ServerMessage } from '../types';

type DataCallback = (msg: ServerMessage) => void;

class BluetoothService {
  private device: BluetoothDevice | null = null;
  private subscription: any = null;
  private callbacks: Set<DataCallback> = new Set();
  private recvBuffer: string = '';

  // ── Descubrimiento ────────────────────────────────────────────────

  async isBluetoothEnabled(): Promise<boolean> {
    return RNBluetoothClassic.isBluetoothEnabled();
  }

  async requestEnable(): Promise<boolean> {
    return RNBluetoothClassic.requestBluetoothEnabled();
  }

  /** Devuelve dispositivos ya emparejados + escaneados (hasta 10s). */
  async discover(): Promise<BluetoothDevice[]> {
    const paired = await RNBluetoothClassic.getBondedDevices();
    try {
      const discovered = await RNBluetoothClassic.startDiscovery();
      await RNBluetoothClassic.cancelDiscovery();
      // Combinar sin duplicados (por address)
      const all = [...paired];
      for (const d of discovered) {
        if (!all.find(p => p.address === d.address)) {
          all.push(d);
        }
      }
      return all;
    } catch {
      return paired;
    }
  }

  // ── Conexión ──────────────────────────────────────────────────────

  async connect(device: BluetoothDevice): Promise<void> {
    this.device = await device.connect({ delimiter: '\n' });
    this.recvBuffer = '';

    this.subscription = this.device.onDataReceived(evt => {
      this.recvBuffer += evt.data;
      let idx: number;
      while ((idx = this.recvBuffer.indexOf('\n')) !== -1) {
        const line = this.recvBuffer.slice(0, idx).trim();
        this.recvBuffer = this.recvBuffer.slice(idx + 1);
        if (!line) continue;
        try {
          const msg = JSON.parse(line) as ServerMessage;
          this.callbacks.forEach(cb => cb(msg));
        } catch {
          // JSON malformado — ignorar
        }
      }
    });
  }

  async disconnect(): Promise<void> {
    this.subscription?.remove();
    this.subscription = null;
    try {
      await this.device?.disconnect();
    } catch {}
    this.device = null;
  }

  isConnected(): boolean {
    return this.device?.isConnected() ?? false;
  }

  // ── Envío ─────────────────────────────────────────────────────────

  /** Envía un comando JSON al servidor Pi (añade '\n' al final). */
  send(cmd: object): void {
    if (!this.device) throw new Error('No hay conexión Bluetooth activa');
    this.device.write(JSON.stringify(cmd) + '\n');
  }

  // ── Suscripción a datos ───────────────────────────────────────────

  onData(callback: DataCallback): () => void {
    this.callbacks.add(callback);
    return () => this.callbacks.delete(callback);
  }
}

// Singleton exportado
export const bluetoothService = new BluetoothService();
