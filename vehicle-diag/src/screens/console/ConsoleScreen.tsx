import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  FlatList,
  ListRenderItem,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { useLogsStore } from '../../stores/logsStore';
import { colors, fontSize, monoFont, spacing } from '../../shared/theme';
import { DownArrowIcon } from '../../assets/icons/DownArrowIcon';
import { PauseIcon } from '../../assets/icons/PauseIcon';

function Line({ text }: { text: string }) {
  const isErr = text.includes('[ERR]');
  const isTx = text.includes('[TX]');
  return (
    <Text
      style={[
        styles.line,
        isErr && styles.lineErr,
        isTx && styles.lineTx,
      ]}
    >
      {text}
    </Text>
  );
}

export function ConsoleScreen() {
  const consoleLines = useLogsStore((s) => s.consoleLines);
  const clearConsole = useLogsStore((s) => s.clearConsole);
  const listRef = useRef<FlatList<string>>(null);
  const [autoScroll, setAutoScroll] = useState(true);

  useEffect(() => {
    if (autoScroll && consoleLines.length > 0) {
      listRef.current?.scrollToEnd({ animated: false });
    }
  }, [consoleLines.length, autoScroll]);

  const renderItem: ListRenderItem<string> = useCallback(
    ({ item }) => <Line text={item} />,
    [],
  );

  const keyExtractor = useCallback((_: string, i: number) => String(i), []);

  return (
    <View style={styles.root}>
      <View style={styles.toolbar}>
        <Text style={styles.lineCount}>{consoleLines.length} lines</Text>
        <View style={styles.toolbarRight}>
          <TouchableOpacity
            style={[styles.autoScrollBtn, autoScroll && styles.autoScrollBtnActive]}
            onPress={() => setAutoScroll(!autoScroll)}
            activeOpacity={0.7}
          >
            {autoScroll ? (
              <DownArrowIcon size={16} color={colors.success} />
            ) : (
              <PauseIcon size={16} color={colors.textSecondary} />
            )}
            <Text style={[styles.autoScrollLabel, autoScroll && styles.autoScrollLabelActive]}>
              {autoScroll ? 'Auto' : 'Manual'}
            </Text>
          </TouchableOpacity>
          <TouchableOpacity style={styles.clearBtn} onPress={clearConsole} activeOpacity={0.7}>
            <Text style={styles.clearLabel}>Clear</Text>
          </TouchableOpacity>
        </View>
      </View>

      {consoleLines.length === 0 ? (
        <View style={styles.empty}>
          <Text style={styles.emptyText}>Waiting for frames…</Text>
        </View>
      ) : (
        <FlatList
          ref={listRef}
          data={consoleLines}
          renderItem={renderItem}
          keyExtractor={keyExtractor}
          style={styles.list}
          contentContainerStyle={styles.listContent}
          onContentSizeChange={() => autoScroll && listRef.current?.scrollToEnd({ animated: false })}
          initialNumToRender={60}
          maxToRenderPerBatch={60}
          windowSize={8}
          removeClippedSubviews
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#000' },
  toolbar: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    backgroundColor: colors.surface,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  lineCount: { color: colors.textSecondary, fontSize: fontSize.sm },
  toolbarRight: {
    flexDirection: 'row',
    gap: spacing.sm,
    alignItems: 'center',
  },
  autoScrollBtn: {
    paddingHorizontal: spacing.md,
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
    paddingVertical: spacing.xs,
    borderRadius: 4,
    borderWidth: 1,
    borderColor: colors.textSecondary,
    backgroundColor: 'transparent',
  },
  autoScrollBtnActive: {
    borderColor: colors.success,
    backgroundColor: colors.success + '20',
  },
  autoScrollLabel: {
    color: colors.textSecondary,
    fontSize: fontSize.sm,
  },
  autoScrollLabelActive: {
    color: colors.success,
    fontWeight: '600',
  },
  clearBtn: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
    borderRadius: 4,
    borderWidth: 1,
    borderColor: colors.error,
  },
  clearLabel: { color: colors.error, fontSize: fontSize.sm },
  list: { flex: 1 },
  listContent: { paddingHorizontal: spacing.sm, paddingVertical: spacing.xs },
  line: {
    fontFamily: monoFont,
    fontSize: 12,
    color: colors.success,
    lineHeight: 19,
    paddingVertical: 1,
  },
  lineErr: { color: colors.error },
  lineTx: { color: colors.warning },
  empty: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  emptyText: { color: colors.textMuted, fontSize: fontSize.sm },
});
