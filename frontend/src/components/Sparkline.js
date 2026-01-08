import React from 'react';
import { LineChart, Line, ResponsiveContainer } from 'recharts';

function Sparkline({ data, color = '#18181b', width = 60, height = 24 }) {
  // data should be array of numbers, e.g., [45, 52, 48, 60, 55, 58]
  // Convert to format recharts needs
  const chartData = data.map((value, index) => ({
    index,
    value: value || 0
  }));

  if (!data || data.length === 0) {
    return (
      <span style={{ 
        display: 'inline-block', 
        width: width, 
        height: height,
        color: '#d4d4d8',
        fontSize: '11px',
        textAlign: 'center'
      }}>
        —
      </span>
    );
  }

  return (
    <ResponsiveContainer width={width} height={height}>
      <LineChart data={chartData}>
        <Line
          type="monotone"
          dataKey="value"
          stroke={color}
          strokeWidth={1.5}
          dot={false}
          isAnimationActive={false}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}

export default Sparkline;
