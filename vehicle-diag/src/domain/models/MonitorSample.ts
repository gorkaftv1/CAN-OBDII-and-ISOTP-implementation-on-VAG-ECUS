export interface MonitorSample {
  type: 'sample' | 'error';
  pid: number;
  name: string;
  value?: number;
  unit?: string;
  ts?: number;
  message?: string;
}
