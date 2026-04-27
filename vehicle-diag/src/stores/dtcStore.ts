import { create } from 'zustand';
import { DtcCode } from '../domain/models/DtcCode';
import { getAdapter } from '../infrastructure/adapterFactory';
import { LogService } from '../domain/services/LogService';

interface DtcState {
  codes: DtcCode[];
  loading: boolean;
  clearing: boolean;
  error: string | null;
  lastFetched: number | null;
  fetch: () => Promise<void>;
  clear: () => Promise<void>;
}

export const useDtcStore = create<DtcState>((set) => ({
  codes: [],
  loading: false,
  clearing: false,
  error: null,
  lastFetched: null,

  fetch: async () => {
    set({ loading: true, error: null });
    try {
      const raw = await getAdapter().fetchDtcs();
      const codes: DtcCode[] = raw.map((d) => ({ ...d, timestamp: Date.now() }));
      set({ codes, loading: false, lastFetched: Date.now() });
      LogService.add('info', `DTC scan: ${codes.length} fault code(s) found`);
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Scan failed';
      set({ loading: false, error: msg });
      LogService.add('error', `DTC scan failed: ${msg}`);
    }
  },

  clear: async () => {
    set({ clearing: true, error: null });
    try {
      await getAdapter().clearDtcs();
      set({ codes: [], clearing: false, lastFetched: Date.now() });
      LogService.add('info', 'DTCs cleared');
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Clear failed';
      set({ clearing: false, error: msg });
      LogService.add('error', `DTC clear failed: ${msg}`);
    }
  },
}));
