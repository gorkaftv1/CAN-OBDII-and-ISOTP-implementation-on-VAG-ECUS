import React, { useEffect, useRef } from 'react';
import {
  ActivityIndicator,
  Alert,
  Animated,
  FlatList,
  ListRenderItem,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { useConnectionStore } from '../../stores/connectionStore';
import { useDtcStore } from '../../stores/dtcStore';
import { DtcCode } from '../../domain/models/DtcCode';
import { LogService } from '../../domain/services/LogService';
import { colors, fontSize, spacing } from '../../shared/theme';
import { format } from 'date-fns';
import { SearchIcon } from '../../assets/icons/SearchIcon';
import { CheckIcon } from '../../assets/icons/CheckIcon';
import { BluetoothIcon } from '../../assets/icons/BluetoothIcon';
import { WarningIcon } from '../../assets/icons/WarningIcon';

const SEVERITY_COLOR: Record<DtcCode['severity'], string> = {
  error: colors.error,
  warning: colors.warning,
  info: colors.textSecondary,
};

const SEVERITY_LABEL: Record<DtcCode['severity'], string> = {
  error: 'CRITICAL',
  warning: 'WARNING',
  info: 'INFO',
};

function DtcRow({ item }: { item: DtcCode }) {
  const color = SEVERITY_COLOR[item.severity];
  return (
    <View style={styles.row}>
      <View style={[styles.severityBar, { backgroundColor: color }]} />
      <View style={styles.rowBody}>
        <View style={styles.rowHeader}>
          <Text style={[styles.code, { color }]}>{item.code}</Text>
          <View style={[styles.badge, { borderColor: color, backgroundColor: color + '22' }]}>
            <Text style={[styles.badgeText, { color }]}>{SEVERITY_LABEL[item.severity]}</Text>
          </View>
        </View>
        <Text style={styles.description}>{item.description}</Text>
        <Text style={styles.timestamp}>
          Detected {format(item.timestamp, 'HH:mm:ss · dd MMM yyyy')}
        </Text>
      </View>
    </View>
  );
}

function EmptyState({ scanned }: { scanned: boolean }) {
  return (
    <View style={styles.emptyWrap}>
      {scanned ? (
        <CheckIcon size={64} color={colors.success} />
      ) : (
        <SearchIcon size={64} color={colors.primary} />
      )}
      <Text style={styles.emptyTitle}>
        {scanned ? 'No fault codes detected' : 'Tap Scan to read fault codes'}
      </Text>
      <Text style={styles.emptyHint}>
        {scanned
          ? 'Vehicle systems are reporting no faults.'
          : 'The scan queries the vehicle ECU for stored diagnostic trouble codes.'}
      </Text>
    </View>
  );
}

export function DtcScreen() {
  const { status } = useConnectionStore();
  const { codes, loading, clearing, error, lastFetched, fetch, clear } = useDtcStore();

  const shakeAnim = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    if (error) {
      Animated.sequence([
        Animated.timing(shakeAnim, { toValue: 8, duration: 60, useNativeDriver: true }),
        Animated.timing(shakeAnim, { toValue: -8, duration: 60, useNativeDriver: true }),
        Animated.timing(shakeAnim, { toValue: 6, duration: 60, useNativeDriver: true }),
        Animated.timing(shakeAnim, { toValue: 0, duration: 60, useNativeDriver: true }),
      ]).start();
    }
  }, [error]);

  function handleClear() {
    if (codes.length === 0) return;
    Alert.alert(
      'Clear fault codes?',
      'This will erase all stored DTCs from the vehicle ECU. This action cannot be undone.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Clear all',
          style: 'destructive',
          onPress: () => {
            LogService.add('info', 'Sending clear DTCs command...');
            clear();
          },
        },
      ],
    );
  }

  if (status !== 'connected') {
    return (
      <View style={styles.root}>
        <View style={styles.emptyWrap}>
          <BluetoothIcon size={64} color={colors.textMuted} />
          <Text style={styles.emptyTitle}>Not connected</Text>
          <Text style={styles.emptyHint}>Connect to an OBD2 adapter to read fault codes.</Text>
        </View>
      </View>
    );
  }

  const renderItem: ListRenderItem<DtcCode> = ({ item }) => <DtcRow item={item} />;

  const errorCount = codes.filter((c) => c.severity === 'error').length;
  const warnCount = codes.filter((c) => c.severity === 'warning').length;

  return (
    <View style={styles.root}>
      {/* ── Toolbar ── */}
      <View style={styles.toolbar}>
        <View style={styles.toolbarLeft}>
          {codes.length > 0 && (
            <>
              {errorCount > 0 && (
                <View style={[styles.chip, { borderColor: colors.error }]}>
                  <Text style={[styles.chipText, { color: colors.error }]}>
                    {errorCount} critical
                  </Text>
                </View>
              )}
              {warnCount > 0 && (
                <View style={[styles.chip, { borderColor: colors.warning }]}>
                  <Text style={[styles.chipText, { color: colors.warning }]}>
                    {warnCount} warning
                  </Text>
                </View>
              )}
            </>
          )}
          {lastFetched && codes.length === 0 && (
            <Text style={styles.noFaultsLabel}>No faults</Text>
          )}
        </View>

        <View style={styles.toolbarRight}>
          <TouchableOpacity
            style={[styles.btn, styles.btnClear, codes.length === 0 && styles.btnDisabled]}
            onPress={handleClear}
            disabled={clearing || codes.length === 0}
            activeOpacity={0.75}
          >
            {clearing ? (
              <ActivityIndicator size="small" color={colors.error} />
            ) : (
              <Text style={[styles.btnText, { color: colors.error }]}>Clear</Text>
            )}
          </TouchableOpacity>

          <TouchableOpacity
            style={[styles.btn, styles.btnScan, loading && styles.btnDisabled]}
            onPress={fetch}
            disabled={loading}
            activeOpacity={0.75}
          >
            {loading ? (
              <ActivityIndicator size="small" color={colors.background} />
            ) : (
              <Text style={[styles.btnText, { color: colors.background }]}>Scan</Text>
            )}
          </TouchableOpacity>
        </View>
      </View>

      {/* ── Error banner ── */}
      {error ? (
        <Animated.View
          style={[styles.errorBanner, { transform: [{ translateX: shakeAnim }] }]}
        >
          <WarningIcon size={20} color={colors.error} />
          <Text style={styles.errorBannerText}>{error}</Text>
        </Animated.View>
      ) : null}

      {/* ── List ── */}
      <FlatList
        data={codes}
        renderItem={renderItem}
        keyExtractor={(item) => item.code}
        style={styles.list}
        contentContainerStyle={codes.length === 0 ? styles.listEmpty : styles.listContent}
        ListEmptyComponent={<EmptyState scanned={lastFetched !== null} />}
        ItemSeparatorComponent={() => <View style={styles.separator} />}
      />

      {/* ── Last scanned ── */}
      {lastFetched ? (
        <Text style={styles.lastScanned}>
          Last scan: {format(lastFetched, 'HH:mm:ss · dd MMM yyyy')}
        </Text>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.background },

  toolbar: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    backgroundColor: colors.surface,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
    gap: spacing.sm,
  },
  toolbarLeft: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs, flex: 1 },
  toolbarRight: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },

  chip: {
    paddingHorizontal: spacing.sm,
    paddingVertical: 3,
    borderRadius: 20,
    borderWidth: 1,
  },
  chipText: { fontSize: fontSize.xs, fontWeight: '600' },
  noFaultsLabel: { fontSize: fontSize.sm, color: colors.success },

  btn: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs + 2,
    borderRadius: 7,
    minWidth: 68,
    alignItems: 'center',
    justifyContent: 'center',
  },
  btnScan: { backgroundColor: colors.primary },
  btnClear: { borderWidth: 1, borderColor: colors.error },
  btnDisabled: { opacity: 0.4 },
  btnText: { fontSize: fontSize.sm, fontWeight: '600' },

  errorBanner: {
    backgroundColor: colors.error + '22',
    borderBottomWidth: 1,
    borderBottomColor: colors.error,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
  },
  errorBannerText: { color: colors.error, fontSize: fontSize.sm },

  list: { flex: 1 },
  listContent: { paddingVertical: spacing.sm },
  listEmpty: { flex: 1 },

  separator: {
    height: StyleSheet.hairlineWidth,
    backgroundColor: colors.border,
    marginLeft: spacing.md + 4,
  },

  row: {
    flexDirection: 'row',
    backgroundColor: colors.surface,
    marginHorizontal: spacing.md,
    marginVertical: spacing.xs,
    borderRadius: 10,
    overflow: 'hidden',
    borderWidth: 1,
    borderColor: colors.border,
  },
  severityBar: { width: 4 },
  rowBody: { flex: 1, padding: spacing.md },
  rowHeader: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, marginBottom: spacing.xs },
  code: { fontSize: fontSize.lg, fontWeight: '700', fontVariant: ['tabular-nums'] },
  badge: {
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
    borderWidth: 1,
  },
  badgeText: { fontSize: 9, fontWeight: '700', letterSpacing: 0.8 },
  description: { fontSize: fontSize.sm, color: colors.text, lineHeight: 20, marginBottom: spacing.xs },
  timestamp: { fontSize: fontSize.xs, color: colors.textMuted },

  emptyWrap: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: spacing.xl },
  emptyTitle: { fontSize: fontSize.md, color: colors.text, fontWeight: '600', marginBottom: spacing.sm, textAlign: 'center' },
  emptyHint: { fontSize: fontSize.sm, color: colors.textMuted, textAlign: 'center', lineHeight: 20 },

  lastScanned: {
    fontSize: fontSize.xs,
    color: colors.textMuted,
    textAlign: 'center',
    paddingVertical: spacing.sm,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.border,
  },
});
