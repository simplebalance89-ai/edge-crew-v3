'use client';

import { Game } from '@/lib/types';
import { cn } from '@/lib/utils';
import { format } from 'date-fns';
import { ConvergenceBadge, ConvergencePill } from './ConvergenceBadge';
import { ConfidenceMeter } from './ConfidenceMeter';
import { LineMovementChart } from './LineMovementChart';
import { Trophy, Clock, Activity, TrendingUp, TrendingDown, Minus } from 'lucide-react';
import Link from 'next/link';

interface GameCardProps {
  game: Game;
  variant?: 'compact' | 'full' | 'minimal';
  showChart?: boolean;
  className?: string;
}

function getGradeColor(grade: string): string {
  if (grade.startsWith('A')) return 'text-emerald-400';
  if (grade.startsWith('B')) return 'text-[#D4A017]';
  if (grade.startsWith('C')) return 'text-orange-400';
  return 'text-red-400';
}

function getPickIcon(pick: string) {
  if (pick === 'OVER') return <TrendingUp className="w-4 h-4" />;
  if (pick === 'UNDER') return <TrendingDown className="w-4 h-4" />;
  return <Minus className="w-4 h-4" />;
}

export function GameCard({ game, variant = 'compact', showChart = true, className }: GameCardProps) {
  const isLive = game.status === 'LIVE';
  const lineMovement = game.lineMovement || [];
  
  if (variant === 'minimal') {
    return (
      <Link href={`/game/${game.id}`}>
        <div className={cn('bg-slate-900/60 border border-slate-800 rounded-lg p-3 hover:border-slate-700 transition-colors cursor-pointer', className)}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <ConvergencePill status={game.convergence.status} />
              <span className="text-slate-200 font-medium text-sm">{game.awayTeam} @ {game.homeTeam}</span>
            </div>
            <span className={cn('font-bold', getGradeColor(game.ourProcess.grade))}>{game.ourProcess.grade}</span>
          </div>
        </div>
      </Link>
    );
  }

  return (
    <Link href={`/game/${game.id}`}>
      <div className={cn('bg-slate-900/60 backdrop-blur-sm border border-slate-800 rounded-xl p-4 hover:border-[#D4A017]/30 hover:shadow-lg hover:shadow-[#D4A017]/5 transition-all duration-300 cursor-pointer group', game.bestBet && 'border-[#D4A017]/20', className)}>
        <div className="flex items-start justify-between mb-3">
          <div className="flex items-center gap-2">
            {game.bestBet && <Trophy className="w-4 h-4 text-[#D4A017]" />}
            <span className="text-slate-400 text-xs uppercase tracking-wider">{game.sport}</span>
            {isLive && <span className="flex items-center gap-1 text-emerald-400 text-xs"><Activity className="w-3 h-3 animate-pulse" />LIVE</span>}
          </div>
          <ConvergenceBadge status={game.convergence.status} delta={game.convergence.delta} size="sm" />
        </div>

        <div className="mb-3">
          <div className="flex items-center justify-between">
            <span className="text-slate-200 font-semibold">{game.awayTeam}</span>
            {game.score && <span className="text-slate-200 font-mono">{game.score.away}</span>}
          </div>
          <div className="flex items-center justify-between">
            <span className="text-slate-200 font-semibold">{game.homeTeam}</span>
            {game.score && <span className="text-slate-200 font-mono">{game.score.home}</span>}
          </div>
        </div>

        <div className="flex items-center justify-between text-sm mb-3">
          <div className="flex items-center gap-1 text-slate-400">
            <Clock className="w-3 h-3" />
            <span>{format(new Date(game.startTime), 'MMM d, h:mm a')}</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-slate-500 text-xs">Line:</span>
            <span className="text-[#D4A017] font-mono font-semibold">{game.currentLine}</span>
          </div>
        </div>

        <div className="flex items-center justify-between pt-3 border-t border-slate-800">
          <div className="flex items-center gap-3">
            <div className="text-center">
              <span className="text-slate-500 text-xs block">Our Grade</span>
              <span className={cn('font-bold', getGradeColor(game.ourProcess.grade))}>{game.ourProcess.grade}</span>
            </div>
            <div className="text-center">
              <span className="text-slate-500 text-xs block">AI Grade</span>
              <span className={cn('font-bold', getGradeColor(game.aiProcess.grade))}>{game.aiProcess.grade}</span>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {getPickIcon(game.convergence.ourPick)}
            <span className="text-slate-400 text-xs">{game.convergence.ourPick}</span>
          </div>
        </div>

        {showChart && lineMovement.length > 0 && (
          <div className="mt-4 pt-4 border-t border-slate-800">
            <LineMovementChart data={lineMovement} currentLine={game.currentLine} openingLine={game.openingLine} height={80} />
          </div>
        )}
      </div>
    </Link>
  );
}
