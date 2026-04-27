import { BleManager, Device, Subscription } from 'react-native-ble-plx';
import { DtcCode } from '../domain/models/DtcCode';
import { MonitorSample } from '../domain/models/MonitorSample';
import { IVehicleAdapter } from './IVehicleAdapter';
import { LogService } from '../domain/services/LogService';

// Nordic UART Service UUIDs
const NUS_SERVICE = '6E400001-B5A3-F393-E0A9-E50E24DCCA9E';
const RX_CHAR     = '6E400002-B5A3-F393-E0A9-E50E24DCCA9E'; // app → Pi (write)
const TX_CHAR     = '6E400003-B5A3-F393-E0A9-E50E24DCCA9E'; // Pi → app (notify)

const DEVICE_NAME       = 'SEAT_DIAG';
const MTU               = 512;
const WRITE_CHUNK_BYTES = 240; // Nordic UART safe maximum
const SCAN_TIMEOUT_MS   = 20_000;
const REQUEST_TIMEOUT_MS = 15_000; // Aligned with Pi client timeout (15s)
const CLIENT_TIMEOUT_MS  = 20_000; // Pi disconnects after 15s, so we use 20s as safety margin
const INACTIVITY_CHECK_MS = 5_000; // Check every 5 seconds

// ── Base64 helpers (React Native doesn't expose Buffer) ──────────────

function strToB64(str: string): string {
  const bytes = new TextEncoder().encode(str);
  let bin = '';
  for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
  return btoa(bin);
}

function b64ToStr(b64: string): string {
  const bin = atob(b64);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return new TextDecoder().decode(bytes);
}

// ── Pending request slot ─────────────────────────────────────────────

interface Pending {
  resolve: (data: unknown) => void;
  reject: (err: Error) => void;
  timer: ReturnType<typeof setTimeout>;
}

// ── Adapter ──────────────────────────────────────────────────────────

export class BleAdapter implements IVehicleAdapter {
  private static instance: BleAdapter;

  private readonly manager = new BleManager();
  private device: Device | null = null;
  private txSub: Subscription | null = null;

  // NDJSON reassembly buffer
  private rxBuf = '';

  // Request-response queue (FIFO — one outstanding request at a time is typical)
  private queue: Pending[] = [];

  // Active monitor sample subscribers
  private sampleCbs: Set<(s: MonitorSample) => void> = new Set();

  // Activity monitoring (detect Pi timeout on client side)
  private lastActivityTime = 0;
  private activityMonitorInterval: ReturnType<typeof setInterval> | null = null;
  private pingInterval: ReturnType<typeof setInterval> | null = null;

  static getInstance(): BleAdapter {
    if (!BleAdapter.instance) BleAdapter.instance = new BleAdapter();
    return BleAdapter.instance;
  }

  // ── IVehicleAdapter ──────────────────────────────────────────────

  async connect(): Promise<void> {
    let retries = 0;
    const MAX_RETRIES = 5;

    while (retries < MAX_RETRIES) {
      try {
        this.device = await this.scanAndConnect();
        await this.subscribeToTx();
        
        try {
          LogService.add('info', '🔐 Authenticating with Pi...');
          await this.authenticate();
          LogService.add('success', '✓ Authentication successful');

          // ✓ Auth successful → start keepalive + activity monitor
          this.lastActivityTime = Date.now();
          this.startPingInterval();
          this.startActivityMonitor();
        } catch (e) {
          const errMsg = e instanceof Error ? e.message : String(e);
          LogService.add('error', `❌ Authentication failed: ${errMsg}`);
          await this.disconnect();
          throw e;
        }
        return;  // ✓ Success
      } catch (e) {
        retries++;
        const errMsg = e instanceof Error ? e.message : String(e);
        
        if (retries >= MAX_RETRIES) {
          LogService.add('error', `❌ Connection failed after ${MAX_RETRIES} retries: ${errMsg}`);
          throw e;
        }
        
        // Backoff: 2s, 4s, 8s, 16s, 30s
        const waitMs = Math.min(2 ** retries * 1000, 30000);
        LogService.add('warning', `⚠️ Connection attempt ${retries}/${MAX_RETRIES} failed. Retrying in ${waitMs}ms...`);
        await new Promise(r => setTimeout(r, waitMs));
      }
    }
  }

