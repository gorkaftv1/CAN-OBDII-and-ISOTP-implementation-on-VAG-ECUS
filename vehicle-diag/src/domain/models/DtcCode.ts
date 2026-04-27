export interface DtcCode {
  code: string;
  description: string;
  severity: 'info' | 'warning' | 'error';
  timestamp: number;
}
