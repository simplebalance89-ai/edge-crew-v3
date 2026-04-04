import { create } from 'zustand';
import { devtools, persist } from 'zustand/middleware';
import type { Game, ConvergenceResult, Pick, Sport, User } from '@/types';

interface AppState {
  // UI State
  selectedSport: Sport;
  setSelectedSport: (sport: Sport) => void;
  
  // Data
  games: Game[];
  setGames: (games: Game[]) => void;
  currentGame: ConvergenceResult | null;
  setCurrentGame: (game: ConvergenceResult | null) => void;
  picks: Pick[];
  setPicks: (picks: Pick[]) => void;
  addPick: (pick: Pick) => void;
  user: User | null;
  setUser: (user: User | null) => void;
  
  // Loading States
  isLoadingGames: boolean;
  setIsLoadingGames: (loading: boolean) => void;
  isGrading: boolean;
  setIsGrading: (loading: boolean) => void;
  
  // Errors
  error: string | null;
  setError: (error: string | null) => void;
  clearError: () => void;
}

export const useAppStore = create<AppState>()(
  devtools(
    persist(
      (set) => ({
        // UI State
        selectedSport: 'nba',
        setSelectedSport: (sport) => set({ selectedSport: sport }),
        
        // Data
        games: [],
        setGames: (games) => set({ games }),
        currentGame: null,
        setCurrentGame: (game) => set({ currentGame: game }),
        picks: [],
        setPicks: (picks) => set({ picks }),
        addPick: (pick) => set((state) => ({ picks: [pick, ...state.picks] })),
        user: null,
        setUser: (user) => set({ user }),
        
        // Loading
        isLoadingGames: false,
        setIsLoadingGames: (loading) => set({ isLoadingGames: loading }),
        isGrading: false,
        setIsGrading: (loading) => set({ isGrading: loading }),
        
        // Errors
        error: null,
        setError: (error) => set({ error }),
        clearError: () => set({ error: null }),
      }),
      {
        name: 'edge-crew-storage',
        partialize: (state) => ({ 
          selectedSport: state.selectedSport,
          picks: state.picks,
          user: state.user,
        }),
      }
    ),
    { name: 'EdgeCrewStore' }
  )
);
