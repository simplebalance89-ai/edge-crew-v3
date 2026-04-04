'use client';

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  Area,
  ComposedChart,
} from 'recharts';
import { LineMovement } from '@/lib/types';
import { format } from 'date-fns';
import { cn } from '@/lib/utils';

interface LineMovementChartProps {
  data: LineMovement[];
  currentLine?: number;
  openingLine?: number;
  height?: number;
  className?: string;
}

interface ChartDataPoint {
  timestamp: string;
  formattedTime: string;
  line: number;
  index: number;
}

function formatChartData(movements: LineMovement[]): ChartDataPoint[] {
  return movements
    .sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime())
    .map((m, index) => ({
      timestamp: m.timestamp,
      formattedTime: format(new Date(m.timestamp), 'MMM d HH:mm'),
      line: m.line,
      index,
    }));
}

function CustomTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: Array<{ value: number }>;
  label?: string;
}) {
  if (active && payload && payload.length) {
    return (
      <div className="bg-slate-900/95 border border-slate-700 rounded-lg p-3 shadow-xl">
        <p className="text-slate-400 text-xs mb-1">{label}</p>
        <p className="text-[#D4A017] font-bold text-lg">
          {payload[0].value.toFixed(1)}
        </p>
      </div>
    );
  }
  return null;
}

export function LineMovementChart({
  data,
  currentLine,
  openingLine,
  height = 120,
  className,
}: LineMovementChartProps) {
  const chartData = formatChartData(data);
  
  if (chartData.length === 0) {
    return (
      <div
        className={cn(
          'flex items-center justify-center bg-slate-900/50 rounded-lg',
          className
        )}
        style={{ height }}
      >
        <span className="text-slate-500 text-sm">No line movement data</span>
      </div>
    );
  }

  const minLine = Math.min(...chartData.map(d => d.line));
  const maxLine = Math.max(...chartData.map(d => d.line));
  const yDomain = [
    Math.floor(minLine - 1),
    Math.ceil(maxLine + 1),
  ];

  return (
    <div className={cn('w-full', className)} style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={chartData} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
          <defs>
            <linearGradient id="lineGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#D4A017" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#D4A017" stopOpacity={0} />
            </linearGradient>
          </defs>
          
          <XAxis
            dataKey="formattedTime"
            tick={{ fill: '#64748b', fontSize: 10 }}
            tickLine={false}
            axisLine={{ stroke: '#334155' }}
            interval="preserveStartEnd"
            minTickGap={30}
          />
          
          <YAxis
            domain={yDomain}
            tick={{ fill: '#64748b', fontSize: 10 }}
            tickLine={false}
            axisLine={false}
            tickFormatter={(value) => value.toFixed(1)}
          />
          
          <Tooltip content={<CustomTooltip />} />
          
          {openingLine && (
            <ReferenceLine
              y={openingLine}
              stroke="#64748b"
              strokeDasharray="3 3"
              strokeWidth={1}
            />
          )}
          
          <Area
            type="monotone"
            dataKey="line"
            stroke="none"
            fill="url(#lineGradient)"
          />
          
          <Line
            type="monotone"
            dataKey="line"
            stroke="#D4A017"
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 4, fill: '#D4A017', stroke: '#fff', strokeWidth: 2 }}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
