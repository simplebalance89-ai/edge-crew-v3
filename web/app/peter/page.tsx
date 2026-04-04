'use client';

import { useState } from 'react';
import { useGames, useLocks } from '@/hooks/useGrades';
import { TwoLaneDisplay } from '@/components/TwoLaneDisplay';
import { GameCard } from '@/components/GameCard';
import { ConvergenceBadge } from '@/components/ConvergenceBadge';
import { useRealtime } from '@/hooks/useRealtime';
import { Game, ConvergenceStatus } from '@/lib/types';
import { ArrowLeft, Lock, TrendingUp, Filter, RefreshCw } from 'lucide-react';
import Link from 'next/link';
import { cn } from '@/lib/utils';

const mockGame: Game = {
  id: 'mock-1',
  sport: 'NBA',
  homeTeam: 'Lakers',
  awayTeam: 'Warriors',
  startTime: new Date().toISOString(),
  currentLine: 225.5,
  openingLine: 222.0,
  status: 'SCHEDULED',
  bestBet: true,
  ourProcess: {
    grade: 'A-',
    score: 87.5,
    components: [
      { name: 'Trend Analysis', weight: 0.3, score: 92, details: 'Strong over trend' },
      { name: 'Matchup Edge', weight: 0.25, score: 85, details: 'Favorable pace' },
      { name: 'Situational', weight: 0.25, score: 88, details: 'Back-to-back spot' },
      { name: 'Market Timing', weight: 0.2, score: 85, details: 'Early line value' },
    ],
  },
  aiProcess: {
    grade: 'B+',
    score: 82.3,
    ensembleConfidence: 78.5,
    breakdown: [
      { model: 'GPT-4', prediction: 'OVER', confidence: 82, line: 226 },
      { model: 'Claude', prediction: 'OVER', confidence: 79, line: 225 },
      { model: 'Gemini', prediction: 'NO_PICK', confidence: 65 },
      { model: 'Llama', prediction: 'OVER', confidence: 75, line: 227 },
    ],
  },
  convergence: {
    status: 'ALIGNED',
    delta: 5.2,
    ourPick: 'OVER',
    aiPick: 'OVER',
    notes: 'Both processes favor the over',
  },
  lineMovement: [
    { timestamp: new Date(Date.now() - 86400000).toISOString(), line: 222, source: 'open' },
    { timestamp: new Date(Date.now() - 43200000).toISOString(), line: 223.5, source: 'betonline' },
    { timestamp: new Date(Date.now() - 21600000).toISOString(), line: 224, source: 'pinnacle' },
    { timestamp: new Date().toISOString(), line: 225.5, source: 'current' },
  ],
  gradeHistory: [],
};

export default function ProEdgePage() {
  const { games } = useGames();
  const { locks } = useLocks();
  const [selectedGame, setSelectedGame] = useState<Game>(mockGame);
  const [filter, setFilter] = useState<ConvergenceStatus | 'ALL'>('ALL');

  useRealtime({
    gameId: selectedGame.id,
    onUpdate: (update) => {
      console.log('Pro Edge update:', update);
    },
  });

  const filteredGames = filter === 'ALL' ? games : games.filter((g) => g.convergence.status === filter);

  return (
    <div className="min-h-screen bg-slate-950">
      {/* Header */}
      <header className="sticky top-0 z-50 bg-slate-950/80 backdrop-blur-md border-b border-slate-800">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Link
                href="/"
                className="flex items-center gap-2 text-slate-400 hover:text-slate-200 transition-colors"
              >
                <ArrowLeft className="w-5 h-5" />
                <span>Back</span>
              </Link>
              <div className="h-6 w-px bg-slate-800" />
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 bg-[#D4A017] rounded-lg flex items-center justify-center">
                  <TrendingUp className="w-5 h-5 text-slate-900" />
                </div>
                <div>
                  <h1 className="text-lg font-bold text-slate-100">Pro Edge</h1>
                  <p className="text-xs text-slate-400">Two-Lane Analysis</p>
                </div>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <button className="p-2 text-slate-400 hover:text-slate-200 transition-colors">
                <RefreshCw className="w-5 h-5" />
              </button>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Two Lane Display */}
        <section className="mb-8">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-slate-100">Selected Game Analysis</h2>
            <ConvergenceBadge status={selectedGame.convergence.status} delta={selectedGame.convergence.delta} />
          </div>
          <TwoLaneDisplay
            ourProcess={selectedGame.ourProcess}
            aiProcess={selectedGame.aiProcess}
            convergence={selectedGame.convergence}
          />
        </section>

        {/* Game Selector */}
        <section className="mb-8">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Filter className="w-4 h-4 text-slate-400" />
              <h2 className="text-lg font-semibold text-slate-100">Select Game</h2>
            </div>
            <div className="flex gap-2">
              {(['ALL', 'LOCK', 'ALIGNED', 'DIVERGENT', 'CONFLICT'] as const).map((f) => (
                <button
                  key={f}
                  onClick={() => setFilter(f)}
                  className={cn(
                    'px-3 py-1.5 rounded-lg text-sm font-medium transition-all',
                    filter === f ? 'bg-[#D4A017] text-slate-900' : 'bg-slate-900 text-slate-400 hover:text-slate-200'
                  )}
                >
                  {f}
                </button>
              ))}
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {filteredGames.slice(0, 8).map((game) => (
              <button
                key={game.id}
                onClick={() => setSelectedGame(game)}
                className={cn(
                  'text-left transition-all',
                  selectedGame.id === game.id && 'ring-2 ring-[#D4A017] rounded-xl'
                )}
              >
                <GameCard game={game} variant="minimal" />
              </button>
            ))}
          </div>
        </section>

        {/* Locks Section */}
        {locks.length > 0 && (
          <section>
            <div className="flex items-center gap-2 mb-4">
              <Lock className="w-5 h-5 text-emerald-400" />
              <h2 className="text-lg font-semibold text-slate-100">Today&apos;s Locks</h2>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {locks.map((game) => (
                <GameCard key={game.id} game={game} />
              ))}
            </div>
          </section>
        )}
      </main>
    </div>
  );
}
