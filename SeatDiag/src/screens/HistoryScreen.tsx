/**
 * HistoryScreen — Pantalla 5: lista de sesiones diagnósticas pasadas.
 */

import React, { useEffect, useState } from 'react';
import {
  View,
  Text,
  FlatList,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  SafeAreaView,
} from 'react-native';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { DiagService } from '../services/DiagService';
import type { LogSession, RootStackParamList } from '../types';

type Nav = NativeStackNavigationProp<RootStackParamList, 'History'>;

export function HistoryScreen() {
  const navigation = useNavigation<Nav>();
  const [sessions, setSessions] = useState<LogSession[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    DiagService.getSessions()
      .then(setSessions)
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color="#1565C0" size="large" />
      </View>
    );
  }

  return (
    <SafeAreaView style={styles.safe}>
      <Text style={styles.title}>Historial de sesiones</Text>
      <FlatList
        data={sessions}
        keyExtractor={item => String(item.session_id)}
        contentContainerStyle={styles.list}
        ListEmptyComponent={
          <Text style={styles.empty}>No hay sesiones registradas</Text>
        }
        renderItem={({ item }) => (
          <TouchableOpacity
            style={styles.row}
            onPress={() => navigation.navigate('SessionDetail', { session: item })}
          >
            <View>
              <Text style={styles.sessionLabel}>
                {item.label || `Sesión #${item.session_id}`}
              </Text>
              <Text style={styles.sessionDate}>{item.started_at}</Text>
            </View>
            <View style={styles.badge}>
              <Text style={styles.badgeText}>{item.sample_count} muestras</Text>
            </View>
          </TouchableOpacity>
        )}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: '#121212' },
  center: { flex: 1, backgroundColor: '#121212', justifyContent: 'center', alignItems: 'center' },
  title: { color: '#FFF', fontSize: 20, fontWeight: 'bold', padding: 16 },
  list: { padding: 16 },
  empty: { color: '#666', textAlign: 'center', marginTop: 40 },
  row: {
    backgroundColor: '#1E1E1E',
    borderRadius: 10,
    padding: 14,
    marginBottom: 10,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  sessionLabel: { color: '#FFF', fontSize: 15, fontWeight: '500' },
  sessionDate: { color: '#777', fontSize: 12, marginTop: 3 },
  badge: {
    backgroundColor: '#1565C033',
    borderRadius: 6,
    paddingHorizontal: 8,
    paddingVertical: 3,
  },
  badgeText: { color: '#90CAF9', fontSize: 12 },
});
