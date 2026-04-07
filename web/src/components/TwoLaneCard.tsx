import { useState, type MouseEvent } from 'react'
import { Lock, Check } from 'lucide-react'
import { useAppStore } from '@/store/useAppStore'
import { lockPick, submitGutPick } from '@/services/api'
import type { Game, Grade, ConvergenceResult } from '@/types'

interface TwoLaneCardProps {
  game: Game
  ourGrade?: Grade
  aiGrade?: Grade & { model?: string }
  convergence?: ConvergenceResult['convergence']
}

const gradeColor = (g: string) => {
  if (g?.startsWith('A')) return '#10B981'
  if (g?.startsWith('B')) return '#38BDF8'
  if (g?.startsWith('C') || g?.startsWith('D')) return '#F59E0B'
  return '#ef4444'
}

export function TwoLaneCard({ game, ourGrade, aiGrade, convergence }: TwoLaneCardProps) {
  const { user } = useAppStore()
  const [locking, setLocking] = useState(false)
  const [locked, setLocked] = useState(false)
  const [gutActive, setGutActive] = useState(false)
  const [gutToast, setGutToast] = useState<string | null>(null)

  const handleGutPick = async (e: MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    if (!user?.username || !game.pick?.side) return
    const enginePick = game.pick.side
    const opposite = enginePick === game.homeTeam ? game.awayTeam : game.homeTeam
    const confirmed = window.confirm(
      `GUT PICK: Override engine's pick on ${enginePick}?\n\nYour gut pick will be: ${opposite}\n\n(1 gut pick per sport per day)`
    )
    if (!confirmed) return
    try {
      await submitGutPick({
        username: user.username,
        game_id: game.id,
        sport: (game.sport || '').toUpperCase(),
        pick_side: opposite,
        engine_pick_side: enginePick,
      })
      setGutActive(true)
      setGutToast(`GUT PICK logged: ${opposite}`)
      setTimeout(() => setGutToast(null), 3000)
    } catch (err: any) {
      const status = err?.response?.status
      if (status === 400) {
        setGutToast(`Already used your gut pick for ${(game.sport || '').toUpperCase()} today`)
      } else {
        setGutToast('Failed to log gut pick')
      }
      setTimeout(() => setGutToast(null), 3000)
    }
  }

  const handleLockPick = async (amount: number) => {
    if (!user?.username || !game.pick?.side) return
    setLocking(true)
    try {
      await lockPick(user.username, {
        game_id: game.id,
        sport: game.sport?.toLowerCase() || '',
        team: game.pick.side,
        type: game.pick.type || 'ml',
        line: game.pick.line || 0,
        amount,
        odds: -110,
      })
      setLocked(true)
      setTimeout(() => setLocked(false), 3000)
    } catch (e) {
      console.error('Lock pick failed:', e)
    }
    setLocking(false)
  }

  const displayStatus = convergence?.status || 'PENDING'
  const displayOur = ourGrade || { score: 0, grade: '-', confidence: 0, thesis: '' }
  const displayAI = aiGrade || { score: 0, grade: '-', confidence: 0, model: 'AI' }
  const consensusScore = convergence?.consensusScore || 0
  const consensusGrade = convergence?.consensusGrade || '-'
  const delta = convergence?.delta || 0
  const pick = game.pick

  const statusStyles: Record<string, string> = {
    LOCK: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/40',
    ALIGNED: 'bg-[#38BDF8]/15 text-[#38BDF8] border-[#38BDF8]/40',
    CLOSE: 'bg-amber-500/15 text-amber-400 border-amber-500/40',
    SPLIT: 'bg-rose-500/15 text-rose-400 border-rose-500/40',
    PENDING: 'bg-white/5 text-white/40 border-white/15',
  }

  return (
    <div className="bg-[#0E0E14] border rounded-xl p-4 transition-all border-[#1A1A28] hover:border-[#1A1A28]/80">
      {/* ─── HEADER ─── */}
      <div className="flex justify-between items-start mb-3">
        <div>
          <h3 className="text-base font-bold text-[#E8E8EC]">{game.awayTeam} <span className="text-[#6E6E80] font-normal">@</span> {game.homeTeam}</h3>
          <div className="flex items-center gap-3 mt-1">
            <span className="text-xs text-[#6E6E80]">
              {game.scheduledAt ? new Date(game.scheduledAt).toLocaleDateString([], { month: 'short', day: 'numeric' }) + ' ' + new Date(game.scheduledAt).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' }) : ''}
            </span>
            {game.odds && (
              <>
                {game.odds.spread !== 0 && <span className="text-xs text-[#6E6E80]">Spread: {game.odds.spread > 0 ? '+' : ''}{game.odds.spread}</span>}
                {game.odds.total > 0 && <span className="text-xs text-[#6E6E80]">O/U: {game.odds.total}</span>}
                {game.odds.mlHome !== 0 && <span className="text-xs text-[#6E6E80]">ML: {game.odds.mlAway}/{game.odds.mlHome}</span>}
              </>
            )}
          </div>
        </div>
        <div className="flex flex-col items-end gap-1">
          <span className={`px-3 py-1 rounded-full text-[10px] font-black tracking-wider border ${statusStyles[displayStatus] || statusStyles.PENDING}`}>
            {displayStatus}
          </span>
          {game.arbitrage?.has_arb && (
            <div className="text-right">
              <span className="px-2 py-0.5 rounded-full text-[9px] font-black tracking-wider bg-gradient-to-r from-red-500/20 to-yellow-500/20 border border-yellow-500/50 text-yellow-400">
                ARB {game.arbitrage.arb_pct}%
              </span>
              <div className="text-[8px] text-yellow-400/70 mt-0.5">
                Home: {game.arbitrage.best_home.book} {game.arbitrage.best_home.odds} | Away: {game.arbitrage.best_away.book} {game.arbitrage.best_away.odds}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* ═══ TWO-LANE FORK ═══ */}
      <div className="grid grid-cols-2 gap-3 mb-3">

        {/* ── LEFT LANE: OUR PROCESS ── */}
        <div className="bg-[#F72585]/[0.04] border border-[#F72585]/20 rounded-xl p-3">
          <div className="text-[10px] font-black tracking-[1.5px] text-[#F72585] mb-2 pb-1.5 border-b border-white/[0.06]">OUR PROCESS</div>

          {/* Main Matrix — top variable scores */}
          {displayOur.variables && Object.keys(displayOur.variables).length > 0 && (
            <div className="mb-2">
              <div className="text-[9px] text-white/35 font-bold tracking-wide mb-1">MAIN MATRIX</div>
              {Object.entries(displayOur.variables as Record<string, {score: number; name: string; available: boolean}>)
                .filter(([, v]) => v.available)
                .sort(([, a], [, b]) => b.score - a.score)
                .slice(0, 8)
                .map(([key, v]) => (
                  <div key={key} className="flex justify-between text-[10px] py-[1px]">
                    <span className="text-white/50">{v.name}</span>
                    <span className="font-bold" style={{ color: v.score >= 7 ? '#10B981' : v.score >= 5 ? '#d4a024' : '#ef4444' }}>
                      {v.score}
                    </span>
                  </div>
                ))}
            </div>
          )}

          {/* Chains fired */}
          {displayOur.keyFactors && displayOur.keyFactors.length > 0 && (
            <div className="mb-2 flex flex-wrap gap-1">
              {displayOur.keyFactors.map((chain: string, i: number) => (
                <span key={i} className="text-[8px] px-1.5 py-0.5 bg-[#F72585]/10 border border-[#F72585]/30 text-[#F72585] rounded">
                  {chain}
                </span>
              ))}
            </div>
          )}

          {/* Grader Cards: Sintonia, Edge, Renzo */}
          {displayOur.profiles && Object.keys(displayOur.profiles).length > 0 && (
            <div className="grid grid-cols-4 gap-1.5 mb-2">
              {Object.entries(displayOur.profiles as Record<string, {grade: string; final: number; sizing: string; picks?: string; margin?: number}>).map(([name, p]) => {
                const colors: Record<string, string> = { sintonia: '#F72585', edge: '#818cf8', renzo: '#9B59B6', crew: '#D4A017' }
                const pickLabel = p.picks === 'home' ? game.homeTeam?.split(' ').pop() : p.picks === 'away' ? game.awayTeam?.split(' ').pop() : ''
                return (
                  <div key={name} className="bg-white/[0.03] border border-white/[0.08] rounded-lg p-2 text-center">
                    <div className="text-[8px] font-black uppercase" style={{ color: colors[name] || '#F72585' }}>{name}</div>
                    <div className="text-[20px] font-black leading-tight" style={{ color: gradeColor(p.grade) }}>{p.grade}</div>
                    <div className="text-[9px] text-white/40">{p.final.toFixed(1)}</div>
                    {p.sizing && p.sizing !== 'PASS' && (
                      <div className="text-[8px] text-white/50 mt-0.5">{p.sizing}</div>
                    )}
                    {pickLabel && (
                      <div className="text-[8px] font-bold mt-0.5" style={{ color: colors[name] || '#F72585' }}>{pickLabel}</div>
                    )}
                  </div>
                )
              })}
            </div>
          )}

          {/* Engine Grade Card */}
          <div className="text-center py-2 bg-white/[0.03] border border-white/[0.08] rounded-lg">
            <div className="text-[9px] font-black text-[#F72585] tracking-wide">ENGINE GRADE</div>
            <div className="text-[28px] font-black leading-tight" style={{ color: gradeColor(displayOur.grade) }}>
              {displayOur.grade}
            </div>
            <div className="text-[10px] text-white/40">{displayOur.score.toFixed(1)}</div>
            <div className="text-[10px] text-white/30">{displayOur.confidence}% conf</div>
          </div>
        </div>

        {/* ── RIGHT LANE: AI PROCESS ── */}
        <div className="bg-[#00D4AA]/[0.04] border border-[#00D4AA]/20 rounded-xl p-3">
          <div className="text-[10px] font-black tracking-[1.5px] text-[#00D4AA] mb-2 pb-1.5 border-b border-white/[0.06]">AI PROCESS</div>

          {/* Per-model grade cards */}
          {game.aiModels && game.aiModels.length > 0 ? (
            <>
              <div className="text-[9px] text-white/35 font-bold tracking-wide mb-1">MODEL GRADES</div>
              <div className="grid grid-cols-3 gap-1.5 mb-2">
                {game.aiModels.map((m, i) => (
                  <div key={i} className="bg-white/[0.03] border border-white/[0.08] rounded-lg p-1.5 text-center">
                    <div className="text-[7px] font-black text-[#00D4AA] uppercase truncate">{m.model}</div>
                    <div className="text-[18px] font-black leading-tight" style={{ color: gradeColor(m.grade) }}>
                      {m.grade}
                    </div>
                    <div className="text-[9px] text-white/40">{m.score}</div>
                    {(m as any).pick && <div className="text-[7px] font-bold text-[#00D4AA] mt-0.5 truncate">{(m as any).pick}</div>}
                  </div>
                ))}
              </div>
              {/* Per-model thesis */}
              <div className="space-y-1.5 border-t border-white/[0.06] pt-2">
                {game.aiModels.map((m, i) => (
                  <div key={i}>
                    <div className="flex items-center gap-1">
                      <span className="text-[8px] font-bold text-[#00D4AA]/80">{m.model}</span>
                      <span className="text-[8px] font-mono text-white/50">{m.grade}</span>
                      {(m as any).pick && <span className="text-[8px] font-bold text-[#38BDF8]">{(m as any).pick}</span>}
                    </div>
                    {m.thesis && (
                      <div className="text-[9px] text-white/35 leading-snug line-clamp-2">{m.thesis}</div>
                    )}
                  </div>
                ))}
              </div>
            </>
          ) : (
            <>
              {/* Odds-model fallback */}
              <div className="text-center py-2 bg-white/[0.03] border border-white/[0.08] rounded-lg">
                <div className="text-[9px] font-black text-[#00D4AA] tracking-wide">{(displayAI as any).model || 'ODDS MODEL'}</div>
                <div className="text-[28px] font-black leading-tight" style={{ color: gradeColor(displayAI.grade) }}>
                  {displayAI.grade}
                </div>
                <div className="text-[10px] text-white/40">{displayAI.score.toFixed(1)}</div>
              </div>
              <div className="mt-3 text-center text-[9px] text-white/20 italic">
                Click Analyze All for AI model reasoning
              </div>
            </>
          )}
        </div>
      </div>

      {/* ═══ NRFI VERDICT (replaces convergence header when present) ═══ */}
      {game.nrfi ? (
        <div className="bg-[#D4A017]/[0.06] border border-[#D4A017]/25 rounded-xl p-4 text-center mb-3">
          <div className="text-[10px] font-black tracking-[2px] text-[#D4A017] mb-2">NRFI ANALYSIS</div>

          {/* NRFI verdict badge */}
          <span className={`inline-block px-4 py-1.5 rounded-full text-sm font-black tracking-wider border ${
            game.nrfi.verdict === 'NRFI'
              ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/40'
              : game.nrfi.verdict === 'YRFI'
              ? 'bg-rose-500/15 text-rose-400 border-rose-500/40'
              : 'bg-white/10 text-white/50 border-white/20'
          }`}>
            {game.nrfi.verdict}
          </span>

          <div className="text-lg font-black mt-2" style={{ color: game.nrfi.verdict === 'NRFI' ? '#10B981' : game.nrfi.verdict === 'YRFI' ? '#EF4444' : '#6E6E80' }}>
            {game.nrfi.confidence}% confidence
          </div>

          <div className="text-[10px] text-white/40 mt-1 leading-snug max-w-md mx-auto">
            {game.nrfi.reason}
          </div>
        </div>
      ) : null}

      {/* ═══ CONVERGENCE ═══ */}
      <div className="bg-[#D4A017]/[0.06] border border-[#D4A017]/25 rounded-xl p-4 text-center">
        <div className="text-[10px] font-black tracking-[2px] text-[#D4A017] mb-2">CONVERGENCE</div>

        {/* Status badge */}
        <span className={`inline-block px-3.5 py-1 rounded-full text-[11px] font-black tracking-wider border ${statusStyles[displayStatus] || statusStyles.PENDING}`}>
          {displayStatus}
        </span>

        {/* Score comparison */}
        <div className="flex justify-center items-center gap-6 mt-3">
          <div className="text-center">
            <div className="text-[9px] text-[#F72585] font-bold">OUR</div>
            <div className="text-xl font-black" style={{ color: gradeColor(displayOur.grade) }}>
              {displayOur.score.toFixed(1)}
            </div>
          </div>
          <div className="text-xl text-white/15">vs</div>
          <div className="text-center">
            <div className="text-[9px] text-[#00D4AA] font-bold">AI</div>
            <div className="text-xl font-black" style={{ color: gradeColor(displayAI.grade) }}>
              {displayAI.score.toFixed(1)}
            </div>
          </div>
        </div>

        {/* Final grade */}
        <div className="text-[42px] font-black leading-none mt-2" style={{ color: gradeColor(consensusGrade) }}>
          {consensusGrade}
        </div>
        <div className="text-xs text-white/40">{consensusScore.toFixed(1)} | {'\u0394'} {delta.toFixed(2)}</div>

        {/* Pick + Lock Button */}
        {pick && pick.side && user && (
          <div className="mt-3 flex items-center justify-center gap-2 flex-wrap">
            <button
              onClick={handleGutPick}
              title="Override engine's pick (1 per sport per day)"
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[11px] font-black tracking-wider transition-all border ${
                gutActive
                  ? 'bg-purple-500 text-white border-purple-500'
                  : 'bg-white/5 text-white/60 border-white/15 hover:bg-purple-500/15 hover:text-purple-300 hover:border-purple-500/40'
              }`}
            >
              {gutActive ? 'GUT ✓' : 'GUT PICK'}
            </button>
            {gutActive && (
              <span className="px-2 py-0.5 rounded-full text-[9px] font-black tracking-wider bg-purple-500/20 border border-purple-500/50 text-purple-300">
                GUT
              </span>
            )}
          </div>
        )}
        {gutToast && (
          <div className="mt-2 text-center text-[10px] font-bold text-purple-300">{gutToast}</div>
        )}
        {pick && pick.side && (
          <div className="mt-3 flex items-center justify-center gap-2">
            <div className="inline-block bg-[#D4A017]/15 border border-[#D4A017]/30 text-[#D4A017] text-sm font-extrabold py-2 px-4 rounded-lg">
              {pick.side}
              {pick.type === 'spread' && pick.line !== 0 ? ` ${pick.line > 0 ? '+' : ''}${pick.line}` : ` ${pick.type.toUpperCase()}`}
              {pick.sizing && pick.sizing !== 'No Play' ? ` (${pick.sizing})` : ''}
            </div>
            {user && (
              locked ? (
                <span className="flex items-center gap-1 px-3 py-2 rounded-lg text-[11px] font-bold bg-emerald-500/20 border border-emerald-500/40 text-emerald-400">
                  <Check size={12} /> Locked!
                </span>
              ) : locking ? (
                <span className="flex items-center gap-1 px-3 py-2 rounded-lg text-[11px] font-bold bg-white/5 border border-white/15 text-white/40">
                  <div className="w-3 h-3 border border-white/40 border-t-transparent rounded-full animate-spin" /> ...
                </span>
              ) : (
                <div className="flex items-center gap-1.5">
                  <button
                    onClick={(e) => { e.preventDefault(); handleLockPick(50) }}
                    className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-[11px] font-medium transition-all bg-white/5 border border-white/15 text-white/60 hover:bg-[#D4A017]/15 hover:text-[#D4A017] hover:border-[#D4A017]/30"
                  >
                    <Lock size={10} /> $50
                  </button>
                  <button
                    onClick={(e) => { e.preventDefault(); handleLockPick(100) }}
                    className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-[11px] font-black transition-all bg-[#D4A017]/15 border border-[#D4A017]/40 text-[#D4A017] hover:bg-[#D4A017]/25 hover:border-[#D4A017]/60"
                  >
                    <Lock size={10} /> $100
                  </button>
                </div>
              )
            )}
          </div>
        )}

        {/* ── EV Display ── */}
        {game.ev && game.ev.ev_pct !== null && game.ev.ev_pct !== undefined && (
          <div className="mt-3 flex items-center justify-center gap-4">
            <div className="text-center">
              <div className="text-[9px] text-white/35 font-bold tracking-wide">EV%</div>
              <div className={`text-lg font-black ${game.ev.ev_pct >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                {game.ev.ev_pct > 0 ? '+' : ''}{game.ev.ev_pct}%
              </div>
            </div>
            <div className="text-center">
              <div className="text-[9px] text-white/35 font-bold tracking-wide">EV GRADE</div>
              <div className="text-lg font-black" style={{ color: gradeColor(game.ev.ev_grade) }}>
                {game.ev.ev_grade}
              </div>
            </div>
            <div className="text-center">
              <div className="text-[9px] text-white/35 font-bold tracking-wide">KELLY</div>
              <div className="text-sm font-bold text-white/70">{game.ev.kelly_units}</div>
            </div>
            <div className="text-center">
              <div className="text-[9px] text-white/35 font-bold tracking-wide">WIN PROB</div>
              <div className="text-sm font-bold text-white/70">
                {game.ev.true_prob != null ? `${(game.ev.true_prob * 100).toFixed(1)}%` : '-'}
              </div>
            </div>
            {game.ev.edge != null && (
              <div className="text-center">
                <div className="text-[9px] text-white/35 font-bold tracking-wide">EDGE</div>
                <div className={`text-sm font-bold ${game.ev.edge >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                  {game.ev.edge > 0 ? '+' : ''}{(game.ev.edge * 100).toFixed(1)}%
                </div>
              </div>
            )}
          </div>
        )}

        {/* ── Peter's Rules ── */}
        {game.peterRules && (
          <div className="mt-3">
            {game.peterRules.has_kill && (
              <div className="mb-2 text-center py-2 bg-rose-500/20 border border-rose-500/50 rounded-lg">
                <span className="text-sm font-black text-rose-400 tracking-wider">PETER SAYS: KILL</span>
              </div>
            )}
            {game.peterRules.flags.length > 0 ? (
              <div className="flex flex-wrap justify-center gap-1.5">
                {game.peterRules.flags.map((f, i) => (
                  <div key={i} className={`px-2 py-1 rounded-md border text-[9px] font-bold ${
                    f.action === 'KILL' ? 'bg-rose-500/15 border-rose-500/40 text-rose-400' :
                    f.action === 'BOOST' ? 'bg-emerald-500/15 border-emerald-500/40 text-emerald-400' :
                    'bg-amber-500/15 border-amber-500/40 text-amber-400'
                  }`}>
                    <span className="font-black">{f.action}</span>
                    <span className="ml-1 font-normal text-white/50">{f.note}</span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center text-[10px] text-emerald-400 font-bold">CLEAN — No flags</div>
            )}
          </div>
        )}

        {/* ── Kalshi ── */}
        {game.kalshi_prob != null && (
          <div className="mt-2 text-center text-[10px] text-[#38BDF8] font-bold">
            Kalshi: {(game.kalshi_prob * 100).toFixed(0)}% implied
          </div>
        )}

        {/* Kimi Gatekeeper */}
        {game.gatekeeper && game.gatekeeper.action && (
          <div className={`mt-3 p-2.5 rounded-lg border ${
            game.gatekeeper.action === 'BOOST' ? 'bg-emerald-500/10 border-emerald-500/30' :
            game.gatekeeper.action === 'CHALLENGE' ? 'bg-rose-500/10 border-rose-500/30' :
            'bg-[#D4A017]/10 border-[#D4A017]/30'
          }`}>
            <div className="flex items-center justify-center gap-2 mb-1">
              <span className={`text-[10px] font-black tracking-wider ${
                game.gatekeeper.action === 'BOOST' ? 'text-emerald-400' :
                game.gatekeeper.action === 'CHALLENGE' ? 'text-rose-400' :
                'text-[#D4A017]'
              }`}>
                KIMI GATEKEEPER
              </span>
              <span className={`text-xs font-black ${
                game.gatekeeper.action === 'BOOST' ? 'text-emerald-400' :
                game.gatekeeper.action === 'CHALLENGE' ? 'text-rose-400' :
                'text-[#D4A017]'
              }`}>
                {game.gatekeeper.action === 'BOOST' ? '▲' : game.gatekeeper.action === 'CHALLENGE' ? '▼' : '✓'} {game.gatekeeper.action}
                {game.gatekeeper.adjustment !== 0 && ` (${game.gatekeeper.adjustment > 0 ? '+' : ''}${game.gatekeeper.adjustment})`}
              </span>
            </div>
            {game.gatekeeper.reason && (
              <div className="text-[9px] text-white/40 leading-snug">{game.gatekeeper.reason}</div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
