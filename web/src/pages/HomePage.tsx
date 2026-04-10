import { useState, useMemo } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { TwoLaneCard } from '@/components/TwoLaneCard'
import { getGames, analyzeGames } from '@/services/api'
import type { Sport } from '@/types'
import { SPORT_LABELS } from '@/types'

const SPORTS: Sport[] = ['nba', 'nhl', 'mlb', 'nfl', 'ncaab', 'soccer', 'mma', 'boxing', 'golf']

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
  const queryClient = useQueryClient()

  const apiMode = selectedSport === 'mlb' ? mlbMode : undefined
  const apiLeague = selectedSport === 'soccer' ? soccerLeague || undefined : undefined

  // Fetch games
  const { data: games, isLoading, error } = useQuery({
    queryKey: ['games', selectedSport, apiMode, apiLeague],
    queryFn: () => getGames(selectedSport, apiMode, apiLeague),
  })

  // Sort games by engine grade score desc; ungraded to the bottom
  const sortedGames = useMemo(() => {
    if (!Array.isArray(games)) return games
    const scoreOf = (g: any): number => {
      const s = g?.ourGrade?.score ?? g?.grade?.score ?? g?.score
      return typeof s === 'number' && s > 0 ? s : -Infinity
    }
    return [...games].sort((a, b) => scoreOf(b) - scoreOf(a))
  }, [games])

  // Deep AI analysis — calls /api/analyze which runs crowdsource + gatekeeper
  const handleAnalyzeAll = async () => {
    if (analyzing) return
    setAnalyzing(true)
    setAnalyzeError(null)

    try {
      const enriched = await analyzeGames(selectedSport)
      // Update the query cache with enriched games so cards re-render
      if (Array.isArray(enriched)) {
        queryClient.setQueryData(['games', selectedSport, apiMode, apiLeague], enriched)
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
      {selectedSport === 'soccer' && (
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
          <p className="text-[#6E6E80] text-sm">{games?.length || 0} games on slate</p>
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
          Running 10 real Azure AI models (Grok 4.1, Grok 3, DeepSeek R1, DeepSeek V3.2 Spec, Kimi K2 Thinking, Phi-4 Reasoning, GPT-4.1, GPT-5 Mini, o4-mini, Llama-4 Maverick) on {games?.length || 0} games... This may take 30-60 seconds.
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
