import { create } from 'zustand';
import { ConnectionService } from '../domain/services/ConnectionService';
import { LogService } from '../domain/services/LogService';

export type ConnectionStatus = 'disconnected' | 'scanning' | 'connecting' | 'connected';

interface ConnectionState {
  status: ConnectionStatus;
  deviceName: string | null;
  error: string | null;
  connect: () => Promise<void>;
  disconnect: () => Promise<void>;
}

export const useConnectionStore = create<ConnectionState>((set) => ({
  status: 'disconnected',
  deviceName: null,
  error: null,

  connect: async () => {
    set({ status: 'scanning', error: null });
    try {
      const deviceName = await ConnectionService.connect((phase) => {
        set({ status: phase });
      });
      set({ status: 'connected', deviceName });
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Connection failed';
      set({ status: 'disconnected', error: msg });
      LogService.add('error', `Connection failed: ${msg}`);
    }
  },

  disconnect: async () => {
    await ConnectionService.disconnect();
    set({ status: 'disconnected', deviceName: null });
  },
}));
