/**
 * DtcScreen — Pantalla 4: leer y borrar DTCs.
 */

import React, { useEffect, useState } from 'react';
import {
  View,
  Text,
  FlatList,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  Alert,
  SafeAreaView,
} from 'react-native';
import { useDiagnostics } from '../hooks/useDiagnostics';

export function DtcScreen() {
  const { dtcs, loading, error, readDtcs, clearDtcs } = useDiagnostics();
  const [hasRead, setHasRead] = useState(false);

  useEffect(() => {
    readDtcs().then(() => setHasRead(true));
  }, []);

  function confirmClear() {
    Alert.alert(
      'Borrar DTCs',
      '¿Deseas borrar todos los códigos de error?',
      [
        { text: 'Cancelar', style: 'cancel' },
        {
          text: 'Borrar',
          style: 'destructive',
          onPress: async () => {
            await clearDtcs();
            setHasRead(true);
          },
        },
      ],
    );
  }

  return (
    <SafeAreaView style={styles.safe}>
      <View style={styles.header}>
        <Text style={styles.title}>Códigos de Error (DTC)</Text>
        {loading && <ActivityIndicator color="#1565C0" />}
      </View>

      {error && <Text style={styles.error}>{error}</Text>}

      {hasRead && !loading && dtcs.length === 0 && (
        <View style={styles.empty}>
          <Text style={styles.emptyIcon}>✓</Text>
          <Text style={styles.emptyText}>No hay DTCs almacenados</Text>
        </View>
      )}

      <FlatList
        data={dtcs}
        keyExtractor={item => item.code}
        contentContainerStyle={styles.list}
        renderItem={({ item }) => (
          <View style={styles.dtcRow}>
            <Text style={styles.dtcCode}>{item.code}</Text>
            <Text style={styles.dtcDesc}>{item.description}</Text>
          </View>
        )}
      />

      <View style={styles.actions}>
        <TouchableOpacity
          style={styles.button}
          onPress={() => { setHasRead(false); readDtcs().then(() => setHasRead(true)); }}
          disabled={loading}
        >
          <Text style={styles.buttonText}>Leer DTCs</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.button, styles.buttonDanger]}
          onPress={confirmClear}
          disabled={loading || dtcs.length === 0}
        >
          <Text style={styles.buttonText}>Borrar DTCs</Text>
        </TouchableOpacity>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: '#121212' },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#2A2A2A',
  },
  title: { color: '#FFF', fontSize: 20, fontWeight: 'bold' },
  error: { color: '#EF5350', padding: 16 },
  empty: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  emptyIcon: { fontSize: 48, color: '#66BB6A' },
  emptyText: { color: '#888', fontSize: 16, marginTop: 8 },
  list: { padding: 16 },
  dtcRow: {
    backgroundColor: '#1E1E1E',
    borderRadius: 10,
    padding: 14,
    marginBottom: 10,
  },
  dtcCode: { color: '#EF5350', fontSize: 16, fontWeight: 'bold', fontFamily: 'monospace' },
  dtcDesc: { color: '#CCC', fontSize: 13, marginTop: 4 },
  actions: {
    flexDirection: 'row',
    gap: 12,
    padding: 16,
    borderTopWidth: 1,
    borderTopColor: '#2A2A2A',
  },
  button: {
    flex: 1,
    backgroundColor: '#1565C0',
    borderRadius: 10,
    padding: 14,
    alignItems: 'center',
  },
  buttonDanger: { backgroundColor: '#C62828' },
  buttonText: { color: '#FFF', fontSize: 15, fontWeight: '600' },
});