  private async authenticate(token = '1234'): Promise<void> {
    LogService.add('debug', `Sending auth with token: ${token}`);
    try {
      await this.request({ cmd: 'auth', token });
    } catch (e) {
      const errMsg = e instanceof Error ? e.message : String(e);
      LogService.add('error', `Auth request error: ${errMsg}`);
      throw e;
    }
  }

  async disconnect(): Promise<void> {
    if (this.pingInterval) {
      clearInterval(this.pingInterval);
      this.pingInterval = null;
    }
    if (this.activityMonitorInterval) {
      clearInterval(this.activityMonitorInterval);
      this.activityMonitorInterval = null;
    }
    this.txSub?.remove();
    this.txSub = null;
    this.rxBuf = '';
    this.drainQueue(new Error('Disconnected'));
    if (this.device) {
      try { await this.device.cancelConnection(); } catch { /* ignore */ }
      this.device = null;
    }
  }

  isConnected(): boolean {
    return this.device !== null;
  }

  startMonitor(
    pids: number[],
    intervalMs: number,
    onSample: (s: MonitorSample) => void,
  ): () => void {
    this.sampleCbs.add(onSample);
    // Send monitor_start; we don't need to await — samples will arrive as push
    LogService.add('info', `Starting monitor: ${pids.length} PIDs, interval ${intervalMs}ms`);
    this.request({ cmd: 'monitor_start', pids, interval_ms: intervalMs }).catch((e) => {
      const errMsg = e instanceof Error ? e.message : String(e);
      LogService.add('error', `Monitor start failed: ${errMsg}`);
    });

    return () => {
      this.sampleCbs.delete(onSample);
      if (this.sampleCbs.size === 0) {
        LogService.add('info', `Stopping monitor`);
        this.request({ cmd: 'monitor_stop' }).catch((e) => {
          const errMsg = e instanceof Error ? e.message : String(e);
          LogService.add('error', `Monitor stop failed: ${errMsg}`);
        });
      }
    };
  }

  async fetchDtcs(): Promise<Array<Pick<DtcCode, 'code' | 'description' | 'severity'>>> {
    const raw = await this.request<Array<{ code: string; description: string }>>({ cmd: 'dtcs' });
    return (raw ?? []).map((d) => ({ ...d, severity: 'warning' as const }));
  }

  async clearDtcs(): Promise<void> {
    await this.request({ cmd: 'clear_dtcs' });
  }

  async getSnapshot(): Promise<Record<string, { value: number; unit: string }>> {
    return await this.request({ cmd: 'snapshot' });
  }

  async getVin(): Promise<string> {
    return await this.request({ cmd: 'vin' });
  }

  async getSessions(limit: number = 50): Promise<any[]> {
    return await this.request({ cmd: 'sessions', limit });
  }

  async getSessionSamples(
    sessionId: number,
    pid?: number,
    limit: number = 1000,
  ): Promise<any[]> {
    return await this.request({
      cmd: 'session_samples',
      session_id: sessionId,
      pid,
      limit,
    });
  }

  async getSessionCommands(sessionId: number): Promise<any[]> {
    return await this.request({ cmd: 'session_commands', session_id: sessionId });
  }

  // ── BLE internals ────────────────────────────────────────────────

