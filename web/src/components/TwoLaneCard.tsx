import { useState, type MouseEvent } from 'react'
import { Lock, Check } from 'lucide-react'
import { useAppStore } from '@/store/useAppStore'
import { lockPick, submitGutPick, analyzeGame } from '@/services/api'
import type { Game, Grade, ConvergenceResult, ChainInfo } from '@/types'

interface TwoLaneCardProps {
  game: Game
  ourGrade?: Grade
  aiGrade?: Grade & { model?: string }
  convergence?: ConvergenceResult['convergence']
}

const SPORT_HEADLINES: Record<string, string[]> = {
  MLB: ['bullpen', 'lineup_dna', 'starting_pitcher'],
  NBA: ['three_pt_rate', 'b2b_fatigue', 'star_player'],
  NHL: ['goalie', 'pp_pct', 'pk_pct'],
  NFL: ['weather', 'star_player', 'turnover_diff'],
  SOCCER: ['goalkeeper', 'congestion', 'xg_diff'],
  NCAAB: ['conference_strength', 'pace', 'home_away'],
  NCAAF: ['recruiting', 'home_away', 'coaching_change'],
  MMA: ['reach_advantage', 'finish_rate', 'form'],
  BOXING: ['reach_advantage', 'stance_matchup', 'finish_rate'],
}

const VARIABLE_DISPLAY_NAMES: Record<string, string> = {
  bullpen: 'Bullpen',
  lineup_dna: 'Lineup DNA',
  starting_pitcher: 'Starting Pitcher',
  three_pt_rate: '3PT Rate',
  b2b_fatigue: 'B2B Fatigue',
  star_player: 'Star Player',
  goalie: 'Goalie',
  pp_pct: 'Power Play %',
  pk_pct: 'Penalty Kill %',
  weather: 'Weather',
  turnover_diff: 'Turnover Diff',
  goalkeeper: 'Goalkeeper',
  congestion: 'Congestion',
  xg_diff: 'xG Diff',
  conference_strength: 'Conf Strength',
  pace: 'Pace',
  home_away: 'Home/Away',
  recruiting: 'Recruiting',
  coaching_change: 'Coaching Change',
  reach_advantage: 'Reach Adv',
  finish_rate: 'Finish Rate',
  form: 'Form',
  stance_matchup: 'Stance Matchup',
}

const gradeColor = (g: string) => {
  if (g?.startsWith('A')) return '#10B981'
  if (g?.startsWith('B')) return '#38BDF8'
  if (g?.startsWith('C') || g?.startsWith('D')) return '#F59E0B'
  return '#ef4444'
}

