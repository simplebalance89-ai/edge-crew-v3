'use client';

import useSWR from 'swr';
import { Game, DashboardStats, FilterOptions } from '@/lib/types';
import { api } from '@/lib/api';

const REFRESH_INTERVAL = 30000; // 30 seconds

export function useGames(filters?: FilterOptions) {
  const { data, error, isLoading, mutate } = useSWR<Game[]>(
    ['games', filters],
    () => api.games.list(filters),
    {
      refreshInterval: REFRESH_INTERVAL,
      revalidateOnFocus: true,
      dedupingInterval: 5000,
    }
  );

  return {
    games: data || [],
    isLoading,
    error,
    mutate,
  };
}

export function useGame(id: string) {
  const { data, error, isLoading, mutate } = useSWR<Game>(
    id ? `game-${id}` : null,
    () => api.games.get(id),
    {
      refreshInterval: REFRESH_INTERVAL,
      revalidateOnFocus: true,
    }
  );

  return {
    game: data,
    isLoading,
    error,
    mutate,
  };
}

export function useDashboardStats() {
  const { data, error, isLoading } = useSWR<DashboardStats>(
    'dashboard-stats',
    () => api.stats.dashboard(),
    {
      refreshInterval: REFRESH_INTERVAL,
      revalidateOnFocus: true,
    }
  );

  return {
    stats: data,
    isLoading,
    error,
  };
}

export function useBestBets() {
  const { data, error, isLoading } = useSWR<Game[]>(
    'best-bets',
    () => api.games.getBestBets(),
    {
      refreshInterval: REFRESH_INTERVAL,
      revalidateOnFocus: true,
    }
  );

  return {
    bestBets: data || [],
    isLoading,
    error,
  };
}

export function useLocks() {
  const { data, error, isLoading } = useSWR<Game[]>(
    'locks',
    () => api.games.getLocks(),
    {
      refreshInterval: REFRESH_INTERVAL,
      revalidateOnFocus: true,
    }
  );

  return {
    locks: data || [],
    isLoading,
    error,
  };
}

export function useGamesBySport(sport: string) {
  const { data, error, isLoading } = useSWR<Game[]>(
    sport ? `games-sport-${sport}` : null,
    () => api.games.getBySport(sport),
    {
      refreshInterval: REFRESH_INTERVAL,
      revalidateOnFocus: true,
    }
  );

  return {
    games: data || [],
    isLoading,
    error,
  };
}
