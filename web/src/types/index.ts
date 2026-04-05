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
  ev?: {
    ev_pct: number | null;
    ev_grade: string;
    kelly_units: string;
    true_prob: number | null;
    implied_prob: number | null;
    edge: number | null;
    moneyline: number | null;
  };
  peterRules?: {
    flags: Array<{ rule: string; action: string; severity: string; note: string }>;
    adjustment: number;
    has_kill: boolean;
  };
  kalshi_prob?: number | null;
  nrfi?: {
    verdict: string;
    confidence: number;
    reason: string;
  };
  arbitrage?: {
    has_arb: boolean;
    arb_pct: number;
    best_home: { book: string; odds: number };
    best_away: { book: string; odds: number };
  } | null;
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
  profiles?: Record<string, { grade: string; final: number; composite: number; sizing: string; chains_fired: string[] }>;
  variables?: Record<string, { score: number; name: string; available: boolean }>;
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
  username: string;
  name: string;
  bankroll: Bankroll;
}

export interface Bankroll {
  starting: number;
  current: number;
  wagered: number;
  profit: number;
  wins: number;
  losses: number;
  pushes: number;
}

export interface LockedPick {
  id: string;
  game_id: string;
  sport: string;
  team: string;
  type: string;
  line: number;
  amount: number;
  odds: number;
  result: "pending" | "W" | "L" | "P";
  profit: number;
  locked_at: string;
}

export interface BetSlip {
  slip_id: string | null;
  generated?: string;
  user?: string;
  picks?: Array<{
    game: string;
    pick: string;
    type: string;
    amount: string;
    book: string;
  }>;
  total_risk?: string;
  potential_payout?: string;
  notes?: string;
  error?: string;
}

export type Sport = "nba" | "nhl" | "mlb" | "nfl" | "ncaab" | "soccer" | "mma" | "boxing";

export const SPORT_LABELS: Record<Sport, string> = {
  nba: "NBA",
  nhl: "NHL",
  mlb: "MLB",
  nfl: "NFL",
  ncaab: "NCAAB",
  soccer: "Soccer",
  mma: "MMA",
  boxing: "Boxing",
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
