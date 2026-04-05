import type { Game, Grade, ConvergenceResult } from '@/types'

interface TwoLaneCardProps {
  game: Game
  ourGrade?: Grade
  aiGrade?: Grade & { model?: string }
  convergence?: ConvergenceResult['convergence']
}

export function TwoLaneCard({ game, ourGrade, aiGrade, convergence }: TwoLaneCardProps) {
  const getStatusBadge = (status: string) => {
    const styles: Record<string, string> = {
      LOCK: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
      ALIGNED: 'bg-[#00E5FF]/10 text-[#00E5FF] border-[#00E5FF]/30',
      CLOSE: 'bg-amber-500/10 text-amber-400 border-amber-500/30',
      SPLIT: 'bg-rose-500/10 text-rose-400 border-rose-500/30',
    }
    return styles[status] || styles.CLOSE
  }

  const getSizingColor = (sizing: string) => {
    if (sizing === 'Strong Play') return 'text-emerald-400'
    if (sizing === 'Standard') return 'text-[#00E5FF]'
    if (sizing === 'Lean') return 'text-amber-400'
    return 'text-[#6E6E80]'
  }

  const displayStatus = convergence?.status || 'PENDING'
  const displayOur = ourGrade || { score: 0, grade: '-', confidence: 0, thesis: '' }
  const displayAI = aiGrade || { score: 0, grade: '-', confidence: 0, model: 'AI' }
  const consensusScore = convergence?.consensusScore || 0
  const consensusGrade = convergence?.consensusGrade || '-'
  const delta = convergence?.delta || 0
  const pick = game.pick

  return (
    <div className="bg-[#0E0E14] border border-[#1A1A28] rounded-xl p-5 hover:border-[#1A1A28]/80 transition-all">
      {/* Header */}
      <div className="flex justify-between items-start mb-4">
        <div>
          <h3 className="text-lg font-bold text-[#E8E8EC]">{game.homeTeam} vs {game.awayTeam}</h3>
          <div className="flex items-center gap-3 mt-1">
            <p className="text-sm text-[#6E6E80]">
              {game.scheduledAt ? new Date(game.scheduledAt).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' }) : ''}
            </p>
            {game.odds && (
              <p className="text-xs text-[#6E6E80]">
                {game.odds.spread !== 0 && <span>Spread: {game.odds.spread > 0 ? '+' : ''}{game.odds.spread}</span>}
                {game.odds.total > 0 && <span className="ml-2">O/U: {game.odds.total}</span>}
              </p>
            )}
          </div>
        </div>
        <span className={`px-3 py-1 rounded-full text-xs font-bold border ${getStatusBadge(displayStatus)}`}>
          {displayStatus}
        </span>
      </div>

      {/* Two Lanes */}
      <div className="grid grid-cols-2 gap-3 mb-4">
        {/* Our Process - Magenta */}
        <div className="bg-[#FF2D78]/5 border border-[#FF2D78]/20 rounded-lg p-4">
          <div className="text-xs font-bold text-[#FF2D78] uppercase tracking-wider mb-2">Our Process</div>
          <div className="text-3xl font-black text-white">{displayOur.score.toFixed(1)}</div>
          <div className="text-sm font-semibold text-[#FF2D78]">{displayOur.grade}</div>
          <div className="text-xs text-[#6E6E80] mt-1">{displayOur.confidence}% conf</div>
          {displayOur.thesis && (
            <div className="text-xs text-[#9E9EA8] mt-2 leading-relaxed">{displayOur.thesis}</div>
          )}
          {displayOur.keyFactors && displayOur.keyFactors.length > 0 && (
            <div className="flex flex-wrap gap-1 mt-2">
              {displayOur.keyFactors.map((chain: string, i: number) => (
                <span key={i} className="text-[10px] px-1.5 py-0.5 bg-[#FF2D78]/10 text-[#FF2D78] rounded font-mono">
                  {chain}
                </span>
              ))}
            </div>
          )}
        </div>

        {/* AI Process - Cyan */}
        <div className="bg-[#00E5FF]/5 border border-[#00E5FF]/20 rounded-lg p-4">
          <div className="text-xs font-bold text-[#00E5FF] uppercase tracking-wider mb-2">AI Process</div>
          <div className="text-3xl font-black text-white">{displayAI.score.toFixed(1)}</div>
          <div className="text-sm font-semibold text-[#00E5FF]">{displayAI.grade}</div>
          <div className="text-xs text-[#6E6E80] mt-1">{(displayAI as any).model || 'Odds-Model'}</div>

          {/* Per-model breakdown (deep analysis) */}
          {game.aiModels && game.aiModels.length > 0 && (
            <div className="mt-3 space-y-2 border-t border-[#00E5FF]/10 pt-2">
              {game.aiModels.map((m, i) => (
                <div key={i} className="text-[11px]">
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-[#00E5FF]/80">{m.model}</span>
                    <span className="font-mono text-white">{m.grade} <span className="text-[#6E6E80]">{m.score}</span></span>
                  </div>
                  {m.thesis && (
                    <div className="text-[#9E9EA8] leading-snug mt-0.5">{m.thesis}</div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Convergence */}
      <div className="bg-gradient-to-r from-[#00E5FF]/5 to-[#FF2D78]/5 border border-[#1A1A28] rounded-lg p-3">
        <div className="flex justify-between items-center">
          <div>
            <div className="text-xs font-bold text-[#6E6E80] uppercase tracking-wider mb-1">Convergence</div>
            <div className="text-2xl font-black bg-gradient-to-r from-[#00E5FF] to-[#FF2D78] bg-clip-text text-transparent">
              {consensusScore.toFixed(1)} {consensusGrade}
            </div>
            <div className="text-xs text-[#6E6E80]">{'\u0394'} {delta.toFixed(2)} variance</div>

            {/* Gatekeeper Verdict */}
            {game.gatekeeper && (
              <div className={`mt-2 text-[11px] font-semibold ${
                game.gatekeeper.action === 'BOOST' ? 'text-emerald-400' :
                game.gatekeeper.action === 'CHALLENGE' ? 'text-rose-400' :
                'text-[#6E6E80]'
              }`}>
                Kimi: {game.gatekeeper.action}
                {game.gatekeeper.adjustment !== 0 && ` (${game.gatekeeper.adjustment > 0 ? '+' : ''}${game.gatekeeper.adjustment})`}
                {game.gatekeeper.reason && (
                  <span className="font-normal text-[#9E9EA8] ml-1">-- {game.gatekeeper.reason}</span>
                )}
              </div>
            )}
          </div>

          {/* Pick Badge */}
          {pick && pick.side && (
            <div className="text-right">
              <div className={`text-sm font-bold ${getSizingColor(pick.sizing)}`}>
                {pick.sizing}
              </div>
              <div className="text-xs text-[#E8E8EC] font-semibold">
                {pick.side} {pick.type === 'spread' && pick.line !== 0 ? (pick.line > 0 ? `+${pick.line}` : pick.line) : pick.type.toUpperCase()}
              </div>
              <div className="text-xs text-[#6E6E80]">{pick.confidence}% conf</div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
