import React from 'react';
import { Svg, Path } from 'react-native-svg';

interface IconProps {
  size?: number;
  color?: string;
}

export function ConsoleIcon({ size = 24, color = '#fff' }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path
        d="M4 6h16v2H4zm0 5h16v2H4zm0 5h16v2H4z"
        fill={color}
      />
    </Svg>
  );
}
