/**
 * GaugeCard — muestra un PID con visualización según su unidad:
 *   rpm    → arco SVG circular con gradiente verde/amarillo/rojo
 *   km/h   → número grande centrado
 *   °C     → barra vertical (termómetro) con gradiente azul→rojo
 *   %      → barra horizontal con color
 *   otros  → valor numérico con unidad
 */

import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import Svg, { Path, Circle, Text as SvgText, Defs, LinearGradient, Stop } from 'react-native-svg';

interface Props {
  name: string;
  value: number;
  unit: string;
  compact?: boolean;
}

// ── Colores ──────────────────────────────────────────────────────────

function tempColor(value: number): string {
  if (value < 60) return '#4FC3F7';  // azul frío
  if (value < 85) return '#FFD54F';  // amarillo calentando
  return '#EF5350';                   // rojo temperatura normal/alta
}

function percentColor(value: number): string {
  if (value < 40) return '#66BB6A';
  if (value < 75) return '#FFD54F';
  return '#EF5350';
}

// ── Gauge RPM (arco SVG) ──────────────────────────────────────────────

function RpmGauge({ value }: { value: number }) {
  const MAX_RPM = 7000;
  const SIZE = 120;
  const CX = SIZE / 2;
  const CY = SIZE / 2;
  const R = 50;
  const START_ANGLE = -220; // grados desde las 12 en punto, sentido horario
  const TOTAL_ARC = 260;

  const clampedRpm = Math.min(value, MAX_RPM);
  const fraction = clampedRpm / MAX_RPM;
  const sweepAngle = fraction * TOTAL_ARC;

  function polarToXY(angleDeg: number, r: number) {
    const rad = ((angleDeg - 90) * Math.PI) / 180;
    return {
      x: CX + r * Math.cos(rad),
      y: CY + r * Math.sin(rad),
    };
  }

  function arcPath(startDeg: number, endDeg: number, r: number) {
    const start = polarToXY(startDeg, r);
    const end = polarToXY(endDeg, r);
    const largeArc = endDeg - startDeg > 180 ? 1 : 0;
    return `M ${start.x} ${start.y} A ${r} ${r} 0 ${largeArc} 1 ${end.x} ${end.y}`;
  }

  const startDeg = START_ANGLE;
  const endDeg = START_ANGLE + TOTAL_ARC;
  const valueDeg = START_ANGLE + sweepAngle;

  const strokeColor = clampedRpm > 5500 ? '#EF5350' : clampedRpm > 3500 ? '#FFD54F' : '#66BB6A';

  return (
    <Svg width={SIZE} height={SIZE}>
      {/* Arco fondo */}
      <Path
        d={arcPath(startDeg, endDeg, R)}
        fill="none"
        stroke="#333"
        strokeWidth={10}
        strokeLinecap="round"
      />
      {/* Arco valor */}
      {fraction > 0 && (
        <Path
          d={arcPath(startDeg, valueDeg, R)}
          fill="none"
          stroke={strokeColor}
          strokeWidth={10}
          strokeLinecap="round"
        />
      )}
      {/* Texto RPM */}
      <SvgText
        x={CX}
        y={CY + 6}
        textAnchor="middle"
        fontSize={18}
        fontWeight="bold"
        fill="#FFFFFF"
      >
        {Math.round(value)}
      </SvgText>
      <SvgText x={CX} y={CY + 20} textAnchor="middle" fontSize={10} fill="#AAA">
        rpm
      </SvgText>
    </Svg>
  );
}

// ── Barra temperatura ─────────────────────────────────────────────────

function TempBar({ value }: { value: number }) {
  const MIN = -40;
  const MAX = 130;
  const fraction = Math.min(Math.max((value - MIN) / (MAX - MIN), 0), 1);
  const height = 60;
  const fillHeight = fraction * height;
  const color = tempColor(value);

  return (
    <View style={styles.tempBarContainer}>
      <View style={[styles.tempBarOuter, { height }]}>
        <View style={[styles.tempBarFill, { height: fillHeight, backgroundColor: color }]} />
      </View>
      <Text style={[styles.tempValue, { color }]}>{Math.round(value)}°C</Text>
    </View>
  );
}

// ── Barra porcentaje ──────────────────────────────────────────────────

function PercentBar({ value }: { value: number }) {
  const fraction = Math.min(Math.max(value / 100, 0), 1);
  const color = percentColor(value);
  return (
    <View style={styles.percentBarContainer}>
      <View style={styles.percentBarOuter}>
        <View style={[styles.percentBarFill, { width: `${fraction * 100}%`, backgroundColor: color }]} />
      </View>
      <Text style={[styles.percentValue, { color }]}>{Math.round(value)}%</Text>
    </View>
  );
}

// ── Componente principal ──────────────────────────────────────────────

export function GaugeCard({ name, value, unit, compact = false }: Props) {
  let content: React.ReactNode;

  if (unit === 'rpm') {
    content = <RpmGauge value={value} />;
  } else if (unit === '°C') {
    content = <TempBar value={value} />;
  } else if (unit === '%') {
    content = <PercentBar value={value} />;
  } else {
    // km/h y otros: número grande
    content = (
      <Text style={styles.bigValue}>
        {Number.isInteger(value) ? value : value.toFixed(1)}
        <Text style={styles.bigUnit}> {unit}</Text>
      </Text>
    );
  }

  return (
    <View style={[styles.card, compact && styles.cardCompact]}>
      <Text style={styles.cardTitle} numberOfLines={1}>{name}</Text>
      <View style={styles.cardContent}>{content}</View>
    </View>
  );
}

// ── Estilos ───────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  card: {
    backgroundColor: '#1E1E1E',
    borderRadius: 12,
    padding: 12,
    margin: 6,
    alignItems: 'center',
    minWidth: 130,
    flex: 1,
  },
  cardCompact: {
    minWidth: 100,
    padding: 8,
  },
  cardTitle: {
    color: '#AAA',
    fontSize: 11,
    marginBottom: 8,
    textAlign: 'center',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  cardContent: {
    alignItems: 'center',
    justifyContent: 'center',
  },
  bigValue: {
    color: '#FFFFFF',
    fontSize: 28,
    fontWeight: 'bold',
  },
  bigUnit: {
    color: '#888',
    fontSize: 14,
    fontWeight: 'normal',
  },
  tempBarContainer: {
    alignItems: 'center',
  },
  tempBarOuter: {
    width: 18,
    backgroundColor: '#333',
    borderRadius: 9,
    overflow: 'hidden',
    justifyContent: 'flex-end',
  },
  tempBarFill: {
    width: '100%',
    borderRadius: 9,
  },
  tempValue: {
    fontSize: 13,
    fontWeight: 'bold',
    marginTop: 4,
  },
  percentBarContainer: {
    width: '100%',
    alignItems: 'center',
  },
  percentBarOuter: {
    width: '100%',
    height: 10,
    backgroundColor: '#333',
    borderRadius: 5,
    overflow: 'hidden',
  },
  percentBarFill: {
    height: '100%',
    borderRadius: 5,
  },
  percentValue: {
    fontSize: 16,
    fontWeight: 'bold',
    marginTop: 6,
  },
});
