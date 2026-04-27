import { Platform } from 'react-native';

export const colors = {
  background: '#0a0a0f',
  surface: '#12121a',
  surfaceElevated: '#1a1a24',
  border: '#2a2a3a',
  primary: '#00d4ff',
  success: '#00ff88',
  warning: '#ffaa00',
  error: '#ff4444',
  text: '#ffffff',
  textSecondary: '#8888aa',
  textMuted: '#44445a',
};

export const spacing = {
  xs: 4,
  sm: 8,
  md: 16,
  lg: 24,
  xl: 32,
};

export const fontSize = {
  xs: 11,
  sm: 13,
  md: 16,
  lg: 20,
  xl: 28,
  xxl: 40,
};

export const monoFont = Platform.select({
  ios: 'Courier',
  android: 'monospace',
  default: 'monospace',
});
