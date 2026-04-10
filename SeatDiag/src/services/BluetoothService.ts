/**
 * BluetoothService — singleton que gestiona la conexión BLE con la Raspberry Pi.
 *
 * Perfil: Nordic UART Service (NUS) sobre BLE. Compatible con Android e iOS.
 * Protocolo: NDJSON (un objeto JSON por línea terminada en '\n').
 *
 * UUIDs NUS:
 *   Service : 6E400001-B5A3-F393-E0A9-E50E24DCCA9E
 *   RX char : 6E400002-B5A3-F393-E0A9-E50E24DCCA9E  (app → Pi, write)
 *   TX char : 6E400003-B5A3-F393-E0A9-E50E24DCCA9E  (Pi → app, notify)
 */

import { BleManager, Device, Subscription, BleError } from 'react-native-ble-plx';
import { ServerMessage } from '../types';

const NUS_SERVICE = '6e400001-b5a3-f393-e0a9-e50e24dcca9e';
const NUS_RX      = '6e400002-b5a3-f393-e0a9-e50e24dcca9e'; // write
const NUS_TX      = '6e400003-b5a3-f393-e0a9-e50e24dcca9e'; // notify

const SCAN_TIMEOUT_MS = 10_000;

type DataCallback = (msg: ServerMessage) => void;

/** Codifica un string UTF-8 a base64 (necesario para ble-plx). */
function toBase64(str: string): string {
  return btoa(unescape(encodeURIComponent(str)));
}

/** Decodifica base64 a string UTF-8. */
function fromBase64(b64: string): string {
  return decodeURIComponent(escape(atob(b64)));
}

class BluetoothService {
  private manager = new BleManager();
  private device: Device | null = null;
  private txSubscription: Subscription | null = null;
  private callbacks: Set<DataCallback> = new Set();
  private recvBuffer: string = '';

  // ── Escaneo ───────────────────────────────────────────────────────

  /**
   * Escanea BLE durante SCAN_TIMEOUT_MS y devuelve los dispositivos encontrados
   * que anuncian el servicio NUS. En Android también incluye dispositivos sin
   * filtro de servicio por si la Pi no lo anuncia en el advertisement.
   */
  async scan(): Promise<Device[]> {
    return new Promise((resolve, reject) => {
      const found = new Map<string, Device>();

      this.manager.startDeviceScan(
        [NUS_SERVICE],
        { allowDuplicates: false },
        (error: BleError | null, device: Device | null) => {
          if (error) {
            this.manager.stopDeviceScan();
            reject(error);
            return;
          }
          if (device) {
            found.set(device.id, device);
          }
        },
      );

      setTimeout(() => {
        this.manager.stopDeviceScan();
        resolve(Array.from(found.values()));
      }, SCAN_TIMEOUT_MS);
    });
  }

  stopScan(): void {
    this.manager.stopDeviceScan();
  }

  // ── Conexión ──────────────────────────────────────────────────────

  async connect(deviceId: string): Promise<void> {
    this.device = await this.manager.connectToDevice(deviceId);
    await this.device.discoverAllServicesAndCharacteristics();

    // Suscribirse a notificaciones TX (Pi → app)
    this.txSubscription = this.device.monitorCharacteristicForService(
      NUS_SERVICE,
      NUS_TX,
      (error, characteristic) => {
        if (error || !characteristic?.value) return;
        const chunk = fromBase64(characteristic.value);
        this.recvBuffer += chunk;

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
      },
    );
  }

  async disconnect(): Promise<void> {
    this.txSubscription?.remove();
    this.txSubscription = null;
    this.recvBuffer = '';
    try {
      await this.device?.cancelConnection();
    } catch {}
    this.device = null;
  }

  isConnected(): boolean {
    return this.device?.isConnected() ?? false;
  }

  // ── Envío ─────────────────────────────────────────────────────────

  /** Envía un comando JSON a la Pi (escribe en la característica RX). */
  send(cmd: object): void {
    if (!this.device) throw new Error('No hay conexión BLE activa');
    const payload = JSON.stringify(cmd) + '\n';
    // writeWithResponse para mayor fiabilidad
    this.device.writeCharacteristicWithResponseForService(
      NUS_SERVICE,
      NUS_RX,
      toBase64(payload),
    );
  }

  // ── Suscripción a datos ───────────────────────────────────────────

  onData(callback: DataCallback): () => void {
    this.callbacks.add(callback);
    return () => this.callbacks.delete(callback);
  }

  // ── Estado BLE ────────────────────────────────────────────────────

  async isBluetoothEnabled(): Promise<boolean> {
    const state = await this.manager.state();
    return state === 'PoweredOn';
  }

  getBleManager(): BleManager {
    return this.manager;
  }
}

// Singleton exportado
export const bluetoothService = new BluetoothService();