function ChainTags({ chains, formatName }: { chains: ChainInfo[]; formatName: (s: string) => string }) {
  const [expanded, setExpanded] = useState(false)
  const positive = chains.filter(c => c.category === 'positive')
  const negative = chains.filter(c => c.category === 'negative')
  const all = [...positive, ...negative]
  const visible = expanded ? all : all.slice(0, 4)
  const overflow = all.length - 4

  return (
    <div className="mb-2 flex flex-wrap gap-1">
      {visible.map((c, i) => {
        const isPos = c.category === 'positive'
        return (
          <span key={i} className={`text-[8px] px-1.5 py-0.5 rounded border ${
            isPos
              ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
              : 'bg-rose-500/10 border-rose-500/30 text-rose-400'
          }`}>
            {formatName(c.name)}{c.bonus ? ` ${c.bonus > 0 ? '+' : ''}${c.bonus.toFixed(1)}` : ''}
          </span>
        )
      })}
      {!expanded && overflow > 0 && (
        <button
          onClick={(e) => { e.preventDefault(); e.stopPropagation(); setExpanded(true) }}
          className="text-[8px] px-1.5 py-0.5 rounded border bg-white/5 border-white/15 text-white/40 hover:text-white/60"
        >
          +{overflow} more
        </button>
      )}
    </div>
  )
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
    CONFLICT: 'bg-rose-500/25 text-rose-300 border-rose-500/60',
    PENDING: 'bg-white/5 text-white/40 border-white/15',
  }

  return (
    <div className="bg-[#0E0E14] border rounded-xl p-4 transition-all border-[#1A1A28] hover:border-[#1A1A28]/80">
      {/* ─── HEADER ─── */}
      <div className="flex justify-between items-start mb-3">
        <div>
          <h3 className="text-base font-bold text-[#E8E8EC]">
            {game.awayTeam} <span className="text-[#6E6E80] font-normal">@</span> {game.homeTeam}
            {(() => {
              const parseH2H = (s?: string) => {
                if (!s || s === '0-0') return null
                const m = s.match(/^(\d+)-(\d+)$/)
                if (!m) return null
                return { w: parseInt(m[1]), l: parseInt(m[2]) }
              }
              const h = parseH2H(game.home_profile?.h2h_season)
              const a = parseH2H(game.away_profile?.h2h_season)
              let leader: { team: string; rec: string } | null = null
              if (h && (!a || h.w >= a.w)) {
                const abbr = game.homeTeam?.split(' ').pop()?.toUpperCase() || ''
                leader = { team: abbr, rec: game.home_profile!.h2h_season! }
              } else if (a) {
                const abbr = game.awayTeam?.split(' ').pop()?.toUpperCase() || ''
                leader = { team: abbr, rec: game.away_profile!.h2h_season! }
              }
              if (!leader) return null
              return (
                <span className="ml-2 text-[10px] font-bold text-[#D4A017]/80">
                  · Season series: {leader.team} {leader.rec}
                </span>
              )
            })()}
          </h3>
          <div className="flex items-center gap-3 mt-1">
            <span className="text-xs text-[#6E6E80]">
              {game.scheduledAt ? new Date(game.scheduledAt).toLocaleDateString([], { month: 'short', day: 'numeric' }) + ' ' + new Date(game.scheduledAt).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' }) : ''}
            </span>
            {game.odds && (() => {
              const fmt = (n: number) => (n > 0 ? `+${n}` : `${n}`)
              return (
              <>
                {game.odds.spread !== 0 && (() => {
                  const homeLine = -game.odds.spread
                  const awayLine = game.odds.spread
                  const ph = game.odds.spreadPriceHome
                  const pa = game.odds.spreadPriceAway
                  return (
                    <span className="text-xs text-[#6E6E80]">
                      Spread: {game.homeTeam} {fmt(homeLine)}{ph != null ? ` (${fmt(ph)})` : ''} / {game.awayTeam} {fmt(awayLine)}{pa != null ? ` (${fmt(pa)})` : ''}
                    </span>
                  )
                })()}
                {game.odds.total > 0 && (
                  <span className="text-xs text-[#6E6E80]">
                    O/U: {game.odds.total}
                    {game.odds.overPrice != null && game.odds.underPrice != null && (
                      <> ({fmt(game.odds.overPrice)}/{fmt(game.odds.underPrice)})</>
                    )}
                  </span>
                )}
                {game.odds.mlHome !== 0 && (
                  <span className="text-xs text-[#6E6E80]">
                    ML: {game.awayTeam} {fmt(game.odds.mlAway)} / {game.homeTeam} {fmt(game.odds.mlHome)}
                    {game.odds.draw != null && <> / Draw {fmt(game.odds.draw)}</>}
                  </span>
                )}
                {game.odds.bttsYes != null && (
                  <span className="text-xs text-[#38BDF8] font-medium">
                    BTTS: Yes {fmt(game.odds.bttsYes)} / No {game.odds.bttsNo != null ? fmt(game.odds.bttsNo) : '—'}
                  </span>
                )}
              </>
              )
            })()}
          </div>
          {/* MLB starting pitchers */}
          {game.sport === 'MLB' && (game.away_profile?.starting_pitcher?.name || game.home_profile?.starting_pitcher?.name) && (
            <div className="mt-1 text-[11px] font-bold text-[#38BDF8]">
              ⚾ {game.away_profile?.starting_pitcher?.name || 'TBD'} <span className="text-white/40 font-normal">vs</span> {game.home_profile?.starting_pitcher?.name || 'TBD'}
            </div>
          )}
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

      {/* ═══ SPORT HEADLINE STATS ═══ */}
      {(() => {
        const sport = (game.sport || '').toUpperCase()
        const headlineKeys = SPORT_HEADLINES[sport]
        if (!headlineKeys || !displayOur.variables) return null
        const vars = displayOur.variables as Record<string, { score: number; name: string; available: boolean }>
        const pills = headlineKeys.filter((k) => vars[k]?.available)
        if (pills.length === 0) return null
        return (
          <div className="flex flex-wrap gap-1.5 mb-3">
            {pills.map((key) => {
              const v = vars[key]
              const color = v.score >= 7 ? '#10B981' : v.score >= 5 ? '#d4a024' : '#ef4444'
              const bgColor = v.score >= 7 ? 'rgba(16,185,129,0.12)' : v.score >= 5 ? 'rgba(212,160,36,0.12)' : 'rgba(239,68,68,0.12)'
              const borderColor = v.score >= 7 ? 'rgba(16,185,129,0.35)' : v.score >= 5 ? 'rgba(212,160,36,0.35)' : 'rgba(239,68,68,0.35)'
              return (
                <span
                  key={key}
                  className="px-2 py-0.5 rounded-full text-[10px] font-bold border"
                  style={{ color, backgroundColor: bgColor, borderColor }}
                >
                  {VARIABLE_DISPLAY_NAMES[key] || v.name}: {v.score}
                </span>
              )
            })}
          </div>
        )
      })()}

      {/* ═══ GOLF OUTRIGHTS ═══ */}
      {game.sport === 'GOLF' && game.outrights && game.outrights.length > 0 && (
        <div className="mb-3">
          <div className="text-[10px] font-black tracking-[1.5px] text-[#10B981] mb-2 pb-1.5 border-b border-white/[0.06]">
            TOURNAMENT OUTRIGHTS — {game.outrights.length} GOLFERS
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-1.5 max-h-[300px] overflow-y-auto">
            {game.outrights.map((g: any, i: number) => (
              <div
                key={g.name}
                className={`flex justify-between items-center px-2.5 py-1.5 rounded-lg text-[11px] ${
                  i === 0 ? 'bg-[#D4A017]/15 border border-[#D4A017]/40 text-[#D4A017] font-bold'
                    : i < 5 ? 'bg-[#10B981]/10 border border-[#10B981]/20 text-[#10B981]'
                    : i < 15 ? 'bg-white/5 border border-white/10 text-white/70'
                    : 'bg-white/[0.02] border border-white/5 text-white/40'
                }`}
              >
                <span className="truncate mr-2">{i === 0 ? '👑 ' : ''}{g.name}</span>
                <span className="font-mono font-bold whitespace-nowrap">{g.odds > 0 ? '+' : ''}{g.odds}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ═══ TWO-LANE FORK ═══ */}
      {game.sport !== 'GOLF' && <div className="grid grid-cols-2 gap-3 mb-3">

        {/* ── LEFT LANE: OUR PROCESS ── */}
        <div className="bg-[#F72585]/[0.04] border border-[#F72585]/20 rounded-xl p-3">
          <div className="text-[10px] font-black tracking-[1.5px] text-[#F72585] mb-2 pb-1.5 border-b border-white/[0.06]">OUR PROCESS</div>

          {/* Main Matrix — top variable scores */}
          {displayOur.variables && Object.keys(displayOur.variables).length > 0 && (() => {
            const sportSpecificVars: Record<string, string> = {
              bullpen: 'MLB', starting_pitching: 'MLB', park_factor: 'MLB',
              pace: 'NBA', three_point: 'NBA', free_throw: 'NBA',
              power_play: 'NHL', goaltending: 'NHL', save_pct: 'NHL',
              red_zone: 'NFL', turnover: 'NFL', rushing: 'NFL',
              tempo: 'NCAAB', bench_scoring: 'NCAAB',
              passing_offense: 'NCAAF', recruiting: 'NCAAF',
            }
            const sportUp = game.sport?.toUpperCase() || ''
            return (
            <div className="mb-2">
              <div className="text-[9px] text-white/35 font-bold tracking-wide mb-1">MAIN MATRIX</div>
              {Object.entries(displayOur.variables as Record<string, {score: number; name: string; weight: number; note: string; available: boolean}>)
                .filter(([, v]) => v.available)
                .sort(([, a], [, b]) => (b.score * (b.weight || 1)) - (a.score * (a.weight || 1)))
                .slice(0, 10)
                .map(([key, v]) => {
                  const weighted = v.score * (v.weight || 1)
                  const barColor = v.score >= 8 ? '#00D4AA' : v.score >= 6 ? '#FFB800' : v.score >= 4 ? '#666' : '#F72585'
                  const varSport = sportSpecificVars[key.toLowerCase()]
                  const sportLabel = varSport && varSport !== sportUp ? ` (${varSport})` : ''
                  return (
                  <div key={key} className="flex justify-between items-center text-[10px] py-[1px]">
                    <span className="text-white/50">{v.name}{sportLabel && <span className="text-white/25 text-[8px]">{sportLabel}</span>}</span>
                    <div className="flex items-center gap-1.5">
                      <div className="w-12 h-1 bg-white/10 rounded-full overflow-hidden">
                        <div className="h-full rounded-full" style={{ width: `${Math.min(weighted * 10, 100)}%`, backgroundColor: barColor }} />
                      </div>
                      <span className="font-bold w-4 text-right" style={{ color: barColor }}>
                        {v.score}
                      </span>
                    </div>
                  </div>
                  )
                })}
            </div>
            )
          })()}

          {/* Chains fired */}
          {(() => {
            const chains: ChainInfo[] = displayOur.chains || []
            const fromKeyFactors = !chains.length && displayOur.keyFactors?.length
            const formatChainName = (s: string) => s.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()).replace(/\B\w+/g, w => w.toLowerCase())
            if (fromKeyFactors) {
              const positive = displayOur.keyFactors!.filter(k => !/penalty|collapse|cold|weak|fade/i.test(k))
              const negative = displayOur.keyFactors!.filter(k => /penalty|collapse|cold|weak|fade/i.test(k))
              const all = [
                ...positive.map(k => ({ name: k, bonus: 0, category: 'positive' as const })),
                ...negative.map(k => ({ name: k, bonus: 0, category: 'negative' as const })),
              ]
              return all.length > 0 ? <ChainTags chains={all} formatName={formatChainName} /> : null
            }
            return chains.length > 0 ? <ChainTags chains={chains} formatName={formatChainName} /> : null
          })()}

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
                {game.aiModels.map((m, i) => {
                  const src = (m as any).source;
                  const srcLabel = src === 'real' ? 'LIVE' : src === 'fail' ? 'FAIL' : '?';
                  const srcColor = src === 'real'
                    ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
                    : src === 'fail'
                    ? 'bg-rose-500/20 text-rose-300 border-rose-500/40'
                    : 'bg-white/10 text-white/40 border-white/20';
                  return (
                    <div key={i} className="relative bg-white/[0.03] border border-white/[0.08] rounded-lg p-1.5 text-center">
                      <span className={`absolute top-0.5 right-0.5 text-[6px] font-black px-1 rounded border ${srcColor}`}>{srcLabel}</span>
                      <div className="text-[7px] font-black text-[#00D4AA] uppercase truncate pr-5">{m.model}</div>
                      <div className="text-[18px] font-black leading-tight" style={{ color: gradeColor(m.grade) }}>
                        {m.grade}
                      </div>
                      <div className="text-[9px] text-white/40">{m.score}</div>
                      {(m as any).pick && <div className="text-[7px] font-bold text-[#00D4AA] mt-0.5 truncate">{(m as any).pick}</div>}
                      {src === 'fail' && m.thesis && (
                        <div className="text-[8px] text-white/40 italic mt-0.5 truncate" title={m.thesis}>{m.thesis}</div>
                      )}
                    </div>
                  );
                })}
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
      </div>}

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

        {/* CONFLICT vote breakdown */}
        {displayStatus === 'CONFLICT' && convergence?.conflict && (
          <div className="mt-2 mx-auto max-w-xs bg-rose-500/10 border border-rose-500/40 rounded-lg px-3 py-2 text-left font-mono text-[10px]">
            <div className="text-rose-300">
              <span className="text-rose-400/70">ENGINE:</span> {convergence.conflict.engineSide}
            </div>
            <div className="text-rose-300">
              <span className="text-rose-400/70">AI:&nbsp;&nbsp;&nbsp;&nbsp;</span> {convergence.conflict.aiSide}
              <span className="text-white/40"> ({convergence.conflict.homeVotes} vs {convergence.conflict.awayVotes})</span>
            </div>
          </div>
        )}

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
        {/* Single-game Analyze button — runs the full AI fan-out for ONLY this game */}
        {(!game.aiModels || game.aiModels.length === 0) && (
          <div className="mt-2 flex justify-center">
            <button
              onClick={async (e) => {
                e.stopPropagation();
                const btn = e.currentTarget as HTMLButtonElement;
                if (btn.disabled) return;
                const orig = btn.textContent;
                btn.textContent = 'Analyzing...';
                btn.disabled = true;
                try {
                  await analyzeGame((game.sport || '').toLowerCase(), game.id);
                  window.location.reload();
                } catch (err) {
                  btn.textContent = 'Failed';
                  setTimeout(() => { btn.textContent = orig; btn.disabled = false; }, 2000);
                }
              }}
              className="px-3 py-1 rounded-lg text-[10px] font-bold bg-[#00D4AA]/15 border border-[#00D4AA]/40 text-[#00D4AA] hover:bg-[#00D4AA]/25"
            >
              Analyze This Game
            </button>
          </div>
        )}
        {pick && pick.side && (
          <div className="mt-3 flex items-center justify-center gap-2 flex-wrap">
            <div className="inline-block bg-[#D4A017]/15 border border-[#D4A017]/30 text-[#D4A017] text-sm font-extrabold py-2 px-4 rounded-lg">
              {pick.side}
              {pick.type === 'spread' && pick.line !== 0 ? ` ${pick.line > 0 ? '+' : ''}${pick.line}` : ` ${pick.type.toUpperCase()}`}
              {pick.sizing && pick.sizing !== 'No Play' ? ` (${pick.sizing})` : ''}
            </div>
            {(pick.killed === true || pick.sizing === 'PASS') ? (
              <div className="inline-block bg-red-600/20 border-2 border-red-500/70 text-red-300 text-[11px] font-black tracking-wider py-2 px-3 rounded-lg uppercase">
                KILLED — DO NOT BET (CONFLICT/KILL flag active)
              </div>
            ) : user && (
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
            game.gatekeeper.action === '?' ? 'bg-rose-500/15 border-rose-500/50' :
            game.gatekeeper.action === 'BOOST' ? 'bg-emerald-500/10 border-emerald-500/30' :
            game.gatekeeper.action === 'CHALLENGE' ? 'bg-rose-500/10 border-rose-500/30' :
            'bg-[#D4A017]/10 border-[#D4A017]/30'
          }`}>
            <div className="flex items-center justify-center gap-2 mb-1">
              <span className={`text-[10px] font-black tracking-wider ${
                game.gatekeeper.action === '?' ? 'text-rose-300' :
                game.gatekeeper.action === 'BOOST' ? 'text-emerald-400' :
                game.gatekeeper.action === 'CHALLENGE' ? 'text-rose-400' :
                'text-[#D4A017]'
              }`}>
                KIMI GATEKEEPER
              </span>
              <span className={`text-xs font-black ${
                game.gatekeeper.action === '?' ? 'text-rose-300' :
                game.gatekeeper.action === 'BOOST' ? 'text-emerald-400' :
                game.gatekeeper.action === 'CHALLENGE' ? 'text-rose-400' :
                'text-[#D4A017]'
              }`}>
                {game.gatekeeper.action === '?' ? '⚠ ERROR' :
                 (game.gatekeeper.action === 'BOOST' ? '▲' : game.gatekeeper.action === 'CHALLENGE' ? '▼' : '✓') + ' ' + game.gatekeeper.action}
                {game.gatekeeper.action !== '?' && game.gatekeeper.adjustment !== 0 && ` (${game.gatekeeper.adjustment > 0 ? '+' : ''}${game.gatekeeper.adjustment})`}
              </span>
            </div>
            {game.gatekeeper.reason && (
              <div className={`text-[9px] leading-snug ${game.gatekeeper.action === '?' ? 'text-rose-300/80 italic' : 'text-white/40'}`}>{game.gatekeeper.reason}</div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
