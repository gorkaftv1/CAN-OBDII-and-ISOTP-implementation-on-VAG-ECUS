import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { NavigationContainer } from '@react-navigation/native';
import React from 'react';
import { View } from 'react-native';
import { ConnectionScreen } from '../screens/connection/ConnectionScreen';
import { ConsoleScreen } from '../screens/console/ConsoleScreen';
import { CustomizeScreen } from '../screens/customize/CustomizeScreen';
import { DashboardScreen } from '../screens/dashboard/DashboardScreen';
import { DtcScreen } from '../screens/dtcs/DtcScreen';
import { LogsScreen } from '../screens/logs/LogsScreen';
import { colors, fontSize } from '../shared/theme';
import { ConnectionIcon } from '../assets/icons/ConnectionIcon';
import { DashboardIcon } from '../assets/icons/DashboardIcon';
import { WarningIcon } from '../assets/icons/WarningIcon';
import { ConsoleIcon } from '../assets/icons/ConsoleIcon';
import { SettingsIcon } from '../assets/icons/SettingsIcon';
import { LogsIcon } from '../assets/icons/LogsIcon';

const Tab = createBottomTabNavigator();

export function AppNavigator() {
  const getIcon = (name: string, color: string) => {
    const iconProps = { color, size: 24 };
    switch (name) {
      case 'Connection':
        return <ConnectionIcon {...iconProps} />;
      case 'Dashboard':
        return <DashboardIcon {...iconProps} />;
      case 'DTCs':
        return <WarningIcon {...iconProps} />;
      case 'Console':
        return <ConsoleIcon {...iconProps} />;
      case 'Customize':
        return <SettingsIcon {...iconProps} />;
      case 'Logs':
        return <LogsIcon {...iconProps} />;
      default:
        return null;
    }
  };

  return (
    <NavigationContainer>
      <Tab.Navigator
        screenOptions={({ route }) => ({
          tabBarIcon: ({ focused }) => (
            <View>
              {getIcon(route.name, focused ? colors.primary : colors.textSecondary)}
            </View>
          ),
          tabBarStyle: {
            backgroundColor: colors.surface,
            borderTopColor: colors.border,
            borderTopWidth: 1,
          },
          tabBarActiveTintColor: colors.primary,
          tabBarInactiveTintColor: colors.textSecondary,
          tabBarLabelStyle: { fontSize: fontSize.xs },
          headerStyle: {
            backgroundColor: colors.surface,
            shadowColor: 'transparent',
            elevation: 0,
            borderBottomWidth: 1,
            borderBottomColor: colors.border,
          } as object,
          headerTintColor: colors.text,
          headerTitleStyle: { fontWeight: '600' as const },
        })}
      >
        <Tab.Screen name="Connection" component={ConnectionScreen} />
        <Tab.Screen name="Dashboard" component={DashboardScreen} />
        <Tab.Screen name="DTCs" component={DtcScreen} />
        <Tab.Screen name="Console" component={ConsoleScreen} />
        <Tab.Screen name="Customize" component={CustomizeScreen} />
        <Tab.Screen name="Logs" component={LogsScreen} />
      </Tab.Navigator>
    </NavigationContainer>
  );
}
