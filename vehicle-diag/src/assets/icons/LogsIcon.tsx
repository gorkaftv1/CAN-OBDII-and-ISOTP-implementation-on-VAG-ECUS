import React from 'react';
import { Svg, Path } from 'react-native-svg';

interface IconProps {
  size?: number;
  color?: string;
}

export function LogsIcon({ size = 24, color = '#fff' }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path
        d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-8-6z"
        fill={color}
      />
      <Path d="M16 18H8v-2h8v2zm0-4H8v-2h8v2zm0-4H8V8h8v2z" fill="white" opacity="0.3" />
    </Svg>
  );
}
