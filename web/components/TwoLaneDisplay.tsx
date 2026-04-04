'use client';

import { OurProcess, AIProcess, Convergence, ConvergenceStatus } from '@/lib/types';
import { cn } from '@/lib/utils';
import { ConvergenceBadge } from './ConvergenceBadge';
import { ConfidenceMeter } from './ConfidenceMeter';
import { CircularConfidenceMeter } from './ConfidenceMeter';
import { TrendingUp, TrendingDown, Minus, Brain, Target, Zap } from 'lucide-react';

interface TwoLaneDisplayProps {
  ourProcess: OurProcess;
  aiProcess: AIProcess;
  convergence: Convergence;
  className?: string;
}

interface LaneProps {
  title: string;
  color: string;
  grade: string;
  score: number;
  children: React.ReactNode;
}

function getGradeColor(grade: string): string {
  if (grade.startsWith('A')) return 'text-emerald-400';
  if (grade.startsWith('B')) return 'text-[#D4A017]';
  if (grade.startsWith('C')) return 'text-orange-400';
  return 'text-red-400';
}

function getGradeBg(grade: string): string {
  if (grade.startsWith('A')) return 'bg-emerald-500/10 border-emerald-500/30';
  if (grade.startsWith('B')) return 'bg-[#D4A017]/10 border-[#D4A017]/30';
  if (grade.startsWith('C')) return 'bg-orange-500/10 border-orange-500/30';
  return 'bg-red-500/10 border-red-500/30';
}

function Lane({ title, color, grade, score, children }: LaneProps) {
  return (
    <div className="bg-slate-900/60 backdrop-blur-sm border border-slate-800 rounded-xl overflow-hidden">
      <div className="p-4 border-b border-slate-800" style={{ borderLeftWidth: '4px', borderLeftColor: color }}>
        <div className="flex items-center justify-between">
          <span className="text-slate-400 text-sm font-medium uppercase tracking-wider">{title}</span>
          <div className={cn('px-3 py-1 rounded-lg border', getGradeBg(grade))}>
            <span className={cn('text-2xl font-bold', getGradeColor(grade))}>{grade}</span>
          </div>
        </div>
        <div className="mt-2">
          <ConfidenceMeter value={score} size="sm" />
        </div>
      </div>
      <div className="p-4">{children}</div>
    </div>
  );
}

export function TwoLaneDisplay({ ourProcess, aiProcess, convergence, className }: TwoLaneDisplayProps) {
  return (
    <div className={cn('grid grid-cols-1 md:grid-cols-2 gap-4', className)}>
      <Lane title="OUR PROCESS" color="#F72585" grade={ourProcess.grade} score={ourProcess.score}>
        <div className="space-y-3">
          {ourProcess.components.map((component, idx) => (
            <div key={idx} className="flex items-center justify-between p-2 bg-slate-800/50 rounded-lg">
              <div className="flex items-center gap-2">
                <Target className="w-4 h-4 text-slate-500" />
                <span className="text-slate-300 text-sm">{component.name}</span>
              </div>
              <div className="flex items-center gap-3">
                <div className="w-16 h-1.5 bg-slate-700 rounded-full overflow-hidden">
                  <div className="h-full bg-[#F72585] rounded-full" style={{ width: `${component.score}%` }} />
                </div>
                <span className="text-slate-400 text-xs w-8 text-right">{component.score.toFixed(0)}%</span>
              </div>
            </div>
          ))}
        </div>
      </Lane>

      <Lane title="AI PROCESS" color="#00D4AA" grade={aiProcess.grade} score={aiProcess.score}>
        <div className="space-y-3">
          {aiProcess.breakdown.map((model, idx) => (
            <div key={idx} className="flex items-center justify-between p-2 bg-slate-800/50 rounded-lg">
              <div className="flex items-center gap-2">
                <Brain className="w-4 h-4 text-slate-500" />
                <span className="text-slate-300 text-sm">{model.model}</span>
              </div>
              <div className="flex items-center gap-2">
                {model.prediction === 'OVER' && <TrendingUp className="w-4 h-4 text-emerald-400" />}
                {model.prediction === 'UNDER' && <TrendingDown className="w-4 h-4 text-red-400" />}
                {model.prediction === 'NO_PICK' && <Minus className="w-4 h-4 text-slate-400" />}
                <CircularConfidenceMeter value={model.confidence} size={32} strokeWidth={3} />
              </div>
            </div>
          ))}
          <div className="pt-2 border-t border-slate-800">
            <div className="flex items-center justify-between">
              <span className="text-slate-400 text-xs uppercase">Ensemble Confidence</span>
              <div className="flex items-center gap-2">
                <Zap className="w-4 h-4 text-[#00D4AA]" />
                <span className="text-[#00D4AA] font-semibold">{aiProcess.ensembleConfidence.toFixed(1)}%</span>
              </div>
            </div>
          </div>
        </div>
      </Lane>

      <div className="md:col-span-2">
        <ConvergenceBadge status={convergence.status} delta={convergence.delta} size="lg" className="w-full" />
      </div>
    </div>
  );
}
