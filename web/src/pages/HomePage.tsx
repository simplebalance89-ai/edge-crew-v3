import { useState, useMemo } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { TwoLaneCard } from '@/components/TwoLaneCard'
import { getGames, analyzeGames } from '@/services/api'
import type { Sport } from '@/types'
import { SPORT_LABELS } from '@/types'

const SPORTS: Sport[] = ['nba', 'nhl', 'mlb', 'nfl', 'ncaab', 'soccer', 'mma', 'boxing', 'golf']
const CHINNY_TAB = 'fuck_chinny'

type MlbMode = 'games' | 'nrfi'
type SoccerLeague = '' | 'epl' | 'la_liga' | 'serie_a' | 'mls' | 'bundesliga' | 'ligue_1' | 'ucl' | 'europa' | 'brazil' | 'liga_mx'

const SOCCER_LEAGUES: { value: SoccerLeague; label: string }[] = [
  { value: '', label: 'All' },
  { value: 'ucl', label: 'UCL' },
  { value: 'europa', label: 'Europa' },
  { value: 'epl', label: 'EPL' },
  { value: 'la_liga', label: 'La Liga' },
  { value: 'serie_a', label: 'Serie A' },
  { value: 'bundesliga', label: 'Bundesliga' },
  { value: 'ligue_1', label: 'Ligue 1' },
  { value: 'mls', label: 'MLS' },
  { value: 'liga_mx', label: 'Liga MX' },
  { value: 'brazil', label: 'Brazil' },
]

