import React, { useEffect } from 'react';
import {
  FlatList,
  ListRenderItem,
  StyleSheet,
  Switch,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { useDashboardStore } from '../../stores/dashboardStore';
import { Widget } from '../../domain/models/Widget';
import { colors, fontSize, spacing } from '../../shared/theme';

function WidgetRow({
  item,
  index,
  total,
  onToggle,
  onUp,
  onDown,
}: {
  item: Widget;
  index: number;
  total: number;
  onToggle: (id: string) => void;
  onUp: (id: string) => void;
  onDown: (id: string) => void;
}) {
  return (
    <View style={styles.row}>
      <Switch
        value={item.visible}
        onValueChange={() => onToggle(item.id)}
        trackColor={{ false: colors.border, true: colors.primary + '88' }}
        thumbColor={item.visible ? colors.primary : colors.textMuted}
      />
      <View style={styles.rowInfo}>
        <Text style={[styles.rowLabel, !item.visible && styles.rowLabelDim]}>{item.label}</Text>
        <Text style={styles.rowUnit}>{item.unit}</Text>
      </View>
      <View style={styles.arrows}>
        <TouchableOpacity
          style={[styles.arrowBtn, index === 0 && styles.arrowBtnDim]}
          onPress={() => onUp(item.id)}
          disabled={index === 0}
          hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
        >
          <Text style={styles.arrowText}>▲</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.arrowBtn, index === total - 1 && styles.arrowBtnDim]}
          onPress={() => onDown(item.id)}
          disabled={index === total - 1}
          hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
        >
          <Text style={styles.arrowText}>▼</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
}

export function CustomizeScreen() {
  const { widgets, loaded, toggleWidget, moveUp, moveDown, loadFromStorage } = useDashboardStore();

  useEffect(() => {
    if (!loaded) void loadFromStorage();
  }, [loaded]);

  const sorted = [...widgets].sort((a, b) => a.order - b.order);

  const renderItem: ListRenderItem<Widget> = ({ item, index }) => (
    <WidgetRow
      item={item}
      index={index}
      total={sorted.length}
      onToggle={toggleWidget}
      onUp={moveUp}
      onDown={moveDown}
    />
  );

  return (
    <View style={styles.root}>
      <Text style={styles.hint}>Toggle visibility and reorder dashboard widgets.</Text>
      <FlatList
        data={sorted}
        renderItem={renderItem}
        keyExtractor={(item) => item.id}
        style={styles.list}
        contentContainerStyle={styles.listContent}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.background },
  hint: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    textAlign: 'center',
    padding: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  list: { flex: 1 },
  listContent: { padding: spacing.md, gap: spacing.sm },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderRadius: 10,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
  },
  rowInfo: { flex: 1, marginLeft: spacing.sm },
  rowLabel: { fontSize: fontSize.md, color: colors.text, fontWeight: '500' },
  rowLabelDim: { color: colors.textMuted },
  rowUnit: { fontSize: fontSize.xs, color: colors.textSecondary, marginTop: 2 },
  arrows: { flexDirection: 'row', gap: spacing.xs },
  arrowBtn: {
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
    borderRadius: 6,
    backgroundColor: colors.surfaceElevated,
    borderWidth: 1,
    borderColor: colors.border,
  },
  arrowBtnDim: { opacity: 0.25 },
  arrowText: { color: colors.text, fontSize: fontSize.sm },
});
