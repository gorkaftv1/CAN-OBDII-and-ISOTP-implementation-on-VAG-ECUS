import React from 'react';
import { Svg, Path } from 'react-native-svg';

interface IconProps {
  size?: number;
  color?: string;
}

export function PauseIcon({ size = 24, color = '#fff' }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path
        d="M6 4h4v16H6V4zm8 0h4v16h-4V4z"
        fill={color}
      />
    </Svg>
  );
}
