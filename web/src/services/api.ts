import axios from 'axios';
import type { Game, ConvergenceResult, Pick, User } from '@/types';

const API_BASE = import.meta.env.VITE_API_URL || '';

const api = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Health
export const checkHealth = () => api.get('/health').then(r => r.data);

// Games
export const getGames = (sport: string) => 
  api.get<Game[]>('/api/games', { params: { sport } }).then(r => r.data);

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

// Picks
export const getPicks = () => 
  api.get<Pick[]>('/api/picks').then(r => r.data);

export const createPick = (data: Partial<Pick>) => 
  api.post<Pick>('/api/picks', data).then(r => r.data);

// User
export const getUser = () => 
  api.get<User>('/api/user').then(r => r.data);

export const updateUser = (data: Partial<User>) => 
  api.put<User>('/api/user', data).then(r => r.data);

// Stats
export const getStats = () => 
  api.get('/api/stats').then(r => r.data);

export default api;
