/**
 * ScanScreen — Pantalla 1: descubrimiento BLE.
 *
 * Escanea dispositivos BLE que anuncian el Nordic UART Service.
 * Destaca el dispositivo "SEAT_DIAG" y navega a ConnectingScreen al pulsarlo.
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
  Platform,
  PermissionsAndroid,
} from 'react-native';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import type { Device } from 'react-native-ble-plx';
import { bluetoothService } from '../services/BluetoothService';
import type { RootStackParamList } from '../types';

type Nav = NativeStackNavigationProp<RootStackParamList, 'Scan'>;

const TARGET_NAME = 'SEAT_DIAG';

async function requestAndroidBlePermissions(): Promise<boolean> {
  if (Platform.OS !== 'android') return true;

  if (Platform.Version >= 31) {
    const results = await PermissionsAndroid.requestMultiple([
      PermissionsAndroid.PERMISSIONS.BLUETOOTH_SCAN,
      PermissionsAndroid.PERMISSIONS.BLUETOOTH_CONNECT,
    ]);
    return Object.values(results).every(r => r === PermissionsAndroid.RESULTS.GRANTED);
  }

  // Android < 12
  const result = await PermissionsAndroid.request(
    PermissionsAndroid.PERMISSIONS.ACCESS_FINE_LOCATION,
  );
  return result === PermissionsAndroid.RESULTS.GRANTED;
}

export function ScanScreen() {
  const navigation = useNavigation<Nav>();
  const [devices, setDevices] = useState<Device[]>([]);
  const [scanning, setScanning] = useState(false);

  const scan = useCallback(async () => {
    const enabled = await bluetoothService.isBluetoothEnabled();
    if (!enabled) {
      Alert.alert('Bluetooth requerido', 'Activa el Bluetooth para continuar.');
      return;
    }

    const granted = await requestAndroidBlePermissions();
    if (!granted) {
      Alert.alert('Permisos requeridos', 'La app necesita permisos de Bluetooth para escanear.');
      return;
    }

    setScanning(true);
    setDevices([]);
    try {
      const found = await bluetoothService.scan();
      setDevices(found);
    } catch (e: any) {
      Alert.alert('Error al escanear', e.message ?? String(e));
    } finally {
      setScanning(false);
    }
  }, []);

  const connect = useCallback(
    (device: Device) => {
      navigation.navigate('Connecting', {
        deviceName: device.name ?? device.id,
        deviceId: device.id,
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
        keyExtractor={item => item.id}
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
                <Text style={styles.deviceAddress}>{item.id}</Text>
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
