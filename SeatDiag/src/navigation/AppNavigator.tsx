import React from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';

import { ScanScreen } from '../screens/ScanScreen';
import { ConnectingScreen } from '../screens/ConnectingScreen';
import { DashboardScreen } from '../screens/DashboardScreen';
import { DtcScreen } from '../screens/DtcScreen';
import { HistoryScreen } from '../screens/HistoryScreen';
import { SessionDetailScreen } from '../screens/SessionDetailScreen';

import type { RootStackParamList } from '../types';

const Stack = createNativeStackNavigator<RootStackParamList>();

const screenOptions = {
  headerStyle: { backgroundColor: '#1A1A1A' },
  headerTintColor: '#FFF',
  headerTitleStyle: { fontWeight: 'bold' as const },
  contentStyle: { backgroundColor: '#121212' },
};

export function AppNavigator() {
  return (
    <NavigationContainer>
      <Stack.Navigator initialRouteName="Scan" screenOptions={screenOptions}>
        <Stack.Screen
          name="Scan"
          component={ScanScreen}
          options={{ title: 'Conectar a SEAT Ibiza' }}
        />
        <Stack.Screen
          name="Connecting"
          component={ConnectingScreen}
          options={{ title: 'Conectando...', headerBackVisible: false }}
        />
        <Stack.Screen
          name="Dashboard"
          component={DashboardScreen}
          options={{ title: 'Dashboard', headerBackVisible: false }}
        />
        <Stack.Screen
          name="Dtc"
          component={DtcScreen}
          options={{ title: 'Códigos de Error' }}
        />
        <Stack.Screen
          name="History"
          component={HistoryScreen}
          options={{ title: 'Historial' }}
        />
        <Stack.Screen
          name="SessionDetail"
          component={SessionDetailScreen}
          options={{ title: 'Detalle sesión' }}
        />
      </Stack.Navigator>
    </NavigationContainer>
  );
}
