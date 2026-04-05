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

const scoreColor = (s: number) => s >= 7 ? '#10B981' : s >= 5 ? '#d4a024' : '#ef4444'

export function TwoLaneCard({ game, ourGrade, aiGrade, convergence }: TwoLaneCardProps) {
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
    <div className="bg-[#0E0E14] border border-[#1A1A28] rounded-xl p-4 hover:border-[#1A1A28]/80 transition-all">
      {/* ─── HEADER ─── */}
      <div className="flex justify-between items-start mb-3">
        <div>
          <h3 className="text-base font-bold text-[#E8E8EC]">{game.awayTeam} <span className="text-[#6E6E80] font-normal">@</span> {game.homeTeam}</h3>
          <div className="flex items-center gap-3 mt-1">
            <span className="text-xs text-[#6E6E80]">
              {game.scheduledAt ? new Date(game.scheduledAt).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' }) : ''}
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
        <span className={`px-3 py-1 rounded-full text-[10px] font-black tracking-wider border ${statusStyles[displayStatus] || statusStyles.PENDING}`}>
          {displayStatus}
        </span>
      </div>

      {/* ═══ TWO-LANE FORK ═══ */}
      <div className="grid grid-cols-2 gap-3 mb-3">

        {/* ── LEFT LANE: OUR PROCESS ── */}
        <div className="bg-[#F72585]/[0.04] border border-[#F72585]/20 rounded-xl p-3">
          <div className="text-[10px] font-black tracking-[1.5px] text-[#F72585] mb-2 pb-1.5 border-b border-white/[0.06]">OUR PROCESS</div>

          {/* Main Matrix — variable scores */}
          {displayOur.keyFactors && displayOur.keyFactors.length > 0 ? (
            <div className="mb-2">
              <div className="text-[9px] text-white/35 font-bold tracking-wide mb-1">CHAINS FIRED</div>
              <div className="flex flex-wrap gap-1">
                {displayOur.keyFactors.map((chain: string, i: number) => (
                  <span key={i} className="text-[8px] px-1.5 py-0.5 bg-[#F72585]/10 border border-[#F72585]/30 text-[#F72585] rounded">
                    {chain}
                  </span>
                ))}
              </div>
            </div>
          ) : null}

          {/* Engine Grade Card */}
          <div className="text-center py-2 bg-white/[0.03] border border-white/[0.08] rounded-lg">
            <div className="text-[9px] font-black text-[#F72585] tracking-wide">ENGINE GRADE</div>
            <div className="text-[28px] font-black leading-tight" style={{ color: gradeColor(displayOur.grade) }}>
              {displayOur.grade}
            </div>
            <div className="text-[10px] text-white/40">{displayOur.score.toFixed(1)}</div>
            <div className="text-[10px] text-white/30">{displayOur.confidence}% conf</div>
          </div>

          {/* Thesis */}
          {displayOur.thesis && (
            <div className="mt-2 text-[9px] text-white/40 leading-relaxed">{displayOur.thesis}</div>
          )}
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
                  <div key={i} className="bg-white/[0.03] border border-white/[0.08] rounded-lg p-2 text-center">
                    <div className="text-[7px] font-black text-[#00D4AA] uppercase truncate">{m.model}</div>
                    <div className="text-[18px] font-black leading-tight" style={{ color: gradeColor(m.grade) }}>
                      {m.grade}
                    </div>
                    <div className="text-[9px] text-white/40">{m.score}</div>
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

        {/* Pick */}
        {pick && pick.side && (
          <div className="mt-3 inline-block bg-[#D4A017]/15 border border-[#D4A017]/30 text-[#D4A017] text-sm font-extrabold py-2 px-4 rounded-lg">
            {pick.side}
            {pick.type === 'spread' && pick.line !== 0 ? ` ${pick.line > 0 ? '+' : ''}${pick.line}` : ` ${pick.type.toUpperCase()}`}
            {pick.sizing && pick.sizing !== 'No Play' ? ` (${pick.sizing})` : ''}
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
