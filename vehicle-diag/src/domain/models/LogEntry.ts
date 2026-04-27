export type LogType = 'data' | 'command' | 'error' | 'info';

export interface LogEntry {
  id: string;
  type: LogType;
  content: string;
  timestamp: number;
}
