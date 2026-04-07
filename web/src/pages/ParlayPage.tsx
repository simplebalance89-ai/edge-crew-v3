import { useState, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Receipt, Layers, Check } from 'lucide-react'
import { getGames, toggleSlipLock as apiToggleSlipLock, generateBetSlip } from '@/services/api'
import { useAppStore } from '@/store/useAppStore'
import type { Game, Sport, BetSlip } from '@/types'
import { SPORT_LABELS } from '@/types'

const SPORTS: Sport[] = ['nba', 'nhl', 'mlb', 'nfl', 'ncaab', 'soccer', 'mma', 'boxing']

const gradeRank = (g?: string): number => {
  if (!g) return 0
  const map: Record<string, number> = {
    'A+': 100, A: 95, 'A-': 90,
    'B+': 85, B: 80, 'B-': 75,
    'C+': 70, C: 65, 'C-': 60,
    'D+': 55, D: 50, 'D-': 45,
    F: 10,
  }
  return map[g] ?? 0
}

const gradeColor = (g?: string) => {
  if (!g) return '#6E6E80'
  if (g.startsWith('A')) return '#10B981'
  if (g.startsWith('B')) return '#38BDF8'
  if (g.startsWith('C') || g.startsWith('D')) return '#F59E0B'
  return '#ef4444'
}

