import React, { useEffect, useRef } from 'react';
import {
  Animated,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { useConnectionStore } from '../../stores/connectionStore';
import { useVehicleStore } from '../../stores/vehicleStore';
import { colors, fontSize, spacing } from '../../shared/theme';
import type { ConnectionStatus } from '../../stores/connectionStore';

const STATUS_COLOR: Record<ConnectionStatus, string> = {
  disconnected: colors.textMuted,
  scanning: colors.primary,
  connecting: colors.warning,
  connected: colors.success,
};

const STATUS_LABEL: Record<ConnectionStatus, string> = {
  disconnected: 'Disconnected',
  scanning: 'Scanning…',
  connecting: 'Connecting…',
  connected: 'Connected',
};

export function ConnectionScreen() {
  const { status, deviceName, error, connect, disconnect } = useConnectionStore();
  const { vin } = useVehicleStore();
  const scale = useRef(new Animated.Value(1)).current;
  const opacity = useRef(new Animated.Value(1)).current;
  const animRef = useRef<Animated.CompositeAnimation | null>(null);

  useEffect(() => {
    animRef.current?.stop();
    scale.setValue(1);
    opacity.setValue(1);

    if (status === 'scanning' || status === 'connecting') {
      animRef.current = Animated.loop(
        Animated.sequence([
          Animated.timing(scale, { toValue: 1.55, duration: 650, useNativeDriver: true }),
          Animated.timing(scale, { toValue: 1, duration: 650, useNativeDriver: true }),
        ]),
      );
      animRef.current.start();
    } else if (status === 'connected') {
      animRef.current = Animated.loop(
        Animated.sequence([
          Animated.timing(opacity, { toValue: 0.4, duration: 1400, useNativeDriver: true }),
          Animated.timing(opacity, { toValue: 1, duration: 1400, useNativeDriver: true }),
        ]),
      );
      animRef.current.start();
    }

    return () => animRef.current?.stop();
  }, [status]);

  const dotColor = STATUS_COLOR[status];
  const busy = status === 'scanning' || status === 'connecting';

  return (
    <View style={styles.root}>
      <View style={styles.body}>
        <Text style={styles.title}>OBD2 Diagnostics</Text>

        <View style={styles.indicator}>
          <Animated.View
            style={[styles.ring, { borderColor: dotColor, transform: [{ scale }], opacity }]}
          />
          <View style={[styles.dot, { backgroundColor: dotColor }]} />
        </View>

        <Text style={[styles.statusLabel, { color: dotColor }]}>{STATUS_LABEL[status]}</Text>

        {status === 'connected' && deviceName ? (
          <Text style={styles.deviceName}>{deviceName}</Text>
        ) : null}
        {status === 'connected' && vin ? (
          <Text style={styles.vinText}>{vin}</Text>
        ) : null}

        {error ? <Text style={styles.errorText}>{error}</Text> : null}

        <TouchableOpacity
          style={[
            styles.btn,
            status === 'connected' ? styles.btnDisconnect : styles.btnConnect,
            busy && styles.btnBusy,
          ]}
          onPress={status === 'connected' ? disconnect : connect}
          disabled={busy}
          activeOpacity={0.75}
        >
          <Text style={styles.btnLabel}>
            {status === 'connected' ? 'Disconnect' : busy ? 'Please wait…' : 'Connect'}
          </Text>
        </TouchableOpacity>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.background },
  body: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: spacing.xl },
  title: {
    fontSize: fontSize.xl,
    fontWeight: '700',
    color: colors.text,
    marginBottom: spacing.xl * 2,
    letterSpacing: 0.5,
  },
  indicator: {
    width: 120,
    height: 120,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: spacing.lg,
  },
  ring: {
    position: 'absolute',
    width: 100,
    height: 100,
    borderRadius: 50,
    borderWidth: 2,
  },
  dot: { width: 44, height: 44, borderRadius: 22 },
  statusLabel: { fontSize: fontSize.lg, fontWeight: '600', marginBottom: spacing.xs },
  deviceName: { fontSize: fontSize.sm, color: colors.textSecondary, marginBottom: spacing.xs },
  vinText: { fontSize: fontSize.xs, color: colors.textMuted, fontFamily: 'monospace', marginBottom: spacing.lg },
  errorText: {
    fontSize: fontSize.sm,
    color: colors.error,
    marginTop: spacing.sm,
    textAlign: 'center',
    maxWidth: 280,
  },
  btn: {
    marginTop: spacing.xl,
    paddingHorizontal: spacing.xl,
    paddingVertical: spacing.md,
    borderRadius: 10,
    minWidth: 220,
    alignItems: 'center',
  },
  btnConnect: { backgroundColor: colors.primary },
  btnDisconnect: { backgroundColor: colors.error },
  btnBusy: { opacity: 0.45 },
  btnLabel: { fontSize: fontSize.md, fontWeight: '700', color: colors.background },
});
