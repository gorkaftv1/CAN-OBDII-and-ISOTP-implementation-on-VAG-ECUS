/**
 * ConnectingScreen — Pantalla 2: conectando a la Pi por BLE.
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
import { bluetoothService } from '../services/BluetoothService';
import type { RootStackParamList } from '../types';

type Nav = NativeStackNavigationProp<RootStackParamList, 'Connecting'>;
type Route = RouteProp<RootStackParamList, 'Connecting'>;

export function ConnectingScreen() {
  const navigation = useNavigation<Nav>();
  const route = useRoute<Route>();
  const { deviceName, deviceId } = route.params;

  useEffect(() => {
    let cancelled = false;

    async function doConnect() {
      try {
        await bluetoothService.connect(deviceId);
        if (!cancelled) {
          navigation.replace('Dashboard');
        }
      } catch (e: any) {
        if (!cancelled) {
          Alert.alert(
            'Error de conexión',
            e.message ?? String(e),
            [{ text: 'Volver', onPress: () => navigation.goBack() }],
          );
        }
      }
    }

    doConnect();
    return () => { cancelled = true; };
  }, [deviceId, navigation]);

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
