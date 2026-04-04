import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { TwoLaneCard } from '@/components/TwoLaneCard'
import { getGames, gradeGame } from '@/services/api'
import type { Sport, ConvergenceResult } from '@/types'
import { SPORT_LABELS } from '@/types'

const SPORTS: Sport[] = ['nba', 'nhl', 'mlb', 'nfl', 'ncaab', 'soccer']

export default function HomePage() {
  const [selectedSport, setSelectedSport] = useState<Sport>('nba')
  const [grading, setGrading] = useState(false)

  // Fetch games
  const { data: games, isLoading, error } = useQuery({
    queryKey: ['games', selectedSport],
    queryFn: () => getGames(selectedSport),
  })

  // Grade all games
  const handleAnalyzeAll = async () => {
    if (!games || grading) return
    setGrading(true)
    
    // Grade each game
    for (const game of games) {
      try {
        await gradeGame({
          game_id: game.id,
          sport: selectedSport,
          home_team: game.homeTeam,
          away_team: game.awayTeam,
          context: {},
        })
      } catch (e) {
        console.error('Grading failed:', e)
      }
    }
    
    setGrading(false)
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-center">
          <div className="w-12 h-12 border-4 border-[#00E5FF] border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p className="text-[#6E6E80]">Loading games...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="text-center py-20">
        <p className="text-red-400 mb-2">Failed to load games</p>
        <p className="text-[#6E6E80] text-sm">{(error as Error).message}</p>
      </div>
    )
  }

  return (
    <div>
      {/* Sport Selector */}
      <div className="flex gap-2 mb-6 overflow-x-auto pb-2">
        {SPORTS.map((sport) => (
          <button
            key={sport}
            onClick={() => setSelectedSport(sport)}
            className={`px-4 py-2 rounded-lg font-bold text-sm uppercase tracking-wider whitespace-nowrap transition-all ${
              selectedSport === sport
                ? 'bg-gradient-to-r from-[#00E5FF] to-[#FF2D78] text-black'
                : 'bg-[#0E0E14] text-[#6E6E80] border border-[#1A1A28] hover:border-[#00E5FF]/30 hover:text-white'
            }`}
          >
            {SPORT_LABELS[sport]}
          </button>
        ))}
      </div>

      {/* Analyze Button */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-black text-[#E8E8EC]">{SPORT_LABELS[selectedSport]} Games</h1>
          <p className="text-[#6E6E80] text-sm">{games?.length || 0} games on slate</p>
        </div>
        <button
          onClick={handleAnalyzeAll}
          disabled={grading}
          className="flex items-center gap-2 px-6 py-3 bg-[#00E5FF] text-black font-bold rounded-lg hover:bg-[#00E5FF]/90 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
        >
          {grading ? (
            <>
              <div className="w-4 h-4 border-2 border-black border-t-transparent rounded-full animate-spin" />
              Analyzing...
            </>
          ) : (
            <>
              <span className="text-lg">⚡</span>
              Analyze All
            </>
          )}
        </button>
      </div>

      {/* Games List with Two-Lane Cards */}
      <div className="space-y-4">
        {games?.map((game) => (
          <TwoLaneCard
            key={game.id}
            game={game}
            ourGrade={{
              grade: 'A-',
              score: 7.2,
              confidence: 82,
              thesis: 'Strong home court advantage',
            }}
            aiGrade={{
              grade: 'A',
              score: 7.8,
              confidence: 85,
              thesis: 'Market mispricing detected',
              model: 'DeepSeek-V3',
            }}
            convergence={{
              status: 'ALIGNED',
              consensusScore: 7.5,
              consensusGrade: 'A-',
              delta: 0.6,
              variance: 0.3,
            }}
          />
        ))}
      </div>
    </div>
  )
}
