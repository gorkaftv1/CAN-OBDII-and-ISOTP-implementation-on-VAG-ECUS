import { useState, useCallback } from 'react';
import { DtcItem } from '../types';
import { DiagService } from '../services/DiagService';

/** Hook para operaciones diagnósticas: DTCs y VIN. */
export function useDiagnostics() {
  const [dtcs, setDtcs] = useState<DtcItem[]>([]);
  const [vin, setVin] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const readDtcs = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await DiagService.getDtcs();
      setDtcs(result);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  const clearDtcs = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      await DiagService.clearDtcs();
      setDtcs([]);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  const readVin = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await DiagService.getVin();
      setVin(result);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  return { dtcs, vin, loading, error, readDtcs, clearDtcs, readVin };
}
