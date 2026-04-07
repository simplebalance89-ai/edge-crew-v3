import axios from 'axios';
import type { Game, ConvergenceResult, Pick, User, Bankroll, LockedPick, BetSlip } from '@/types';

const API_BASE = '';

const api = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Health
export const checkHealth = () => api.get('/health').then(r => r.data);

// Games
export const getGames = (sport: string, mode?: string, league?: string) =>
  api.get<Game[]>('/api/games', { params: { sport, ...(mode ? { mode } : {}), ...(league ? { league } : {}) } }).then(r => r.data);

export const getGame = (id: string) => 
  api.get<Game>(`/api/games/${id}`).then(r => r.data);

// Grading
export interface GradeRequest {
  game_id: string;
  sport: string;
  home_team: string;
  away_team: string;
  context?: Record<string, unknown>;
}

export const gradeGame = (data: GradeRequest) =>
  api.post<ConvergenceResult>('/api/grade', data).then(r => r.data);

// Deep AI analysis (crowdsource + gatekeeper)
export const analyzeGames = (sport: string) =>
  api.post<Game[]>('/api/analyze', { sport }).then(r => r.data);

// Picks
export const getPicks = () => 
  api.get<Pick[]>('/api/picks').then(r => r.data);

export const createPick = (data: Partial<Pick>) => 
  api.post<Pick>('/api/picks', data).then(r => r.data);

// User / Auth
export const login = (username: string, pin: string) =>
  api.post<User>('/api/login', { username, pin }).then(r => r.data);

export const getBankroll = (username: string) =>
  api.get<Bankroll>(`/api/user/${username}/bankroll`).then(r => r.data);

export const lockPick = (username: string, data: {
  game_id: string; sport: string; team: string; type: string;
  line?: number; amount?: number; odds?: number;
}) =>
  api.post<LockedPick>(`/api/user/${username}/pick`, data).then(r => r.data);

export const getUserPicks = (username: string) =>
  api.get<LockedPick[]>(`/api/user/${username}/picks`).then(r => r.data);

export const adjustBankroll = (username: string, delta: number) =>
  api.post<Bankroll>(`/api/profile/${username}/adjust`, { delta }).then(r => r.data);

export const gradePick = (username: string, pickId: string, result: string) =>
  api.post(`/api/user/${username}/pick/${pickId}/result`, { result }).then(r => r.data);

// Bet Slip
export const generateBetSlip = (username: string, gameIds: string[] = []) =>
  api.post<BetSlip>('/api/betslip', { username, game_ids: gameIds }).then(r => r.data);

// User-driven slip locks (separate from the legacy /pick history endpoint)
export const toggleSlipLock = (username: string, gameId: string, action: 'add' | 'remove') =>
  api.post<{ username: string; game_ids: string[] }>('/api/locks', {
    username, game_id: gameId, action,
  }).then(r => r.data);

export const getSlipLocks = (username: string) =>
  api.get<{ username: string; game_ids: string[] }>(`/api/locks/${username}`).then(r => r.data);

// Parlay
export interface ParlayPick {
  game: string;
  pick: string;
  odds: number;
  sport: string;
}

export interface ParlayResponse {
  picks: ParlayPick[];
  parlay_odds: string;
  risk: number;
  potential_payout: number;
  confidence: number;
}

export const getParlay = () =>
  api.get<ParlayResponse>('/api/parlay').then(r => r.data);

// Legacy
export const getUser = () =>
  api.get<User>('/api/user').then(r => r.data);

export const updateUser = (data: Partial<User>) =>
  api.put<User>('/api/user', data).then(r => r.data);

// Stats
export const getStats = () =>
  api.get('/api/stats').then(r => r.data);

export default api;
