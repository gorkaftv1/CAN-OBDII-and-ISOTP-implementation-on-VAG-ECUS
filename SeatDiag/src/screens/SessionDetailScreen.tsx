/**
 * SessionDetailScreen — Pantalla 6: detalle de sesión con gráficas temporales.
 */

import React, { useEffect, useState } from 'react';
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  ActivityIndicator,
  Dimensions,
  SafeAreaView,
} from 'react-native';
import { useRoute } from '@react-navigation/native';
import type { RouteProp } from '@react-navigation/native';
import { LineChart } from 'react-native-chart-kit';
import { DiagService } from '../services/DiagService';
import type { MonitorSample, RootStackParamList } from '../types';

type Route = RouteProp<RootStackParamList, 'SessionDetail'>;

const CHART_W = Dimensions.get('window').width - 32;

// PIDs a mostrar en gráficas (los más relevantes)
const CHART_PIDS: { pid: number; label: string; color: string }[] = [
  { pid: 0x0C, label: 'RPM', color: '#90CAF9' },
  { pid: 0x05, label: 'Coolant °C', color: '#EF9A9A' },
  { pid: 0x0D, label: 'Speed km/h', color: '#A5D6A7' },
  { pid: 0x04, label: 'Engine Load %', color: '#FFE082' },
];

const CHART_CONFIG = {
  backgroundColor: '#1E1E1E',
  backgroundGradientFrom: '#1E1E1E',
  backgroundGradientTo: '#1E1E1E',
  decimalPlaces: 0,
  color: (opacity = 1) => `rgba(144, 202, 249, ${opacity})`,
  labelColor: () => '#777',
  style: { borderRadius: 10 },
};

function PidChart({
  samples,
  label,
  color,
}: {
  samples: MonitorSample[];
  label: string;
  color: string;
}) {
  if (samples.length < 2) {
    return (
      <View style={styles.chartEmpty}>
        <Text style={styles.chartLabel}>{label}</Text>
        <Text style={styles.noData}>Sin datos suficientes</Text>
      </View>
    );
  }

  const values = samples.map(s => s.value);
  // Mostrar máx 50 puntos para no saturar
  const step = Math.max(1, Math.floor(values.length / 50));
  const data = values.filter((_, i) => i % step === 0);

  return (
    <View style={styles.chartContainer}>
      <Text style={styles.chartLabel}>{label}</Text>
      <LineChart
        data={{
          labels: [],
          datasets: [{ data, color: () => color, strokeWidth: 2 }],
        }}
        width={CHART_W}
        height={140}
        chartConfig={{ ...CHART_CONFIG, color: () => color }}
        withDots={false}
        withInnerLines={false}
        bezier
        style={styles.chart}
      />
    </View>
  );
}

export function SessionDetailScreen() {
  const route = useRoute<Route>();
  const { session } = route.params;

  const [samplesByPid, setSamplesByPid] = useState<Map<number, MonitorSample[]>>(new Map());
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      const map = new Map<number, MonitorSample[]>();
      for (const { pid } of CHART_PIDS) {
        const samples = await DiagService.getSessionSamples(session.session_id, pid, 500);
        if (samples.length > 0) {
          map.set(pid, samples);
        }
      }
      setSamplesByPid(map);
      setLoading(false);
    }
    load();
  }, [session.session_id]);

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color="#1565C0" size="large" />
      </View>
    );
  }

  return (
    <SafeAreaView style={styles.safe}>
      <ScrollView contentContainerStyle={styles.scroll}>
        <Text style={styles.title}>{session.label || `Sesión #${session.session_id}`}</Text>
        <Text style={styles.meta}>
          Inicio: {session.started_at}
          {session.ended_at ? `\nFin:    ${session.ended_at}` : '  (activa)'}
        </Text>
        <Text style={styles.meta}>{session.sample_count} muestras totales</Text>

        {CHART_PIDS.map(({ pid, label, color }) => (
          <PidChart
            key={pid}
            samples={samplesByPid.get(pid) ?? []}
            label={label}
            color={color}
          />
        ))}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: '#121212' },
  center: { flex: 1, backgroundColor: '#121212', justifyContent: 'center', alignItems: 'center' },
  scroll: { padding: 16 },
  title: { color: '#FFF', fontSize: 20, fontWeight: 'bold', marginBottom: 4 },
  meta: { color: '#888', fontSize: 13, marginBottom: 12 },
  chartContainer: { marginBottom: 20 },
  chartLabel: { color: '#CCC', fontSize: 13, fontWeight: '600', marginBottom: 6 },
  chart: { borderRadius: 10 },
  chartEmpty: { marginBottom: 20 },
  noData: { color: '#555', fontSize: 12 },
});
