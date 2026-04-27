import React, { useCallback, useMemo, useState } from 'react';
import {
  FlatList,
  ListRenderItem,
  Platform,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { useLogsStore } from '../../stores/logsStore';
import { LogEntry, LogType } from '../../domain/models/LogEntry';
import { colors, fontSize, spacing } from '../../shared/theme';

type Filter = 'all' | LogType;

const FILTERS: Filter[] = ['all', 'data', 'command', 'error', 'info'];

const TYPE_COLOR: Record<LogType, string> = {
  data: colors.primary,
  command: colors.warning,
  error: colors.error,
  info: colors.textSecondary,
};

function pad(n: number, z = 2) {
  return n.toString().padStart(z, '0');
}

function fmtTime(ts: number): string {
  const d = new Date(ts);
  return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}.${pad(d.getMilliseconds(), 3)}`;
}

function EntryRow({ entry }: { entry: LogEntry }) {
  const color = TYPE_COLOR[entry.type];
  return (
    <View style={styles.row}>
      <Text style={styles.ts}>{fmtTime(entry.timestamp)}</Text>
      <View style={[styles.badge, { borderColor: color, backgroundColor: color + '22' }]}>
        <Text style={[styles.badgeText, { color }]}>{entry.type.toUpperCase()}</Text>
      </View>
      <Text style={styles.content} numberOfLines={3}>
        {entry.content}
      </Text>
    </View>
  );
}

export function LogsScreen() {
  const entries = useLogsStore((s) => s.entries);
  const [filter, setFilter] = useState<Filter>('all');

  const filtered = useMemo(
    () => (filter === 'all' ? entries : entries.filter((e) => e.type === filter)),
    [entries, filter],
  );

  const renderItem: ListRenderItem<LogEntry> = useCallback(
    ({ item }) => <EntryRow entry={item} />,
    [],
  );

  return (
    <View style={styles.root}>
      <View style={styles.filterBar}>
        {FILTERS.map((f) => (
          <TouchableOpacity
            key={f}
            style={[styles.filterBtn, filter === f && styles.filterBtnActive]}
            onPress={() => setFilter(f)}
          >
            <Text style={[styles.filterLabel, filter === f && styles.filterLabelActive]}>
              {f === 'all' ? 'All' : f.charAt(0).toUpperCase() + f.slice(1)}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      <Text style={styles.count}>{filtered.length} entries</Text>

      <FlatList
        data={filtered}
        renderItem={renderItem}
        keyExtractor={(item) => item.id}
        style={styles.list}
        inverted
        initialNumToRender={40}
        maxToRenderPerBatch={40}
        windowSize={8}
        removeClippedSubviews
        ListEmptyComponent={<Text style={styles.emptyText}>No log entries</Text>}
      />
    </View>
  );
}

const monoFont = Platform.select({ ios: 'Courier', android: 'monospace', default: 'monospace' });

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.background },
  filterBar: {
    flexDirection: 'row',
    backgroundColor: colors.surface,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
    padding: spacing.sm,
    gap: spacing.xs,
  },
  filterBtn: {
    flex: 1,
    paddingVertical: spacing.xs,
    borderRadius: 5,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: colors.border,
  },
  filterBtnActive: { borderColor: colors.primary, backgroundColor: colors.primary + '1a' },
  filterLabel: { fontSize: fontSize.xs, color: colors.textSecondary },
  filterLabelActive: { color: colors.primary, fontWeight: '600' },
  count: {
    fontSize: fontSize.xs,
    color: colors.textMuted,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
  },
  list: { flex: 1 },
  row: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.border,
  },
  ts: {
    fontFamily: monoFont,
    fontSize: 10,
    color: colors.textMuted,
    marginRight: spacing.xs,
    minWidth: 84,
    paddingTop: 2,
  },
  badge: {
    paddingHorizontal: 5,
    paddingVertical: 2,
    borderRadius: 4,
    borderWidth: 1,
    marginRight: spacing.xs,
    alignSelf: 'flex-start',
  },
  badgeText: { fontSize: 9, fontWeight: '700', letterSpacing: 0.5 },
  content: { flex: 1, fontSize: fontSize.xs, color: colors.text, lineHeight: 17 },
  emptyText: {
    textAlign: 'center',
    color: colors.textMuted,
    padding: spacing.xl,
    fontSize: fontSize.sm,
  },
});
