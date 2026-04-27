import React from 'react';
import { ScrollView, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { useConnectionStore } from '../../stores/connectionStore';
import { useDashboardStore } from '../../stores/dashboardStore';
import { useVehicleStore } from '../../stores/vehicleStore';
import { VehicleService } from '../../domain/services/VehicleService';
import { colors, fontSize, spacing } from '../../shared/theme';
import { VehicleData } from '../../domain/models/VehicleData';
import { Widget } from '../../domain/models/Widget';
import { BluetoothIcon } from '../../assets/icons/BluetoothIcon';

type DataKey = keyof Omit<VehicleData, 'timestamp'>;

function formatValue(key: DataKey, value: number): string {
  switch (key) {
    case 'rpm':
      return Math.round(value).toLocaleString();
    case 'speed':
      return Math.round(value).toString();
    case 'voltage':
      return value.toFixed(2);
    default:
      return value.toFixed(1);
  }
}

function valueColor(key: DataKey, value: number): string {
  switch (key) {
    case 'rpm':
      if (value > 5500) return colors.error;
      if (value > 3500) return colors.warning;
      return colors.success;
    case 'engineTemp':
      if (value > 100) return colors.error;
      if (value > 90) return colors.warning;
      return colors.primary;
    case 'fuelLevel':
      if (value < 15) return colors.error;
      if (value < 30) return colors.warning;
      return colors.success;
    case 'voltage':
      if (value < 12.0) return colors.error;
      if (value < 12.4) return colors.warning;
      return colors.success;
    default:
      return colors.text;
  }
}

function WidgetCard({ widget, value }: { widget: Widget; value: number }) {
  const color = valueColor(widget.dataKey, value);
  const large = widget.dataKey === 'rpm';
  return (
    <View style={styles.card}>
      <Text style={styles.cardLabel}>{widget.label}</Text>
      <Text style={[styles.cardValue, { color, fontSize: large ? fontSize.xxl : fontSize.xl }]}>
        {formatValue(widget.dataKey, value)}
      </Text>
      <Text style={styles.cardUnit}>{widget.unit}</Text>
    </View>
  );
}

export function DashboardScreen() {
  const { status } = useConnectionStore();
  const { latest, vin, monitoring } = useVehicleStore();
  const { widgets } = useDashboardStore();

  if (status !== 'connected') {
    return (
      <View style={styles.root}>
        <View style={styles.empty}>
          <BluetoothIcon size={64} color={colors.textMuted} />
          <Text style={styles.emptyTitle}>Not connected</Text>
          <Text style={styles.emptyHint}>Go to Connection tab to connect</Text>
        </View>
      </View>
    );
  }

  const visible = [...widgets].filter((w) => w.visible).sort((a, b) => a.order - b.order);

  return (
    <View style={styles.root}>
      <View style={styles.header}>
        <View style={styles.vinRow}>
          <Text style={styles.vinLabel}>VIN</Text>
          <Text style={styles.vinValue} numberOfLines={1}>{vin ?? '—'}</Text>
        </View>
        <TouchableOpacity
          style={[styles.monitorBtn, monitoring ? styles.monitorBtnStop : styles.monitorBtnStart]}
          onPress={monitoring ? VehicleService.stop : VehicleService.start}
          activeOpacity={0.75}
        >
          <Text style={styles.monitorBtnLabel}>{monitoring ? '■  Stop' : '▶  Start'}</Text>
        </TouchableOpacity>
      </View>

      <ScrollView contentContainerStyle={styles.grid}>
        {visible.map((w) => (
          <WidgetCard key={w.id} widget={w} value={latest ? latest[w.dataKey] : 0} />
        ))}
        {visible.length === 0 && (
          <Text style={styles.emptyHint}>No widgets visible — go to Customize to enable some.</Text>
        )}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.background },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    backgroundColor: colors.surface,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  vinRow: { flex: 1, marginRight: spacing.sm },
  vinLabel: {
    fontSize: fontSize.xs,
    color: colors.textMuted,
    textTransform: 'uppercase',
    letterSpacing: 1,
    marginBottom: 2,
  },
  vinValue: { fontSize: fontSize.sm, color: colors.textSecondary, fontFamily: 'monospace' },
  monitorBtn: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs + 2,
    borderRadius: 8,
    minWidth: 90,
    alignItems: 'center',
  },
  monitorBtnStart: { backgroundColor: colors.success },
  monitorBtnStop:  { backgroundColor: colors.error },
  monitorBtnLabel: { fontSize: fontSize.sm, fontWeight: '700', color: colors.background },
  grid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    padding: spacing.sm,
  },
  card: {
    width: '48%',
    margin: '1%',
    backgroundColor: colors.surface,
    borderRadius: 12,
    padding: spacing.md,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: colors.border,
    minHeight: 120,
  },
  cardLabel: {
    fontSize: fontSize.xs,
    color: colors.textSecondary,
    textTransform: 'uppercase',
    letterSpacing: 1.2,
    marginBottom: spacing.xs,
  },
  cardValue: { fontWeight: '700' },
  cardUnit: { fontSize: fontSize.xs, color: colors.textMuted, marginTop: spacing.xs },
  empty: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: spacing.xl },
  emptyTitle: { fontSize: fontSize.lg, color: colors.textSecondary, marginBottom: spacing.sm },
  emptyHint: { fontSize: fontSize.sm, color: colors.textMuted, textAlign: 'center' },
});
