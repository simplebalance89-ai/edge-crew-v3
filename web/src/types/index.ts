export interface Game {
  id: string;
  sport: string;
  homeTeam: string;
  awayTeam: string;
  scheduledAt: string;
  status: "scheduled" | "live" | "completed";
  odds?: Odds;
  ourGrade?: Grade;
  aiGrade?: Grade & { model?: string };
  convergence?: {
    status: "LOCK" | "ALIGNED" | "CLOSE" | "SPLIT";
    consensusScore: number;
    consensusGrade: string;
    delta: number;
    variance: number;
  };
  bookmaker?: string;
  pick?: {
    side: string;
    type: string;
    line: number;
    confidence: number;
    sizing: string;
  };
  aiModels?: Array<{
    model: string;
    grade: string;
    score: number;
    confidence: number;
    thesis: string;
    key_factors?: string[];
  }>;
  gatekeeper?: {
    action: string;
    adjustment: number;
    reason: string;
  };
}

export interface Odds {
  spread: number;
  total: number;
  mlHome: number;
  mlAway: number;
}

export interface Grade {
  grade: string;
  score: number;
  confidence: number;
  thesis?: string;
  keyFactors?: string[];
}

export interface ConvergenceResult {
  gameId: string;
  sport: string;
  homeTeam: string;
  awayTeam: string;
  ourProcess: Grade;
  aiProcess: Grade & { model: string };
  convergence: {
    status: "LOCK" | "ALIGNED" | "CLOSE" | "SPLIT";
    consensusScore: number;
    consensusGrade: string;
    delta: number;
    variance: number;
  };
  pick?: {
    side: string;
    confidence: number;
    sizing: string;
  };
}

export interface Pick {
  id: string;
  gameId: string;
  game: Game;
  side: string;
  grade: string;
  confidence: number;
  sizing: string;
  result?: "win" | "loss" | "push" | "pending";
  profit?: number;
  createdAt: string;
}

export interface User {
  id: string;
  name: string;
  email: string;
  avatar?: string;
  role: "free" | "pro" | "elite";
  bankroll: Bankroll;
}

export interface Bankroll {
  current: number;
  starting: number;
  totalWagered: number;
  totalProfit: number;
  roi: number;
  wins: number;
  losses: number;
  pushes: number;
}

export type Sport = "nba" | "nhl" | "mlb" | "nfl" | "ncaab" | "soccer";

export const SPORT_LABELS: Record<Sport, string> = {
  nba: "NBA",
  nhl: "NHL",
  mlb: "MLB",
  nfl: "NFL",
  ncaab: "NCAAB",
  soccer: "Soccer",
};

export const GRADE_COLORS: Record<string, string> = {
  "A+": "#10B981",
  "A": "#10B981",
  "A-": "#34D399",
  "B+": "#38BDF8",
  "B": "#38BDF8",
  "B-": "#60A5FA",
  "C+": "#F59E0B",
  "C": "#F59E0B",
  "D": "#EF4444",
  "F": "#EF4444",
};

export const CONVERGENCE_COLORS: Record<string, { bg: string; border: string; text: string }> = {
  LOCK: { bg: "rgba(16, 185, 129, 0.15)", border: "#10B981", text: "#10B981" },
  ALIGNED: { bg: "rgba(56, 189, 248, 0.15)", border: "#38BDF8", text: "#38BDF8" },
  CLOSE: { bg: "rgba(245, 158, 11, 0.15)", border: "#F59E0B", text: "#F59E0B" },
  SPLIT: { bg: "rgba(239, 68, 68, 0.15)", border: "#EF4444", text: "#EF4444" },
};
