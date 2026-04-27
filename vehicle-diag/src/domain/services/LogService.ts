import uuid from 'react-native-uuid';
import { LogType } from '../models/LogEntry';
import { useLogsStore } from '../../stores/logsStore';

export class LogService {
  static add(type: LogType, content: string): void {
    useLogsStore.getState().addEntry({
      id: uuid.v4() as string,
      type,
      content,
      timestamp: Date.now(),
    });
  }
}
