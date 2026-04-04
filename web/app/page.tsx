'use client';

import { useGames, useDashboardStats, useBestBets, useLocks } from '@/hooks/useGrades';
import { GameCard } from '@/components/GameCard';
import { ConvergenceBadge } from '@/components/ConvergenceBadge';
import { useRealtime } from '@/hooks/useRealtime';
import { useState, useEffect } from 'react';
import { FilterOptions, ConvergenceStatus } from '@/lib/types';
import { Trophy, Activity, Lock, AlertTriangle, Zap, TrendingUp, Filter } from 'lucide-react';
import { cn } from '@/lib/utils';

const convergenceFilters: ConvergenceStatus[] = ['LOCK', 'ALIGNED', 'DIVERGENT', 'CONFLICT'];

function StatCard({
  title,
  value,
  icon: Icon,
  color,
  trend,
}: {
  title: string;
  value: number;
  icon: React.ElementType;
  color: string;
  trend?: string;
}) {
  return (
    <div className="bg-slate-900/60 backdrop-blur-sm border border-slate-800 rounded-xl p-4">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-slate-400 text-sm">{title}</p>
          <p className="text-3xl font-bold text-slate-100 mt-1">{value}</p>
          {trend && <p className="text-emerald-400 text-xs mt-1">{trend}</p>}
        </div>
        <div className={cn('p-2 rounded-lg', color)}>
          <Icon className="w-5 h-5 text-white" />
        </div>
      </div>
    </div>
  );
}

export default function Dashboard() {
  const [filters, setFilters] = useState<FilterOptions>({});
  const { games, isLoading } = useGames(filters);
  const { stats } = useDashboardStats();
  const { bestBets } = useBestBets();
  const { locks } = useLocks();
  const [connectionStatus, setConnectionStatus] = useState<'connected' | 'disconnected'>('disconnected');

  useRealtime({
    onUpdate: (update) => {
      console.log('Real-time update:', update);
    },
    onError: () => setConnectionStatus('disconnected'),
  });

  const toggleConvergenceFilter = (status: ConvergenceStatus) => {
    setFilters((prev) => {
      const current = prev.convergence || [];
      if (current.includes(status)) {
        return { ...prev, convergence: current.filter((s) => s !== status) };
      }
      return { ...prev, convergence: [...current, status] };
    });
  };

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 border-2 border-[#D4A017] border-t-transparent rounded-full animate-spin" />
          <span className="text-slate-400">Loading games...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950">
      {/* Header */}
      <header className="sticky top-0 z-50 bg-slate-950/80 backdrop-blur-md border-b border-slate-800">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-gradient-to-br from-[#D4A017] to-[#E5B52A] rounded-xl flex items-center justify-center shadow-lg shadow-[#D4A017]/20">
                <TrendingUp className="w-6 h-6 text-slate-900" />
              </div>
              <div>
                <h1 className="text-xl font-bold text-slate-100">Edge Crew</h1>
                <p className="text-xs text-slate-400">v3.0 Pro Analytics</p>
              </div>
            </div>
            <div className="flex items-center gap-4">
              <div
                className={cn(
                  'flex items-center gap-2 px-3 py-1.5 rounded-full text-sm',
                  connectionStatus === 'connected'
                    ? 'bg-emerald-500/10 text-emerald-400'
                    : 'bg-slate-800 text-slate-400'
                )}
              >
                <div
                  className={cn(
                    'w-2 h-2 rounded-full',
                    connectionStatus === 'connected' ? 'bg-emerald-400 animate-pulse' : 'bg-slate-500'
                  )}
                />
                {connectionStatus === 'connected' ? 'Live' : 'Offline'}
              </div>
              <a
                href="/peter"
                className="bg-[#D4A017] hover:bg-[#E5B52A] text-slate-900 px-4 py-2 rounded-lg font-semibold transition-colors"
              >
                Pro Edge
              </a>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Stats */}
        {stats && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
            <StatCard title="Total Games" value={stats.totalGames} icon={Activity} color="bg-blue-500/20" />
            <StatCard title="Locks" value={stats.locks} icon={Lock} color="bg-emerald-500/20" />
            <StatCard title="Best Bets" value={stats.bestBets} icon={Trophy} color="bg-[#D4A017]/20" />
            <StatCard title="Conflicts" value={stats.conflict} icon={AlertTriangle} color="bg-red-500/20" />
          </div>
        )}

        {/* Filters */}
        <div className="mb-6">
          <div className="flex items-center gap-2 mb-3">
            <Filter className="w-4 h-4 text-slate-400" />
            <span className="text-slate-400 text-sm">Filter by Convergence</span>
          </div>
          <div className="flex flex-wrap gap-2">
            {convergenceFilters.map((status) => (
              <button
                key={status}
                onClick={() => toggleConvergenceFilter(status)}
                className={cn(
                  'px-3 py-1.5 rounded-lg text-sm font-medium transition-all',
                  filters.convergence?.includes(status)
                    ? 'bg-slate-800 text-slate-100'
                    : 'bg-slate-900/50 text-slate-500 hover:text-slate-300'
                )}
              >
                {status}
              </button>
            ))}
          </div>
        </div>

        {/* Best Bets */}
        {bestBets.length > 0 && (
          <section className="mb-8">
            <div className="flex items-center gap-2 mb-4">
              <Trophy className="w-5 h-5 text-[#D4A017]" />
              <h2 className="text-lg font-semibold text-slate-100">Best Bets</h2>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {bestBets.map((game) => (
                <GameCard key={game.id} game={game} />
              ))}
            </div>
          </section>
        )}

        {/* Locks */}
        {locks.length > 0 && (
          <section className="mb-8">
            <div className="flex items-center gap-2 mb-4">
              <Lock className="w-5 h-5 text-emerald-400" />
              <h2 className="text-lg font-semibold text-slate-100">Locks</h2>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {locks.map((game) => (
                <GameCard key={game.id} game={game} />
              ))}
            </div>
          </section>
        )}

        {/* All Games */}
        <section>
          <div className="flex items-center gap-2 mb-4">
            <Zap className="w-5 h-5 text-blue-400" />
            <h2 className="text-lg font-semibold text-slate-100">All Games</h2>
            <span className="text-slate-500 text-sm">({games.length})</span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {games.map((game) => (
              <GameCard key={game.id} game={game} />
            ))}
          </div>
        </section>
      </main>
    </div>
  );
}