export default function ParlayPage() {
  const navigate = useNavigate()
  const { user, slipLocks, toggleSlipLock } = useAppStore()
  const [busyId, setBusyId] = useState<string | null>(null)
  const [slipLoading, setSlipLoading] = useState(false)
  const [slipError, setSlipError] = useState<string | null>(null)

  // Pull games for every sport
  const queries = SPORTS.map((sport) =>
    // eslint-disable-next-line react-hooks/rules-of-hooks
    useQuery<Game[]>({
      queryKey: ['games', sport],
      queryFn: () => getGames(sport).catch(() => []),
      staleTime: 60_000,
    })
  )

  const allGames = useMemo(() => {
    const merged: Game[] = []
    queries.forEach((q) => {
      if (q.data) merged.push(...q.data)
    })
    // Sort by engine grade desc
    return merged
      .filter((g) => g.pick && g.pick.side)
      .sort((a, b) => gradeRank(b.ourGrade?.grade) - gradeRank(a.ourGrade?.grade))
  }, [queries.map((q) => q.data).join('|')])

  const loading = queries.some((q) => q.isLoading)
  const selectedCount = slipLocks.length

  // Parlay count: with Peter's Rules max 2 parlays, 2-4 legs each
  const parlaysBuilt = selectedCount >= 4 ? 2 : selectedCount >= 2 ? 1 : 0

  const handleToggle = async (gameId: string) => {
    if (!user?.username) return
    setBusyId(gameId)
    const isLocked = slipLocks.includes(gameId)
    const action = isLocked ? 'remove' : 'add'
    try {
      await apiToggleSlipLock(user.username, gameId, action)
      toggleSlipLock(gameId)
    } catch (e) {
      console.error('Toggle slip lock failed:', e)
    } finally {
      setBusyId(null)
    }
  }

  const [betSlip, setBetSlip] = useState<BetSlip | null>(null)

  const handleGenerate = async () => {
    if (!user?.username || slipLocks.length === 0) return
    setSlipLoading(true)
    setSlipError(null)
    try {
      const slip = await generateBetSlip(user.username, slipLocks)
      if (slip.error) setSlipError(slip.error)
      else setBetSlip(slip)
    } catch (e) {
      setSlipError((e as Error).message || 'Failed to generate bet slip')
    }
    setSlipLoading(false)
  }

  if (!user) {
    return (
      <div className="text-center py-20">
        <Layers size={48} className="mx-auto mb-4 text-[#d4a017]" />
        <h2 className="text-xl font-bold mb-2">Log in to build your slip</h2>
        <p className="text-white/60">Go to Profile to log in.</p>
      </div>
    )
  }

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6 flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-black flex items-center gap-2">
            <Layers size={24} className="text-[#D4A017]" /> Build Slip
          </h1>
          <p className="text-sm text-white/50 mt-1">
            Pick which games to include. Sorted by engine grade.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="text-xs text-white/60 bg-white/5 border border-white/10 rounded-lg px-3 py-2">
            <span className="font-black text-[#D4A017]">{selectedCount}</span> picks selected
            <span className="text-white/30 mx-2">|</span>
            <span className="font-black text-[#D4A017]">{parlaysBuilt}</span> parlay{parlaysBuilt === 1 ? '' : 's'} will be built
          </div>
          <button
            onClick={handleGenerate}
            disabled={slipLoading || selectedCount === 0}
            className="flex items-center gap-2 px-5 py-2.5 bg-gradient-to-r from-[#D4A017] to-[#F5C842] text-black font-bold rounded-lg hover:opacity-90 disabled:opacity-40 transition-all"
          >
            {slipLoading ? (
              <>
                <div className="w-4 h-4 border-2 border-black border-t-transparent rounded-full animate-spin" />
                Generating...
              </>
            ) : (
              <>
                <Receipt size={18} />
                Generate Bet Slip
              </>
            )}
          </button>
        </div>
      </div>

      {slipError && (
        <div className="mb-4 p-3 bg-rose-500/10 border border-rose-500/30 rounded-lg text-sm text-rose-400">
          {slipError}
        </div>
      )}

      {loading && allGames.length === 0 && (
        <div className="text-center py-20 text-white/50">Loading games across all sports...</div>
      )}

      {/* Grid of games */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {allGames.map((g) => {
          const isLocked = slipLocks.includes(g.id)
          const isBusy = busyId === g.id
          const grade = g.ourGrade?.grade || '-'
          const score = g.ourGrade?.score ?? 0
          const pick = g.pick
          return (
            <div
              key={g.id}
              className={`rounded-xl p-3 border transition-all flex items-center gap-3 ${
                isLocked
                  ? 'bg-[#D4A017]/10 border-[#D4A017]/60'
                  : 'bg-[#0E0E14] border-[#1A1A28] hover:border-white/20'
              }`}
            >
              {/* Grade badge */}
              <div className="flex flex-col items-center justify-center w-14 shrink-0">
                <div className="text-[8px] text-white/40 font-bold tracking-wide">GRADE</div>
                <div className="text-2xl font-black leading-none" style={{ color: gradeColor(grade) }}>
                  {grade}
                </div>
                <div className="text-[9px] text-white/40">{score.toFixed(1)}</div>
              </div>

              {/* Game info */}
              <div className="flex-1 min-w-0">
                <div className="text-[9px] font-black tracking-wider text-white/40 uppercase">
                  {SPORT_LABELS[g.sport as Sport] || g.sport}
                </div>
                <div className="text-sm font-bold text-white truncate">
                  {g.awayTeam} <span className="text-white/30">@</span> {g.homeTeam}
                </div>
                {pick?.side && (
                  <div className="text-[11px] text-[#D4A017] font-black mt-0.5 truncate">
                    Pick: {pick.side}
                    {pick.type === 'spread' && pick.line !== 0
                      ? ` ${pick.line > 0 ? '+' : ''}${pick.line}`
                      : pick.type
                      ? ` ${pick.type.toUpperCase()}`
                      : ''}
                  </div>
                )}
              </div>

              {/* Toggle */}
              <button
                onClick={() => handleToggle(g.id)}
                disabled={isBusy}
                className={`shrink-0 flex items-center gap-1.5 px-3 py-2 rounded-lg text-[11px] font-black tracking-wider transition-all border ${
                  isLocked
                    ? 'bg-[#D4A017] text-black border-[#D4A017]'
                    : 'bg-white/5 text-white/60 border-white/15 hover:bg-[#D4A017]/15 hover:text-[#D4A017] hover:border-[#D4A017]/40'
                }`}
              >
                {isBusy ? (
                  <div className="w-3 h-3 border border-current border-t-transparent rounded-full animate-spin" />
                ) : isLocked ? (
                  <>
                    <Check size={12} /> INCLUDED
                  </>
                ) : (
                  'ADD'
                )}
              </button>
            </div>
          )
        })}
      </div>

      {!loading && allGames.length === 0 && (
        <div className="bg-[#1a1a1a] border border-white/10 rounded-xl p-8 text-center mt-6">
          <Layers size={48} className="mx-auto mb-4 text-[#d4a017]" />
          <h2 className="text-xl font-bold mb-2">No games available</h2>
          <p className="text-white/60">Load a sport from the Games tab first.</p>
        </div>
      )}

      {/* Minimal confirmation — defer to PicksPage for full modal */}
      {betSlip && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm"
          onClick={() => {
            setBetSlip(null)
            navigate('/picks')
          }}
        >
          <div
            className="bg-[#0E0E14] border border-[#D4A017]/40 rounded-2xl w-full max-w-md mx-4 p-6 text-center"
            onClick={(e) => e.stopPropagation()}
          >
            <Receipt size={40} className="mx-auto mb-3 text-[#D4A017]" />
            <h3 className="text-lg font-black mb-2">Slip Generated</h3>
            <p className="text-sm text-white/60 mb-4">
              Slip ID: <span className="font-mono text-[#D4A017]">{betSlip.slip_id}</span>
            </p>
            <button
              onClick={() => navigate('/picks')}
              className="w-full py-2.5 bg-gradient-to-r from-[#D4A017] to-[#F5C842] text-black font-bold rounded-lg"
            >
              View Full Slip in Picks
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
