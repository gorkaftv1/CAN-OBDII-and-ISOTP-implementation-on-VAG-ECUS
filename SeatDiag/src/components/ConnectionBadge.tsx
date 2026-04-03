import React from 'react';
import { View, Text, StyleSheet } from 'react-native';

interface Props {
  connected: boolean;
  deviceName?: string;
}

export function ConnectionBadge({ connected, deviceName }: Props) {
  return (
    <View style={[styles.badge, connected ? styles.connected : styles.disconnected]}>
      <View style={[styles.dot, connected ? styles.dotOn : styles.dotOff]} />
      <Text style={styles.text}>
        {connected ? (deviceName ?? 'Conectado') : 'Desconectado'}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
  },
  connected: {
    backgroundColor: '#1B5E2044',
  },
  disconnected: {
    backgroundColor: '#B71C1C44',
  },
  dot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    marginRight: 6,
  },
  dotOn: {
    backgroundColor: '#66BB6A',
  },
  dotOff: {
    backgroundColor: '#EF5350',
  },
  text: {
    color: '#DDD',
    fontSize: 12,
  },
});
