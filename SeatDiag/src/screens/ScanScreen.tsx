/**
 * ScanScreen — Pantalla 1: descubrimiento Bluetooth.
 *
 * Muestra la lista de dispositivos BT disponibles.
 * Destaca el dispositivo "SEAT_DIAG_PI" y navega a ConnectingScreen al pulsarlo.
 */

import React, { useState, useCallback } from 'react';
import {
  View,
  Text,
  FlatList,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  Alert,
} from 'react-native';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { bluetoothService } from '../services/BluetoothService';
import type { RootStackParamList } from '../types';

type Nav = NativeStackNavigationProp<RootStackParamList, 'Scan'>;

const TARGET_NAME = 'SEAT_DIAG_PI';

export function ScanScreen() {
  const navigation = useNavigation<Nav>();
  const [devices, setDevices] = useState<any[]>([]);
  const [scanning, setScanning] = useState(false);

  const scan = useCallback(async () => {
    const enabled = await bluetoothService.isBluetoothEnabled();
    if (!enabled) {
      const granted = await bluetoothService.requestEnable();
      if (!granted) {
        Alert.alert('Bluetooth requerido', 'Activa el Bluetooth para continuar.');
        return;
      }
    }
    setScanning(true);
    setDevices([]);
    try {
      const found = await bluetoothService.discover();
      setDevices(found);
    } catch (e: any) {
      Alert.alert('Error', e.message);
    } finally {
      setScanning(false);
    }
  }, []);

  const connect = useCallback(
    (device: any) => {
      navigation.navigate('Connecting', {
        deviceName: device.name ?? device.address,
        deviceAddress: device.address,
      });
    },
    [navigation],
  );

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Buscar dispositivos</Text>
      <Text style={styles.subtitle}>Busca la Raspberry Pi con nombre "{TARGET_NAME}"</Text>

      <TouchableOpacity style={styles.scanButton} onPress={scan} disabled={scanning}>
        {scanning ? (
          <ActivityIndicator color="#FFF" />
        ) : (
          <Text style={styles.scanButtonText}>Escanear Bluetooth</Text>
        )}
      </TouchableOpacity>

      <FlatList
        data={devices}
        keyExtractor={item => item.address}
        contentContainerStyle={styles.list}
        ListEmptyComponent={
          !scanning ? (
            <Text style={styles.empty}>
              {devices.length === 0
                ? 'Pulsa "Escanear" para buscar dispositivos'
                : 'No se encontraron dispositivos'}
            </Text>
          ) : null
        }
        renderItem={({ item }) => {
          const isTarget = item.name === TARGET_NAME;
          return (
            <TouchableOpacity
              style={[styles.deviceRow, isTarget && styles.deviceRowTarget]}
              onPress={() => connect(item)}
            >
              <View>
                <Text style={[styles.deviceName, isTarget && styles.deviceNameTarget]}>
                  {item.name ?? 'Dispositivo desconocido'}
                </Text>
                <Text style={styles.deviceAddress}>{item.address}</Text>
              </View>
              {isTarget && (
                <View style={styles.targetBadge}>
                  <Text style={styles.targetBadgeText}>SEAT DIAG</Text>
                </View>
              )}
            </TouchableOpacity>
          );
        }}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#121212', padding: 16 },
  title: { color: '#FFF', fontSize: 22, fontWeight: 'bold', marginBottom: 4 },
  subtitle: { color: '#888', fontSize: 13, marginBottom: 20 },
  scanButton: {
    backgroundColor: '#1565C0',
    borderRadius: 10,
    padding: 14,
    alignItems: 'center',
    marginBottom: 20,
  },
  scanButtonText: { color: '#FFF', fontSize: 16, fontWeight: '600' },
  list: { paddingBottom: 20 },
  empty: { color: '#666', textAlign: 'center', marginTop: 40 },
  deviceRow: {
    backgroundColor: '#1E1E1E',
    borderRadius: 10,
    padding: 14,
    marginBottom: 10,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  deviceRowTarget: {
    borderColor: '#1565C0',
    borderWidth: 1.5,
  },
  deviceName: { color: '#DDD', fontSize: 15, fontWeight: '500' },
  deviceNameTarget: { color: '#FFF', fontWeight: 'bold' },
  deviceAddress: { color: '#666', fontSize: 12, marginTop: 2 },
  targetBadge: {
    backgroundColor: '#1565C0',
    borderRadius: 6,
    paddingHorizontal: 8,
    paddingVertical: 3,
  },
  targetBadgeText: { color: '#FFF', fontSize: 11, fontWeight: 'bold' },
});
