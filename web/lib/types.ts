export type Grade = 'A+' | 'A' | 'A-' | 'B+' | 'B' | 'B-' | 'C+' | 'C' | 'C-' | 'D' | 'F';

export type ConvergenceStatus = 'LOCK' | 'ALIGNED' | 'DIVERGENT' | 'CONFLICT';

export interface OurProcessComponent {
  name: string;
  weight: number;
  score: number;
  details: string;
}

export interface OurProcess {
  grade: Grade;
  score: number;
  components: OurProcessComponent[];
}

export interface AIModelBreakdown {
  model: string;
  prediction: 'OVER' | 'UNDER' | 'NO_PICK';
  confidence: number;
  line?: number;
}

export interface AIProcess {
  grade: Grade;
  score: number;
  breakdown: AIModelBreakdown[];
  ensembleConfidence: number;
}

export interface Convergence {
  status: ConvergenceStatus;
  delta: number;
  ourPick: 'OVER' | 'UNDER' | 'NO_PICK';
  aiPick: 'OVER' | 'UNDER' | 'NO_PICK';
  notes?: string;
}

export interface LineMovement {
  timestamp: string;
  line: number;
  source: string;
}

export interface GradeHistory {
  timestamp: string;
  grade: Grade;
  score: number;
}

export interface Game {
  id: string;
  sport: 'NBA' | 'NCAAB' | 'NFL' | 'NCAAB';
  homeTeam: string;
  awayTeam: string;
  startTime: string;
  currentLine: number;
  openingLine: number;
  ourProcess: OurProcess;
  aiProcess: AIProcess;
  convergence: Convergence;
  lineMovement: LineMovement[];
  gradeHistory: GradeHistory[];
  bestBet: boolean;
  status: 'SCHEDULED' | 'LIVE' | 'FINAL' | 'POSTPONED';
  score?: {
    home: number;
    away: number;
  };
}

export interface StreamUpdate {
  gameId: string;
  type: 'GRADE_UPDATE' | 'LINE_MOVEMENT' | 'SCORE_UPDATE' | 'STATUS_CHANGE';
  timestamp: string;
  data: Partial<Game>;
}

export interface DashboardStats {
  totalGames: number;
  locks: number;
  aligned: number;
  divergent: number;
  conflict: number;
  bestBets: number;
  lastUpdated: string;
}

export interface FilterOptions {
  sport?: string[];
  status?: string[];
  convergence?: ConvergenceStatus[];
  grade?: Grade[];
}