  private scanAndConnect(): Promise<Device> {
    return new Promise<Device>((resolve, reject) => {
      const scanTimer = setTimeout(() => {
        this.manager.stopDeviceScan();
        reject(new Error(`"${DEVICE_NAME}" not found (scan timeout)`));
      }, SCAN_TIMEOUT_MS);

      this.manager.startDeviceScan(
        [NUS_SERVICE],
        { allowDuplicates: false },
        async (err, device) => {
          if (err) {
            clearTimeout(scanTimer);
            this.manager.stopDeviceScan();
            reject(err);
            return;
          }
          if (!device || device.name !== DEVICE_NAME) return;

          this.manager.stopDeviceScan();
          clearTimeout(scanTimer);

          try {
            const conn = await device.connect({ autoConnect: false });
            await conn.requestMTU(MTU);
            await conn.discoverAllServicesAndCharacteristics();
            conn.onDisconnected(() => this.handleUnexpectedDisconnect());
            resolve(conn);
          } catch (e) {
            reject(e);
          }
        },
      );
    });
  }

  private subscribeToTx(): Promise<void> {
    return new Promise<void>((resolve, reject) => {
      if (!this.device) { reject(new Error('Not connected')); return; }

      this.txSub = this.device.monitorCharacteristicForService(
        NUS_SERVICE,
        TX_CHAR,
        (err, char) => {
          if (err || !char?.value) return;
          this.feedBuffer(b64ToStr(char.value));
        },
      );
      // monitorCharacteristicForService is synchronous in setup; resolve immediately
      resolve();
    });
  }

  // ── NDJSON buffer ────────────────────────────────────────────────

  private feedBuffer(chunk: string): void {
    // Any message = activity (including heartbeats)
    this.lastActivityTime = Date.now();
    
    this.rxBuf += chunk;
    // Split on newline; last element is the incomplete trailing fragment
    const lines = this.rxBuf.split('\n');
    this.rxBuf = lines.pop() ?? '';
    for (const line of lines) {
      const t = line.trim();
      if (!t) continue;
      try {
        this.dispatch(JSON.parse(t) as Record<string, unknown>);
      } catch {
        // malformed JSON chunk — skip silently
      }
    }
  }

  private dispatch(msg: Record<string, unknown>): void {
    // Push messages (monitor samples) bypass the request queue
    if (msg.type === 'sample' || msg.type === 'error') {
      this.sampleCbs.forEach((cb) => cb(msg as unknown as MonitorSample));
      return;
    }

    // Heartbeat: Pi keep-alive — ACK it so Pi keeps _last_rx_time fresh
    if (msg.type === 'heartbeat') {
      this.sendHeartbeatAck();
      return;
    }

    // Ignore our own ACK echoes (shouldn't arrive, but be defensive)
    if (msg.type === 'heartbeat_ack') {
      return;
    }

    // Pong response to our proactive ping — discard without touching the queue
    if (msg.status === 'ok' && msg.data === 'pong') {
      LogService.add('debug', 'Ping ACK from Pi');
      return;
    }

    // Request-response: consume the head of the FIFO queue
    const pending = this.queue.shift();
    if (!pending) {
      LogService.add('debug', `⚠️ Orphaned message (no pending request): ${JSON.stringify(msg)}`);
      return;
    }
    clearTimeout(pending.timer);

    if (msg.status === 'ok') {
      LogService.add('debug', `✓ Response OK: ${msg.cmd ?? 'unknown'}`);
      pending.resolve(msg.data);
    } else {
      const errMsg = (msg.message as string) ?? 'Server error';
      LogService.add('warning', `⚠️ Response error for ${msg.cmd ?? 'unknown'}: ${errMsg}`);
      pending.reject(new Error(errMsg));
    }
  }

  // ── Request-response ─────────────────────────────────────────────

  private request<T = unknown>(cmd: object): Promise<T> {
    return new Promise<T>((resolve, reject) => {
      const timer = setTimeout(() => {
        const idx = this.queue.findIndex((p) => p.timer === timer);
        if (idx !== -1) this.queue.splice(idx, 1);
        reject(new Error(`Timeout: ${JSON.stringify(cmd)}`));
      }, REQUEST_TIMEOUT_MS);

      this.queue.push({ resolve: resolve as (d: unknown) => void, reject, timer });
      this.writeRx(JSON.stringify(cmd) + '\n').catch((e) => {
        // If the write fails, remove from queue and reject
        const idx = this.queue.findIndex((p) => p.timer === timer);
        if (idx !== -1) { clearTimeout(timer); this.queue.splice(idx, 1); }
        reject(e);
      });
    });
  }