export default function HomePage() {
  const [selectedSport, setSelectedSport] = useState<Sport>('nba')
  const [mlbMode, setMlbMode] = useState<MlbMode>('games')
  const [soccerLeague, setSoccerLeague] = useState<SoccerLeague>('')
  const [analyzing, setAnalyzing] = useState(false)
  const [analyzeError, setAnalyzeError] = useState<string | null>(null)
  const [specialTab, setSpecialTab] = useState<'none' | typeof CHINNY_TAB>('none')
  const queryClient = useQueryClient()

  const isChinnyTab = specialTab === CHINNY_TAB
  const effectiveSport: Sport = isChinnyTab ? 'soccer' : selectedSport
  const apiMode = effectiveSport === 'mlb' ? mlbMode : undefined
  const apiLeague = effectiveSport === 'soccer' && !isChinnyTab ? soccerLeague || undefined : undefined

  // Fetch games
  const { data: games, isLoading, error } = useQuery({
    queryKey: ['games', effectiveSport, apiMode, apiLeague, specialTab],
    queryFn: () => getGames(effectiveSport, apiMode, apiLeague),
  })

  // Sort games by engine grade score desc; ungraded to the bottom
  const sortedGames = useMemo(() => {
    if (!Array.isArray(games)) return games
    const gradeRank: Record<string, number> = {
      'A+': 10, A: 9, 'A-': 8, 'B+': 7, B: 6, 'B-': 5, 'C+': 4, C: 3, D: 2, F: 1, '-': 0,
    }
    const filtered = isChinnyTab
      ? games.filter((g: any) => {
          const cg = (g?.convergence?.consensusGrade || '').toString().toUpperCase()
          return (gradeRank[cg] || 0) >= gradeRank['B+']
        })
      : games
    const consensusRankOf = (g: any): number => {
      const cg = (g?.convergence?.consensusGrade || '-').toString().toUpperCase()
      return gradeRank[cg] || 0
    }
    const consensusScoreOf = (g: any): number => {
      const s = g?.convergence?.consensusScore
      return typeof s === 'number' && s > 0 ? s : -Infinity
    }
    const engineScoreOf = (g: any): number => {
      const s = g?.ourGrade?.score ?? g?.grade?.score ?? g?.score
      return typeof s === 'number' && s > 0 ? s : -Infinity
    }
    return [...filtered].sort((a, b) => {
      const rankDelta = consensusRankOf(b) - consensusRankOf(a)
      if (rankDelta !== 0) return rankDelta
      const consDelta = consensusScoreOf(b) - consensusScoreOf(a)
      if (consDelta !== 0) return consDelta
      return engineScoreOf(b) - engineScoreOf(a)
    })
  }, [games, isChinnyTab])

  // Deep AI analysis — calls /api/analyze which runs crowdsource + gatekeeper
  const handleAnalyzeAll = async () => {
    if (analyzing) return
    setAnalyzing(true)
    setAnalyzeError(null)

    try {
      const enriched = await analyzeGames(
        effectiveSport,
        isChinnyTab ? { fast: true } : (effectiveSport === 'soccer' ? { league: apiLeague, fast: true } : undefined)
      )
      // Update the query cache with enriched games so cards re-render
      if (Array.isArray(enriched)) {
        queryClient.setQueryData(['games', effectiveSport, apiMode, apiLeague, specialTab], enriched)
      }
    } catch (e) {
      console.error('Analysis failed:', e)
      setAnalyzeError((e as Error).message || 'Analysis failed')
    }

    setAnalyzing(false)
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
            onClick={() => {
              setSpecialTab('none')
              setSelectedSport(sport)
            }}
            className={`px-4 py-2 rounded-lg font-bold text-sm uppercase tracking-wider whitespace-nowrap transition-all ${
              !isChinnyTab && selectedSport === sport
                ? 'bg-gradient-to-r from-[#00E5FF] to-[#FF2D78] text-black'
                : 'bg-[#0E0E14] text-[#6E6E80] border border-[#1A1A28] hover:border-[#00E5FF]/30 hover:text-white'
            }`}
          >
            {SPORT_LABELS[sport]}
          </button>
        ))}
        <button
          onClick={() => {
            setSelectedSport('soccer')
            setSpecialTab(CHINNY_TAB)
          }}
          className={`px-4 py-2 rounded-lg font-bold text-sm uppercase tracking-wider whitespace-nowrap transition-all ${
            isChinnyTab
              ? 'bg-gradient-to-r from-[#00E5FF] to-[#FF2D78] text-black'
              : 'bg-[#0E0E14] text-[#6E6E80] border border-[#1A1A28] hover:border-[#00E5FF]/30 hover:text-white'
          }`}
        >
          FUCK Chinny
        </button>
      </div>

      {/* MLB Mode Toggle */}
      {selectedSport === 'mlb' && (
        <div className="flex gap-2 mb-4">
          {(['games', 'nrfi'] as MlbMode[]).map((mode) => (
            <button
              key={mode}
              onClick={() => setMlbMode(mode)}
              className={`px-4 py-1.5 rounded-lg font-bold text-xs uppercase tracking-wider transition-all ${
                mlbMode === mode
                  ? 'bg-[#00E5FF] text-black'
                  : 'bg-[#0E0E14] text-[#6E6E80] border border-[#1A1A28] hover:border-[#00E5FF]/30 hover:text-white'
              }`}
            >
              {mode === 'games' ? 'Games' : 'NRFI'}
            </button>
          ))}
        </div>
      )}

      {/* Soccer League Filter */}
      {selectedSport === 'soccer' && !isChinnyTab && (
        <div className="flex gap-2 mb-4">
          {SOCCER_LEAGUES.map((lg) => (
            <button
              key={lg.value}
              onClick={() => setSoccerLeague(lg.value)}
              className={`px-4 py-1.5 rounded-lg font-bold text-xs uppercase tracking-wider transition-all ${
                soccerLeague === lg.value
                  ? 'bg-[#00E5FF] text-black'
                  : 'bg-[#0E0E14] text-[#6E6E80] border border-[#1A1A28] hover:border-[#00E5FF]/30 hover:text-white'
              }`}
            >
              {lg.label}
            </button>
          ))}
        </div>
      )}

      {/* Analyze Button */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-black text-[#E8E8EC]">{SPORT_LABELS[selectedSport]} Games</h1>
          <p className="text-[#6E6E80] text-sm">{sortedGames?.length || 0} games on slate</p>
        </div>
        <button
          onClick={handleAnalyzeAll}
          disabled={analyzing}
          className="flex items-center gap-2 px-6 py-3 bg-[#00E5FF] text-black font-bold rounded-lg hover:bg-[#00E5FF]/90 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
        >
          {analyzing ? (
            <>
              <div className="w-4 h-4 border-2 border-black border-t-transparent rounded-full animate-spin" />
              AI Models Running...
            </>
          ) : (
            <>
              <span className="text-lg">⚡</span>
              Analyze All
            </>
          )}
        </button>
      </div>

      {/* Analysis status */}
      {analyzing && (
        <div className="mb-4 p-3 bg-[#00E5FF]/5 border border-[#00E5FF]/20 rounded-lg text-sm text-[#00E5FF]">
          Running AI analysis on {sortedGames?.length || 0} games...
        </div>
      )}
      {analyzeError && (
        <div className="mb-4 p-3 bg-rose-500/10 border border-rose-500/30 rounded-lg text-sm text-rose-400">
          Analysis error: {analyzeError}
        </div>
      )}

      {/* Games List with Two-Lane Cards */}
      <div className="space-y-4">
        {sortedGames?.map((game) => (
          <Link key={game.id} to={`/game/${game.id}`} className="block">
            <TwoLaneCard
              game={game}
              ourGrade={game.ourGrade || {grade: '-', score: 0, confidence: 0, thesis: ''}}
              aiGrade={game.aiGrade || {grade: '-', score: 0, confidence: 0, model: 'AI'}}
              convergence={game.convergence || {status: 'ALIGNED', consensusScore: 0, consensusGrade: '-', delta: 0, variance: 0}}
            />
          </Link>
        ))}
      </div>
    </div>
  )
}
