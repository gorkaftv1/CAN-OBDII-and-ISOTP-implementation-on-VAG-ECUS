/**
 * ConnectingScreen — Pantalla 2: conectando a la Pi por Bluetooth RFCOMM.
 */

import React, { useEffect } from 'react';
import {
  View,
  Text,
  ActivityIndicator,
  StyleSheet,
  Alert,
} from 'react-native';
import { useNavigation, useRoute } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import type { RouteProp } from '@react-navigation/native';
import RNBluetoothClassic from 'react-native-bluetooth-classic';
import { bluetoothService } from '../services/BluetoothService';
import type { RootStackParamList } from '../types';

type Nav = NativeStackNavigationProp<RootStackParamList, 'Connecting'>;
type Route = RouteProp<RootStackParamList, 'Connecting'>;

export function ConnectingScreen() {
  const navigation = useNavigation<Nav>();
  const route = useRoute<Route>();
  const { deviceName, deviceAddress } = route.params;

  useEffect(() => {
    let cancelled = false;

    async function doConnect() {
      try {
        const devices = await RNBluetoothClassic.getBondedDevices();
        const target = devices.find(d => d.address === deviceAddress);
        if (!target) {
          // Intentar con el address directo aunque no esté en bonded
          const all = await bluetoothService.discover();
          const found = all.find(d => d.address === deviceAddress);
          if (!found) throw new Error('Dispositivo no encontrado');
          await bluetoothService.connect(found);
        } else {
          await bluetoothService.connect(target);
        }
        if (!cancelled) {
          navigation.replace('Dashboard');
        }
      } catch (e: any) {
        if (!cancelled) {
          Alert.alert(
            'Error de conexión',
            e.message,
            [{ text: 'Volver', onPress: () => navigation.goBack() }],
          );
        }
      }
    }

    doConnect();
    return () => { cancelled = true; };
  }, [deviceAddress, navigation]);

  return (
    <View style={styles.container}>
      <ActivityIndicator size="large" color="#1565C0" />
      <Text style={styles.title}>Conectando...</Text>
      <Text style={styles.subtitle}>{deviceName}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#121212',
    justifyContent: 'center',
    alignItems: 'center',
  },
  title: {
    color: '#FFF',
    fontSize: 20,
    fontWeight: 'bold',
    marginTop: 20,
  },
  subtitle: {
    color: '#888',
    fontSize: 14,
    marginTop: 8,
  },
});
