'use client';

import { ConvergenceStatus } from '@/lib/types';
import { cn } from '@/lib/utils';
import { Lock, CheckCircle2, AlertTriangle, XCircle } from 'lucide-react';

interface ConvergenceBadgeProps {
  status: ConvergenceStatus;
  delta: number;
  className?: string;
  showDelta?: boolean;
  size?: 'sm' | 'md' | 'lg';
}

const statusConfig = {
  LOCK: {
    icon: Lock,
    label: 'LOCK',
    bgColor: 'bg-emerald-500/20',
    borderColor: 'border-emerald-500/50',
    textColor: 'text-emerald-400',
    glowColor: 'shadow-emerald-500/30',
  },
  ALIGNED: {
    icon: CheckCircle2,
    label: 'ALIGNED',
    bgColor: 'bg-[#D4A017]/20',
    borderColor: 'border-[#D4A017]/50',
    textColor: 'text-[#D4A017]',
    glowColor: 'shadow-[#D4A017]/30',
  },
  DIVERGENT: {
    icon: AlertTriangle,
    label: 'DIVERGENT',
    bgColor: 'bg-orange-500/20',
    borderColor: 'border-orange-500/50',
    textColor: 'text-orange-400',
    glowColor: 'shadow-orange-500/30',
  },
  CONFLICT: {
    icon: XCircle,
    label: 'CONFLICT',
    bgColor: 'bg-red-500/20',
    borderColor: 'border-red-500/50',
    textColor: 'text-red-400',
    glowColor: 'shadow-red-500/30',
  },
};

const sizeConfig = {
  sm: {
    container: 'px-2 py-1 text-xs gap-1',
    icon: 14,
  },
  md: {
    container: 'px-3 py-1.5 text-sm gap-1.5',
    icon: 16,
  },
  lg: {
    container: 'px-4 py-2 text-base gap-2',
    icon: 20,
  },
};

export function ConvergenceBadge({
  status,
  delta,
  className,
  showDelta = true,
  size = 'md',
}: ConvergenceBadgeProps) {
  const config = statusConfig[status];
  const Icon = config.icon;
  const sizeStyles = sizeConfig[size];

  return (
    <div
      className={cn(
        'inline-flex items-center justify-center rounded-lg border font-semibold',
        'backdrop-blur-sm transition-all duration-300',
        'shadow-lg',
        config.bgColor,
        config.borderColor,
        config.textColor,
        config.glowColor,
        sizeStyles.container,
        className
      )}
    >
      <Icon size={sizeStyles.icon} />
      <span>{config.label}</span>
      {showDelta && (
        <span className="opacity-75">
          ({delta > 0 ? '+' : ''}{delta.toFixed(1)})
        </span>
      )}
    </div>
  );
}

export function ConvergencePill({
  status,
  className,
}: {
  status: ConvergenceStatus;
  className?: string;
}) {
  const config = statusConfig[status];

  return (
    <div
      className={cn(
        'w-3 h-3 rounded-full',
        config.bgColor.replace('/20', ''),
        'ring-2',
        config.borderColor.replace('/50', '/30'),
        className
      )}
      title={config.label}
    />
  );
}