  private async writeRx(data: string): Promise<void> {
    if (!this.device) throw new Error('Not connected');
    const bytes = new TextEncoder().encode(data);
    const cmd = data.split('\n')[0];
    
    try {
      // Chunk into WRITE_CHUNK_BYTES slices and write each with response
      for (let offset = 0; offset < bytes.length; offset += WRITE_CHUNK_BYTES) {
        const slice = bytes.subarray(offset, offset + WRITE_CHUNK_BYTES);
        let bin = '';
        for (let i = 0; i < slice.length; i++) bin += String.fromCharCode(slice[i]);
        await this.device.writeCharacteristicWithResponseForService(
          NUS_SERVICE,
          RX_CHAR,
          btoa(bin),
        );
      }
      LogService.add('debug', `📤 Write sent: ${cmd}`);
    } catch (e) {
      const errMsg = e instanceof Error ? e.message : String(e);
      LogService.add('error', `❌ BLE write failed for ${cmd}: ${errMsg}`);
      throw new Error(`BLE write failed: ${errMsg}`);
    }
  }

  // ── Proactive ping (keeps Pi _last_rx_time fresh) ────────────────

  private startPingInterval(): void {
    if (this.pingInterval) clearInterval(this.pingInterval);
    // Send a ping every 10s. The pong response is silently discarded in dispatch().
    this.pingInterval = setInterval(() => {
      if (!this.device) return;
      this.writeRx(JSON.stringify({ cmd: 'ping' }) + '\n').catch(() => {});
    }, 10_000);
  }

  // ── Activity Monitoring (Detect Pi timeout on client side) ────────

  private sendHeartbeatAck(): void {
    // Send ACK asynchronously without blocking - fire and forget
    if (!this.device) return;
    
    const ackMsg = JSON.stringify({ type: 'heartbeat_ack' }) + '\n';
    this.writeRx(ackMsg).catch((e) => {
      // Log but don't fail - heartbeat is not critical
      LogService.add('debug', `Could not send heartbeat ACK`);
    });
  }

  private startActivityMonitor(): void {
    if (this.activityMonitorInterval) clearInterval(this.activityMonitorInterval);
    
    this.activityMonitorInterval = setInterval(() => {
      // Only check if still connected
      if (!this.device) return;
      
      const elapsed = Date.now() - this.lastActivityTime;
      
      // Pi timeout: 15 seconds without any message
      if (elapsed > CLIENT_TIMEOUT_MS) {
        LogService.add('error', `Inactivity timeout (${elapsed}ms > ${CLIENT_TIMEOUT_MS}ms). Disconnecting.`);
        this.disconnect().catch(() => {});
      }
    }, INACTIVITY_CHECK_MS);
  }

  // ── Cleanup ──────────────────────────────────────────────────────

  private drainQueue(err: Error): void {
    this.queue.forEach((p) => { clearTimeout(p.timer); p.reject(err); });
    this.queue = [];
  }

  private handleUnexpectedDisconnect(): void {
    const elapsed = Date.now() - this.lastActivityTime;
    LogService.add('warning', `Device disconnected (last activity: ${elapsed}ms ago, monitor: ${this.sampleCbs.size} subscribers)`);
    if (this.pingInterval) {
      clearInterval(this.pingInterval);
      this.pingInterval = null;
    }
    if (this.activityMonitorInterval) {
      clearInterval(this.activityMonitorInterval);
      this.activityMonitorInterval = null;
    }
    this.txSub?.remove();
    this.txSub = null;
    this.rxBuf = '';
    this.device = null;
    this.drainQueue(new Error('Device disconnected unexpectedly'));
  }
}
