/**
 * DashboardScreen — Pantalla 3: dashboard principal con datos en tiempo real.
 *
 * Arranca el monitor live al montar y lo para al desmontar.
 * Muestra 5 gauges principales + grid de PIDs secundarios.
 */

import React from 'react';
import {
  View,
  Text,
  ScrollView,
  TouchableOpacity,
  StyleSheet,
  SafeAreaView,
} from 'react-native';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { GaugeCard } from '../components/GaugeCard';
import { ConnectionBadge } from '../components/ConnectionBadge';
import { useLiveData } from '../hooks/useLiveData';
import { bluetoothService } from '../services/BluetoothService';
import type { RootStackParamList } from '../types';

type Nav = NativeStackNavigationProp<RootStackParamList, 'Dashboard'>;

// PIDs principales (fila grande) y secundarios (grid)
const MAIN_PIDS = [0x0C, 0x0D, 0x05]; // RPM, Speed, Coolant
const SECONDARY_PIDS = [0x04, 0x11, 0x0E, 0x0F, 0x10, 0x42, 0x2F, 0x5C];
const ALL_PIDS = [...MAIN_PIDS, ...SECONDARY_PIDS];

function placeholder(pid: number) {
  return { pid, name: `PID 0x${pid.toString(16).toUpperCase()}`, value: 0, unit: '?', ts: 0 };
}

export function DashboardScreen() {
  const navigation = useNavigation<Nav>();
  const { samples } = useLiveData(ALL_PIDS, 500);

  function sample(pid: number) {
    return samples.get(pid) ?? placeholder(pid);
  }

  return (
    <SafeAreaView style={styles.safe}>
      <View style={styles.header}>
        <Text style={styles.headerTitle}>SEAT Ibiza 6J</Text>
        <ConnectionBadge connected={bluetoothService.isConnected()} deviceName="SEAT_DIAG_PI" />
      </View>

      <ScrollView contentContainerStyle={styles.scroll}>
        {/* ── Gauges principales ── */}
        <View style={styles.mainRow}>
          {MAIN_PIDS.map(pid => {
            const s = sample(pid);
            return <GaugeCard key={pid} name={s.name} value={s.value} unit={s.unit} />;
          })}
        </View>

        {/* ── Gauges secundarios ── */}
        <Text style={styles.sectionTitle}>PARÁMETROS EXTENDIDOS</Text>
        <View style={styles.grid}>
          {SECONDARY_PIDS.map(pid => {
            const s = sample(pid);
            return (
              <GaugeCard key={pid} name={s.name} value={s.value} unit={s.unit} compact />
            );
          })}
        </View>

        {/* ── Botones de acción ── */}
        <View style={styles.actionRow}>
          <TouchableOpacity
            style={styles.actionButton}
            onPress={() => navigation.navigate('Dtc')}
          >
            <Text style={styles.actionButtonText}>DTCs</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={styles.actionButton}
            onPress={() => navigation.navigate('History')}
          >
            <Text style={styles.actionButtonText}>Historial</Text>
          </TouchableOpacity>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: '#121212' },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#2A2A2A',
  },
  headerTitle: { color: '#FFF', fontSize: 18, fontWeight: 'bold' },
  scroll: { padding: 10, paddingBottom: 30 },
  mainRow: { flexDirection: 'row', marginBottom: 16 },
  sectionTitle: {
    color: '#555',
    fontSize: 11,
    letterSpacing: 1,
    marginBottom: 8,
    marginLeft: 6,
  },
  grid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    marginBottom: 20,
  },
  actionRow: {
    flexDirection: 'row',
    gap: 12,
  },
  actionButton: {
    flex: 1,
    backgroundColor: '#1565C0',
    borderRadius: 10,
    padding: 14,
    alignItems: 'center',
  },
  actionButtonText: { color: '#FFF', fontSize: 15, fontWeight: '600' },
});
