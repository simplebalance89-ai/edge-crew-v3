import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { TwoLaneCard } from '@/components/TwoLaneCard'
import { getTopPicks } from '@/services/api'
import { Flame } from 'lucide-react'

export default function TopPicksPage() {
  const { data: picks, isLoading, error } = useQuery({
    queryKey: ['top-picks'],
    queryFn: getTopPicks,
    refetchInterval: 120000,
  })

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-center">
          <div className="w-12 h-12 border-4 border-[#00E5FF] border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p className="text-[#6E6E80]">Loading top picks...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="text-center py-20">
        <p className="text-red-400 mb-2">Failed to load top picks</p>
        <p className="text-[#6E6E80] text-sm">{(error as Error).message}</p>
      </div>
    )
  }

  return (
    <div>
      <div className="mb-6">
        <div className="flex items-center gap-3 mb-1">
          <Flame size={28} className="text-[#FF2D78]" />
          <h1 className="text-3xl font-black bg-gradient-to-r from-[#00E5FF] to-[#FF2D78] bg-clip-text text-transparent">
            TOP PICKS
          </h1>
        </div>
        <p className="text-[#6E6E80] text-sm">
          Best bets across all sports. B+ and above. Sorted by edge.
          {picks && <span className="ml-2 text-[#00E5FF]">{picks.length} picks live</span>}
        </p>
      </div>

      <div className="space-y-4">
        {(!picks || picks.length === 0) ? (
          <div className="bg-[#0E0E14] border border-[#1A1A28] rounded-xl p-8 text-center">
            <div className="text-sm font-bold text-white/70 mb-1">No top picks right now.</div>
            <div className="text-xs text-white/40">
              Slates may not be loaded yet, or no games graded B+ or above.
            </div>
          </div>
        ) : (
          picks.map((game: any, i: number) => (
            <div key={game.id} className="relative">
              <div className="absolute -left-2 -top-2 z-10 w-8 h-8 rounded-full bg-gradient-to-br from-[#D4A017] to-[#F59E0B] flex items-center justify-center text-black text-xs font-black shadow-lg">
                {i + 1}
              </div>

              <div className="absolute right-3 top-3 z-10 flex gap-2">
                {game.bet_label && (
                  <span className="text-[10px] font-black px-2 py-1 rounded bg-[#D4A017]/20 text-[#D4A017] border border-[#D4A017]/40 uppercase">
                    {game.bet_label}
                  </span>
                )}
                {game.total_label && (
                  <span className="text-[10px] font-black px-2 py-1 rounded bg-[#A78BFA]/20 text-[#A78BFA] border border-[#A78BFA]/40 uppercase">
                    {game.total_label}
                  </span>
                )}
                {game.btts_label && (
                  <span className="text-[10px] font-black px-2 py-1 rounded bg-[#10B981]/20 text-[#10B981] border border-[#10B981]/40 uppercase">
                    {game.btts_label}
                  </span>
                )}
              </div>

              <Link to={`/game/${game.id}`} className="block">
                <TwoLaneCard
                  game={game}
                  ourGrade={game.ourGrade || {grade: '-', score: 0, confidence: 0, thesis: ''}}
                  aiGrade={game.aiGrade || {grade: '-', score: 0, confidence: 0, model: 'AI'}}
                  convergence={game.convergence || {status: 'ALIGNED', consensusScore: 0, consensusGrade: '-', delta: 0, variance: 0}}
                />
              </Link>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
