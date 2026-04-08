import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, Lock, Check } from 'lucide-react'
import { TwoLaneCard } from '@/components/TwoLaneCard'
import { getGames, lockPick } from '@/services/api'
import { useAppStore } from '@/store/useAppStore'
import type { Game } from '@/types'

const gradeColor = (g: string) => {
  if (g?.startsWith('A')) return '#10B981'
  if (g?.startsWith('B')) return '#38BDF8'
  if (g?.startsWith('C') || g?.startsWith('D')) return '#F59E0B'
  return '#ef4444'
}

export default function GameDetailPage() {
  const { id } = useParams()
  const { user } = useAppStore()
  const [locking, setLocking] = useState(false)
  const [locked, setLocked] = useState(false)

  // Try all sports to find the game
  const sports = ['nba', 'nhl', 'mlb', 'nfl', 'ncaab', 'soccer', 'mma', 'boxing']

  const { data: allGames, isLoading } = useQuery({
    queryKey: ['all-games-detail', id],
    queryFn: async () => {
      const results = await Promise.allSettled(
        sports.map(s => getGames(s))
      )
      const games: Game[] = []
      results.forEach(r => {
        if (r.status === 'fulfilled' && Array.isArray(r.value)) {
          games.push(...r.value)
        }
      })
      return games
    },
  })

  const game = allGames?.find(g => g.id === id)

  const handleLockPick = async () => {
    if (!user?.username || !game?.pick?.side) return
    setLocking(true)
    try {
      await lockPick(user.username, {
        game_id: game.id,
        sport: game.sport?.toLowerCase() || '',
        team: game.pick.side,
        type: game.pick.type || 'ml',
        line: game.pick.line || 0,
        amount: 100,
        odds: -110,
      })
      setLocked(true)
      setTimeout(() => setLocked(false), 3000)
    } catch (e) {
      console.error('Lock pick failed:', e)
    }
    setLocking(false)
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-center">
          <div className="w-12 h-12 border-4 border-[#00E5FF] border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p className="text-[#6E6E80]">Loading game...</p>
        </div>
      </div>
    )
  }

  if (!game) {
    return (
      <div>
        <Link to="/" className="inline-flex items-center gap-2 text-white/60 hover:text-white mb-6 transition-colors">
          <ArrowLeft size={20} /> Back to games
        </Link>
        <div className="bg-[#1a1a1a] border border-white/10 rounded-xl p-8 text-center">
          <h1 className="text-2xl font-bold mb-4">Game Not Found</h1>
          <p className="text-white/60">No game found with ID: {id}</p>
        </div>
      </div>
    )
  }

  const ourGrade = game.ourGrade || { grade: '-', score: 0, confidence: 0, thesis: '' }
  const aiGrade = game.aiGrade || { grade: '-', score: 0, confidence: 0, model: 'AI' }
  const convergence = game.convergence || { status: 'ALIGNED' as const, consensusScore: 0, consensusGrade: '-', delta: 0, variance: 0 }
  const variables = ourGrade.variables as Record<string, { score: number; name: string; available: boolean; weight?: number; notes?: string }> | undefined
  const pick = game.pick
  const ev = game.ev

  return (
    <div className="max-w-4xl mx-auto">
      {/* Back button */}
      <Link to="/" className="inline-flex items-center gap-2 text-white/60 hover:text-white mb-6 transition-colors">
        <ArrowLeft size={20} /> Back to games
      </Link>

      {/* Full TwoLaneCard */}
      <TwoLaneCard
        game={game}
        ourGrade={ourGrade}
        aiGrade={aiGrade}
        convergence={convergence}
      />

      {/* Lock Pick button (standalone, prominent) */}
      {pick && pick.side && user && (
        <div className="mt-4 flex justify-center">
          <button
            onClick={handleLockPick}
            disabled={locking || locked}
            className={`flex items-center gap-2 px-8 py-3 rounded-xl text-sm font-bold transition-all ${
              locked
                ? 'bg-emerald-500/20 border-2 border-emerald-500/60 text-emerald-400'
                : 'bg-gradient-to-r from-[#D4A017] to-[#F59E0B] text-black hover:opacity-90'
            }`}
          >
            {locked ? <><Check size={16} /> Pick Locked!</> : locking ? <><div className="w-4 h-4 border-2 border-black border-t-transparent rounded-full animate-spin" /> Locking...</> : <><Lock size={16} /> Lock Pick: {pick.side} {pick.type === 'spread' && pick.line !== 0 ? `${pick.line > 0 ? '+' : ''}${pick.line}` : pick.type.toUpperCase()}</>}
          </button>
        </div>
      )}

      {/* ═══ EXPANDED DETAILS ═══ */}
      <div className="mt-6 space-y-4">

        {/* ── FULL VARIABLE BREAKDOWN ── */}
        {variables && Object.keys(variables).length > 0 && (
          <div className="bg-[#0E0E14] border border-[#1A1A28] rounded-xl p-5">
            <h2 className="text-sm font-black tracking-[2px] text-[#F72585] mb-4">FULL VARIABLE BREAKDOWN</h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-1">
              {Object.entries(variables)
                .sort(([, a], [, b]) => b.score - a.score)
                .map(([key, v]) => (
                  <div key={key} className={`flex items-center justify-between py-2 border-b border-white/[0.06] ${!v.available ? 'opacity-40' : ''}`}>
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-bold text-white/80">{v.name}</span>
                        {!v.available && <span className="text-[8px] text-white/30 bg-white/5 px-1.5 py-0.5 rounded">N/A</span>}
                      </div>
                      {v.weight != null && (
                        <span className="text-[10px] text-white/30">Weight: {v.weight}x</span>
                      )}
                      {v.notes && (
                        <div className="text-[10px] text-white/35 mt-0.5 leading-snug">{v.notes}</div>
                      )}
                    </div>
                    <div className="flex items-center gap-2 ml-4">
                      <div className="w-20 h-1.5 bg-white/[0.06] rounded-full overflow-hidden">
                        <div
                          className="h-full rounded-full transition-all"
                          style={{
                            width: `${(v.score / 10) * 100}%`,
                            backgroundColor: v.score >= 7 ? '#10B981' : v.score >= 5 ? '#d4a024' : '#ef4444',
                          }}
                        />
                      </div>
                      <span className="text-sm font-black w-6 text-right" style={{ color: v.score >= 7 ? '#10B981' : v.score >= 5 ? '#d4a024' : '#ef4444' }}>
                        {v.score}
                      </span>
                    </div>
                  </div>
                ))}
            </div>
            <div className="mt-3 pt-3 border-t border-white/[0.08] flex items-center justify-between">
              <span className="text-xs text-white/40">Engine Score</span>
              <span className="text-lg font-black" style={{ color: gradeColor(ourGrade.grade) }}>{ourGrade.score.toFixed(1)} ({ourGrade.grade})</span>
            </div>
          </div>
        )}

        {/* ── AI MODEL THESES (FULL) ── */}
        {game.aiModels && game.aiModels.length > 0 && (
          <div className="bg-[#0E0E14] border border-[#1A1A28] rounded-xl p-5">
            <h2 className="text-sm font-black tracking-[2px] text-[#00D4AA] mb-4">AI MODEL ANALYSIS ({game.aiModels.length} MODELS)</h2>
            <div className="space-y-4">
              {game.aiModels.map((m, i) => (
                <div key={i} className="bg-white/[0.02] border border-white/[0.08] rounded-lg p-4">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-3">
                      <span className="text-xs font-black text-[#00D4AA] uppercase">{m.model}</span>
                      {(() => {
                        const src = (m as any).source || 'real';
                        const label = src === 'real' ? 'LIVE' : src === 'math_fallback' ? 'MATH' : 'STUB';
                        const cls = src === 'real'
                          ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
                          : src === 'math_fallback'
                          ? 'bg-amber-500/20 text-amber-300 border-amber-500/40'
                          : 'bg-rose-500/20 text-rose-300 border-rose-500/40';
                        return <span className={`text-[9px] font-black px-1.5 py-0.5 rounded border ${cls}`}>{label}</span>;
                      })()}
                      <span className="text-lg font-black" style={{ color: gradeColor(m.grade) }}>{m.grade}</span>
                      <span className="text-xs text-white/40">Score: {m.score}</span>
                      <span className="text-xs text-white/40">Conf: {m.confidence}%</span>
                    </div>
                    {(m as any).pick && (
                      <span className="text-xs font-bold px-2 py-1 rounded bg-[#38BDF8]/15 text-[#38BDF8] border border-[#38BDF8]/30">
                        {(m as any).pick}
                      </span>
                    )}
                  </div>
                  {m.thesis && (
                    <p className="text-xs text-white/50 leading-relaxed">{m.thesis}</p>
                  )}
                  {m.key_factors && m.key_factors.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1">
                      {m.key_factors.map((f, j) => (
                        <span key={j} className="text-[9px] px-1.5 py-0.5 bg-[#00D4AA]/10 border border-[#00D4AA]/25 text-[#00D4AA]/70 rounded">
                          {f}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ── EV BREAKDOWN ── */}
        {ev && ev.ev_pct != null && (
          <div className="bg-[#0E0E14] border border-[#1A1A28] rounded-xl p-5">
            <h2 className="text-sm font-black tracking-[2px] text-[#D4A017] mb-4">EV BREAKDOWN</h2>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
              <div className="bg-white/[0.03] border border-white/[0.08] rounded-lg p-3 text-center">
                <div className="text-[10px] text-white/35 font-bold tracking-wide mb-1">EXPECTED VALUE</div>
                <div className={`text-2xl font-black ${ev.ev_pct >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                  {ev.ev_pct > 0 ? '+' : ''}{ev.ev_pct}%
                </div>
              </div>
              <div className="bg-white/[0.03] border border-white/[0.08] rounded-lg p-3 text-center">
                <div className="text-[10px] text-white/35 font-bold tracking-wide mb-1">EV GRADE</div>
                <div className="text-2xl font-black" style={{ color: gradeColor(ev.ev_grade) }}>{ev.ev_grade}</div>
              </div>
              <div className="bg-white/[0.03] border border-white/[0.08] rounded-lg p-3 text-center">
                <div className="text-[10px] text-white/35 font-bold tracking-wide mb-1">MONEYLINE</div>
                <div className="text-xl font-bold text-white/70">{ev.moneyline != null ? (ev.moneyline > 0 ? '+' : '') + ev.moneyline : '-'}</div>
              </div>
              <div className="bg-white/[0.03] border border-white/[0.08] rounded-lg p-3 text-center">
                <div className="text-[10px] text-white/35 font-bold tracking-wide mb-1">IMPLIED PROB</div>
                <div className="text-xl font-bold text-white/70">{ev.implied_prob != null ? `${(ev.implied_prob * 100).toFixed(1)}%` : '-'}</div>
              </div>
              <div className="bg-white/[0.03] border border-white/[0.08] rounded-lg p-3 text-center">
                <div className="text-[10px] text-white/35 font-bold tracking-wide mb-1">TRUE PROB</div>
                <div className="text-xl font-bold text-emerald-400">{ev.true_prob != null ? `${(ev.true_prob * 100).toFixed(1)}%` : '-'}</div>
              </div>
              <div className="bg-white/[0.03] border border-white/[0.08] rounded-lg p-3 text-center">
                <div className="text-[10px] text-white/35 font-bold tracking-wide mb-1">EDGE</div>
                <div className={`text-xl font-bold ${ev.edge != null && ev.edge >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                  {ev.edge != null ? `${ev.edge > 0 ? '+' : ''}${(ev.edge * 100).toFixed(1)}%` : '-'}
                </div>
              </div>
            </div>

            {/* Kelly calculation */}
            <div className="mt-4 bg-white/[0.03] border border-white/[0.08] rounded-lg p-4">
              <div className="text-[10px] text-white/35 font-bold tracking-wide mb-2">KELLY CRITERION</div>
              <div className="flex items-center justify-between">
                <div>
                  <span className="text-xs text-white/50">Recommended Sizing: </span>
                  <span className="text-sm font-black text-[#D4A017]">{ev.kelly_units}</span>
                </div>
                {ev.true_prob != null && ev.implied_prob != null && (
                  <div className="text-xs text-white/35">
                    Kelly = (p * b - q) / b where p={(ev.true_prob).toFixed(3)}, q={((1 - ev.true_prob)).toFixed(3)}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* ── PETER'S RULES (EXPANDED) ── */}
        {game.peterRules && (
          <div className="bg-[#0E0E14] border border-[#1A1A28] rounded-xl p-5">
            <h2 className="text-sm font-black tracking-[2px] text-amber-400 mb-4">PETER'S RULES</h2>

            {game.peterRules.has_kill && (
              <div className="mb-4 py-3 bg-rose-500/20 border border-rose-500/50 rounded-lg text-center">
                <span className="text-lg font-black text-rose-400 tracking-wider">KILL SWITCH ACTIVE</span>
                <p className="text-xs text-rose-400/60 mt-1">This game has triggered a hard kill rule</p>
              </div>
            )}

            {game.peterRules.flags.length > 0 ? (
              <div className="space-y-2">
                {game.peterRules.flags.map((f, i) => (
                  <div key={i} className={`flex items-start gap-3 p-3 rounded-lg border ${
                    f.action === 'KILL' ? 'bg-rose-500/10 border-rose-500/30' :
                    f.action === 'BOOST' ? 'bg-emerald-500/10 border-emerald-500/30' :
                    'bg-amber-500/10 border-amber-500/30'
                  }`}>
                    <span className={`text-xs font-black px-2 py-1 rounded shrink-0 ${
                      f.action === 'KILL' ? 'bg-rose-500/20 text-rose-400' :
                      f.action === 'BOOST' ? 'bg-emerald-500/20 text-emerald-400' :
                      'bg-amber-500/20 text-amber-400'
                    }`}>
                      {f.action}
                    </span>
                    <div className="flex-1 min-w-0">
                      <div className="text-xs font-bold text-white/70">{f.rule}</div>
                      <div className="text-xs text-white/40 mt-0.5">{f.note}</div>
                      <div className="text-[10px] text-white/25 mt-0.5">Severity: {f.severity}</div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-4">
                <span className="text-emerald-400 font-bold text-sm">CLEAN - No flags triggered</span>
                <p className="text-xs text-white/30 mt-1">All rules passed</p>
              </div>
            )}

            {game.peterRules.adjustment !== 0 && (
              <div className="mt-3 pt-3 border-t border-white/[0.08] flex justify-between items-center">
                <span className="text-xs text-white/40">Total Adjustment</span>
                <span className={`text-sm font-black ${game.peterRules.adjustment > 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                  {game.peterRules.adjustment > 0 ? '+' : ''}{game.peterRules.adjustment}
                </span>
              </div>
            )}
          </div>
        )}

        {/* ── GATEKEEPER DETAIL ── */}
        {game.gatekeeper && game.gatekeeper.action && (
          <div className="bg-[#0E0E14] border border-[#1A1A28] rounded-xl p-5">
            <h2 className="text-sm font-black tracking-[2px] text-purple-400 mb-4">KIMI GATEKEEPER</h2>
            <div className={`p-4 rounded-lg border ${
              game.gatekeeper.action === 'BOOST' ? 'bg-emerald-500/10 border-emerald-500/30' :
              game.gatekeeper.action === 'CHALLENGE' ? 'bg-rose-500/10 border-rose-500/30' :
              'bg-[#D4A017]/10 border-[#D4A017]/30'
            }`}>
              <div className="flex items-center gap-3 mb-2">
                <span className={`text-lg font-black ${
                  game.gatekeeper.action === 'BOOST' ? 'text-emerald-400' :
                  game.gatekeeper.action === 'CHALLENGE' ? 'text-rose-400' :
                  'text-[#D4A017]'
                }`}>
                  {game.gatekeeper.action}
                </span>
                {game.gatekeeper.adjustment !== 0 && (
                  <span className="text-sm font-bold text-white/50">
                    ({game.gatekeeper.adjustment > 0 ? '+' : ''}{game.gatekeeper.adjustment} adjustment)
                  </span>
                )}
              </div>
              {game.gatekeeper.reason && (
                <p className="text-xs text-white/50 leading-relaxed">{game.gatekeeper.reason}</p>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
