import { Game, DashboardStats, FilterOptions, StreamUpdate } from './types';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

class APIError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = 'APIError';
  }
}

async function fetcher<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${url}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  });

  if (!response.ok) {
    throw new APIError(response.status, await response.text());
  }

  return response.json();
}

export const api = {
  games: {
    list: (filters?: FilterOptions) => {
      const params = new URLSearchParams();
      if (filters?.sport) filters.sport.forEach(s => params.append('sport', s));
      if (filters?.status) filters.status.forEach(s => params.append('status', s));
      if (filters?.convergence) filters.convergence.forEach(c => params.append('convergence', c));
      if (filters?.grade) filters.grade.forEach(g => params.append('grade', g));
      return fetcher<Game[]>(`/api/games?${params.toString()}`);
    },
    
    get: (id: string) => fetcher<Game>(`/api/games/${id}`),
    
    getBySport: (sport: string) => fetcher<Game[]>(`/api/games/sport/${sport}`),
    
    getBestBets: () => fetcher<Game[]>(`/api/games/best-bets`),
    
    getLocks: () => fetcher<Game[]>(`/api/games/locks`),
  },

  stats: {
    dashboard: () => fetcher<DashboardStats>(`/api/stats/dashboard`),
    
    bySport: (sport: string) => fetcher<DashboardStats>(`/api/stats/sport/${sport}`),
  },

  stream: {
    connect: (gameId?: string): EventSource => {
      const url = gameId 
        ? `${API_BASE}/api/stream?gameId=${gameId}`
        : `${API_BASE}/api/stream`;
      return new EventSource(url);
    },
  },
};

export { APIError };
