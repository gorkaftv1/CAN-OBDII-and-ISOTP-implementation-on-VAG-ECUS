import React from 'react';
import { Svg, Path } from 'react-native-svg';

interface IconProps {
  size?: number;
  color?: string;
}

export function WarningIcon({ size = 24, color = '#fff' }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path
        d="M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z"
        fill={color}
      />
    </Svg>
  );
}
