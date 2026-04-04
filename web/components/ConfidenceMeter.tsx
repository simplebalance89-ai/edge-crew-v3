'use client';

import { cn } from '@/lib/utils';

interface ConfidenceMeterProps {
  value: number;
  max?: number;
  size?: 'sm' | 'md' | 'lg';
  showValue?: boolean;
  className?: string;
}

const sizeConfig = {
  sm: {
    container: 'h-1.5',
    text: 'text-xs',
  },
  md: {
    container: 'h-2',
    text: 'text-sm',
  },
  lg: {
    container: 'h-3',
    text: 'text-base',
  },
};

function getColor(value: number, max: number): string {
  const percentage = (value / max) * 100;
  if (percentage >= 80) return 'bg-emerald-500';
  if (percentage >= 60) return 'bg-[#D4A017]';
  if (percentage >= 40) return 'bg-orange-500';
  return 'bg-red-500';
}

function getGlowColor(value: number, max: number): string {
  const percentage = (value / max) * 100;
  if (percentage >= 80) return 'shadow-emerald-500/50';
  if (percentage >= 60) return 'shadow-[#D4A017]/50';
  if (percentage >= 40) return 'shadow-orange-500/50';
  return 'shadow-red-500/50';
}

export function ConfidenceMeter({
  value,
  max = 100,
  size = 'md',
  showValue = true,
  className,
}: ConfidenceMeterProps) {
  const percentage = Math.min(100, Math.max(0, (value / max) * 100));
  const colorClass = getColor(value, max);
  const glowClass = getGlowColor(value, max);
  const sizeStyles = sizeConfig[size];

  return (
    <div className={cn('w-full', className)}>
      <div className="flex items-center justify-between mb-1">
        <span className="text-slate-400 text-xs uppercase tracking-wider">Confidence</span>
        {showValue && (
          <span className={cn('font-mono font-semibold text-slate-200', sizeStyles.text)}>
            {value.toFixed(1)}%
          </span>
        )}
      </div>
      <div
        className={cn(
          'w-full bg-slate-800 rounded-full overflow-hidden',
          sizeStyles.container
        )}
      >
        <div
          className={cn(
            'h-full rounded-full transition-all duration-500 ease-out',
            colorClass,
            'shadow-lg',
            glowClass
          )}
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  );
}

export function CircularConfidenceMeter({
  value,
  max = 100,
  size = 60,
  strokeWidth = 6,
  className,
}: {
  value: number;
  max?: number;
  size?: number;
  strokeWidth?: number;
  className?: string;
}) {
  const percentage = Math.min(100, Math.max(0, (value / max) * 100));
  const radius = (size - strokeWidth) / 2;
  const circumference = radius * 2 * Math.PI;
  const offset = circumference - (percentage / 100) * circumference;
  
  const colorClass = getColor(value, max).replace('bg-', 'text-');

  return (
    <div className={cn('relative inline-flex items-center justify-center', className)}>
      <svg width={size} height={size} className="transform -rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="currentColor"
          strokeWidth={strokeWidth}
          className="text-slate-800"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="currentColor"
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          className={cn('transition-all duration-500 ease-out', colorClass)}
          strokeDasharray={circumference}
          strokeDashoffset={offset}
        />
      </svg>
      <div className="absolute inset-0 flex items-center justify-center">
        <span className="text-xs font-bold text-slate-200">{Math.round(percentage)}</span>
      </div>
    </div>
  );
}
