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
      DIVERGENT: 'bg-amber-500/10 text-amber-400 border-amber-500/30',
      CONFLICT: 'bg-rose-500/10 text-rose-400 border-rose-500/30',
    }
    return styles[status] || styles.DIVERGENT
  }

  const displayStatus = convergence?.status || 'PENDING'
  const displayOur = ourGrade || { score: 0, grade: '-', confidence: 0 }
  const displayAI = aiGrade || { score: 0, grade: '-', confidence: 0, model: 'AI' }
  const consensusScore = convergence?.consensusScore || 0
  const consensusGrade = convergence?.consensusGrade || '-'
  const delta = convergence?.delta || 0

  return (
    <div className="bg-[#0E0E14] border border-[#1A1A28] rounded-xl p-5 hover:border-[#1A1A28]/80 transition-all">
      {/* Header */}
      <div className="flex justify-between items-start mb-4">
        <div>
          <h3 className="text-lg font-bold text-[#E8E8EC]">{game.homeTeam} vs {game.awayTeam}</h3>
          <p className="text-sm text-[#6E6E80]">{new Date(game.scheduledAt).toLocaleTimeString()}</p>
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
        </div>

        {/* AI Process - Cyan */}
        <div className="bg-[#00E5FF]/5 border border-[#00E5FF]/20 rounded-lg p-4">
          <div className="text-xs font-bold text-[#00E5FF] uppercase tracking-wider mb-2">AI Process</div>
          <div className="text-3xl font-black text-white">{displayAI.score.toFixed(1)}</div>
          <div className="text-sm font-semibold text-[#00E5FF]">{displayAI.grade}</div>
          <div className="text-xs text-[#6E6E80] mt-1">{displayAI.model}</div>
        </div>
      </div>

      {/* Convergence */}
      <div className="bg-gradient-to-r from-[#00E5FF]/5 to-[#FF2D78]/5 border border-[#1A1A28] rounded-lg p-3 text-center">
        <div className="text-xs font-bold text-[#6E6E80] uppercase tracking-wider mb-1">Convergence</div>
        <div className="text-2xl font-black bg-gradient-to-r from-[#00E5FF] to-[#FF2D78] bg-clip-text text-transparent">
          {consensusScore.toFixed(1)} {consensusGrade}
        </div>
        <div className="text-xs text-[#6E6E80]">Δ {delta.toFixed(2)} variance</div>
      </div>
    </div>
  )
}
