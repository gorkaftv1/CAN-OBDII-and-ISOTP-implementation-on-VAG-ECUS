import { useEffect, useRef, useState } from 'react';
import { MonitorSample } from '../types';
import { DiagService } from '../services/DiagService';

const DEFAULT_PIDS = [0x0C, 0x0D, 0x05, 0x04, 0x11]; // RPM, Speed, Coolant, Load, Throttle
const DEFAULT_INTERVAL_MS = 500;

/**
 * Hook que arranca el monitor live en la Pi y mantiene un Map con
 * la última muestra por PID. Al desmontar el componente, para el monitor.
 */
export function useLiveData(
  pids: number[] = DEFAULT_PIDS,
  intervalMs: number = DEFAULT_INTERVAL_MS,
) {
  const [samples, setSamples] = useState<Map<number, MonitorSample>>(new Map());
  const [isMonitoring, setIsMonitoring] = useState(false);
  const unsubRef = useRef<(() => void) | null>(null);

  useEffect(() => {
    setIsMonitoring(true);
    unsubRef.current = DiagService.startMonitor(pids, intervalMs, sample => {
      setSamples(prev => new Map(prev).set(sample.pid, sample));
    });

    return () => {
      unsubRef.current?.();
      DiagService.stopMonitor();
      setIsMonitoring(false);
    };
  }, []);

  return { samples, isMonitoring };
}
