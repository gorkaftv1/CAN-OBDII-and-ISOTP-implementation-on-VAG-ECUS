import { create } from 'zustand';
import { LogEntry } from '../domain/models/LogEntry';

const MAX_ENTRIES = 500;
const MAX_CONSOLE = 1000;

interface LogsState {
  entries: LogEntry[];
  consoleLines: string[];
  addEntry: (entry: LogEntry) => void;
  addConsoleLine: (line: string) => void;
  clearConsole: () => void;
  clearLogs: () => void;
}

export const useLogsStore = create<LogsState>((set, get) => ({
  entries: [],
  consoleLines: [],

  addEntry: (entry) => {
    const { entries } = get();
    set({
      entries:
        entries.length >= MAX_ENTRIES
          ? [...entries.slice(-(MAX_ENTRIES - 1)), entry]
          : [...entries, entry],
    });
  },

  addConsoleLine: (line) => {
    const { consoleLines } = get();
    set({
      consoleLines:
        consoleLines.length >= MAX_CONSOLE
          ? [...consoleLines.slice(-(MAX_CONSOLE - 1)), line]
          : [...consoleLines, line],
    });
  },

  clearConsole: () => set({ consoleLines: [] }),
  clearLogs: () => set({ entries: [] }),
}));
