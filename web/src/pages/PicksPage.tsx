import { useState } from 'react'
import { Trophy, Receipt, X, Copy, Check } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { generateBetSlip, getUserPicks, getBankroll } from '@/services/api'
import { useAppStore } from '@/store/useAppStore'
import type { BetSlip, LockedPick, Bankroll } from '@/types'

export default function PicksPage() {
  const { user } = useAppStore()
  const [betSlip, setBetSlip] = useState<BetSlip | null>(null)
  const [slipLoading, setSlipLoading] = useState(false)
  const [slipError, setSlipError] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)

  const username = user?.username || ''
  const { slipLocks, clearSlipLocks } = useAppStore()

  const { data: picks = [] } = useQuery<LockedPick[]>({
    queryKey: ['userPicks', username],
    queryFn: () => getUserPicks(username),
    enabled: !!username,
    refetchInterval: 10000,
  })

  const { data: bankroll } = useQuery<Bankroll>({
    queryKey: ['bankroll', username],
    queryFn: () => getBankroll(username),
    enabled: !!username,
    refetchInterval: 10000,
  })

  const wins = bankroll?.wins ?? 0
  const losses = bankroll?.losses ?? 0
  const pushes = bankroll?.pushes ?? 0
  const roi = bankroll && bankroll.wagered > 0
    ? ((bankroll.profit / bankroll.wagered) * 100).toFixed(1)
    : '0.0'

  const pendingPicks = picks.filter(p => p.result === 'pending')
  const settledPicks = picks.filter(p => p.result !== 'pending')

  const handleGenerateSlip = async () => {
    setSlipLoading(true)
    setSlipError(null)
    try {
      const slip = await generateBetSlip(username || 'Peter', slipLocks)
      if (slip.error) {
        setSlipError(slip.error)
      } else {
        setBetSlip(slip)
      }
    } catch (e) {
      setSlipError((e as Error).message || 'Failed to generate bet slip')
    }
    setSlipLoading(false)
  }

  const handleCopySlip = () => {
    if (!betSlip || !betSlip.picks) return
    const lines = [
      `BETONLINE.AG — BET SLIP`,
      `Slip ID: ${betSlip.slip_id}`,
      `Generated: ${betSlip.generated}`,
      `User: ${betSlip.user}`,
      `${'─'.repeat(40)}`,
      ...betSlip.picks.map((p) => p.line || `${p.pick} | ${p.amount} | ${p.book}`),
      `${'─'.repeat(40)}`,
      `Total Risk: ${betSlip.total_risk}`,
      `Potential Payout: ${betSlip.potential_payout}`,
      ``,
      betSlip.notes || '',
    ]
    navigator.clipboard.writeText(lines.join('\n'))
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  if (!user) {
    return (
      <div className="text-center py-20">
        <Trophy size={48} className="mx-auto mb-4 text-[#d4a017]" />
        <h2 className="text-xl font-bold mb-2">Log in to view picks</h2>
        <p className="text-white/60">Go to Profile to log in and start tracking.</p>
      </div>
    )
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-black">My Picks</h1>
        <div className="flex items-center gap-3">
          <span className="text-xs text-white/50">
            {slipLocks.length} pick{slipLocks.length === 1 ? '' : 's'} locked for slip
          </span>
          {slipLocks.length > 0 && (
            <button
              onClick={() => clearSlipLocks()}
              className="text-xs px-3 py-2 rounded-lg border border-white/15 text-white/60 hover:bg-white/5"
            >
              Clear
            </button>
          )}
        <button
          onClick={handleGenerateSlip}
          disabled={slipLoading || slipLocks.length === 0}
          className="flex items-center gap-2 px-5 py-2.5 bg-gradient-to-r from-[#D4A017] to-[#F5C842] text-black font-bold rounded-lg hover:opacity-90 disabled:opacity-50 transition-all"
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

      {/* Stats Row */}
      <div className="grid grid-cols-4 gap-4 mb-8">
        <div className="bg-[#1a1a1a] border border-white/10 rounded-xl p-4 text-center">
          <div className="text-3xl font-black text-green-400">{wins}</div>
          <div className="text-xs text-white/50 uppercase tracking-wider">Wins</div>
        </div>
        <div className="bg-[#1a1a1a] border border-white/10 rounded-xl p-4 text-center">
          <div className="text-3xl font-black text-red-400">{losses}</div>
          <div className="text-xs text-white/50 uppercase tracking-wider">Losses</div>
        </div>
        <div className="bg-[#1a1a1a] border border-white/10 rounded-xl p-4 text-center">
          <div className="text-3xl font-black text-white/60">{pushes}</div>
          <div className="text-xs text-white/50 uppercase tracking-wider">Pushes</div>
        </div>
        <div className="bg-[#1a1a1a] border border-white/10 rounded-xl p-4 text-center">
          <div className={`text-3xl font-black ${Number(roi) >= 0 ? 'text-[#d4a017]' : 'text-red-400'}`}>
            {Number(roi) > 0 ? '+' : ''}{roi}%
          </div>
          <div className="text-xs text-white/50 uppercase tracking-wider">ROI</div>
        </div>
      </div>

      {/* Pending Picks */}
      {pendingPicks.length > 0 ? (
        <div className="mb-8">
          <h2 className="text-lg font-bold mb-3 text-[#d4a017]">Active Picks ({pendingPicks.length})</h2>
          <div className="space-y-2">
            {pendingPicks.map(p => (
              <div key={p.id} className="bg-[#1a1a1a] border border-[#D4A017]/30 rounded-xl p-4 flex items-center justify-between">
                <div>
                  <div className="font-bold text-white">{p.team}</div>
                  <div className="text-xs text-white/50">
                    {p.sport.toUpperCase()} | {p.type}{p.line ? ` ${p.line > 0 ? '+' : ''}${p.line}` : ''} | ${p.amount}
                  </div>
                </div>
                <span className="px-3 py-1 rounded-full text-[10px] font-black tracking-wider bg-[#D4A017]/15 text-[#D4A017] border border-[#D4A017]/30">
                  PENDING
                </span>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {/* Settled Picks */}
      {settledPicks.length > 0 ? (
        <div className="mb-8">
          <h2 className="text-lg font-bold mb-3 text-white/70">Settled ({settledPicks.length})</h2>
          <div className="space-y-2">
            {settledPicks.map(p => (
              <div key={p.id} className="bg-[#1a1a1a] border border-white/10 rounded-xl p-4 flex items-center justify-between">
                <div>
                  <div className="font-bold text-white">{p.team}</div>
                  <div className="text-xs text-white/50">
                    {p.sport.toUpperCase()} | {p.type}{p.line ? ` ${p.line > 0 ? '+' : ''}${p.line}` : ''} | ${p.amount}
                  </div>
                </div>
                <div className="text-right">
                  <span className={`px-3 py-1 rounded-full text-[10px] font-black tracking-wider border ${
                    p.result === 'W' ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/40' :
                    p.result === 'L' ? 'bg-rose-500/15 text-rose-400 border-rose-500/40' :
                    'bg-white/10 text-white/50 border-white/20'
                  }`}>
                    {p.result}
                  </span>
                  <div className={`text-xs mt-1 font-bold ${p.profit >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                    {p.profit >= 0 ? '+' : ''}{p.profit.toFixed(2)}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {/* Empty state */}
      {picks.length === 0 && (
        <div className="bg-[#1a1a1a] border border-white/10 rounded-xl p-8 text-center">
          <Trophy size={48} className="mx-auto mb-4 text-[#d4a017]" />
          <h2 className="text-xl font-bold mb-2">No picks yet</h2>
          <p className="text-white/60">
            Grade some games and lock in your picks to track performance.
          </p>
        </div>
      )}

      {/* Bet Slip Modal */}
      {betSlip && betSlip.picks && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm" onClick={() => setBetSlip(null)}>
          <div className="bg-[#0E0E14] border border-[#D4A017]/40 rounded-2xl w-full max-w-lg mx-4 overflow-hidden shadow-2xl" onClick={e => e.stopPropagation()}>
            <div className="bg-gradient-to-r from-[#D4A017] to-[#F5C842] px-6 py-4 flex items-center justify-between">
              <div>
                <div className="text-black font-black text-lg tracking-wide">BETONLINE.AG</div>
                <div className="text-black/60 text-xs font-bold">Edge Crew Bet Slip</div>
              </div>
              <button onClick={() => setBetSlip(null)} className="text-black/60 hover:text-black">
                <X size={20} />
              </button>
            </div>

            <div className="px-6 py-3 border-b border-white/10 flex justify-between text-xs text-white/50">
              <span>ID: {betSlip.slip_id}</span>
              <span>{betSlip.generated}</span>
            </div>

            <div className="px-6 py-4 space-y-3 max-h-80 overflow-y-auto">
              {betSlip.picks.map((p, i) => (
                <div key={i} className="bg-white/[0.04] border border-white/10 rounded-xl p-3">
                  <div className="text-xs text-white/40 mb-1">{p.game}</div>
                  <div className="font-mono text-sm text-[#D4A017] font-bold">
                    {p.line || `${p.pick} | ${p.amount} | ${p.book}`}
                  </div>
                </div>
              ))}
            </div>

            <div className="px-6 py-4 border-t border-white/10 bg-white/[0.02]">
              <div className="flex justify-between mb-2">
                <span className="text-white/50 text-sm">Total Risk</span>
                <span className="text-white font-black text-lg">{betSlip.total_risk}</span>
              </div>
              <div className="flex justify-between mb-3">
                <span className="text-white/50 text-sm">Potential Payout</span>
                <span className="text-emerald-400 font-black text-lg">{betSlip.potential_payout}</span>
              </div>
              {betSlip.notes && (
                <div className="text-[10px] text-white/30 leading-snug mb-3">{betSlip.notes}</div>
              )}
              <button
                onClick={handleCopySlip}
                className="w-full flex items-center justify-center gap-2 py-2.5 bg-[#D4A017]/20 border border-[#D4A017]/40 text-[#D4A017] font-bold rounded-lg hover:bg-[#D4A017]/30 transition-all"
              >
                {copied ? <><Check size={16} /> Copied!</> : <><Copy size={16} /> Copy to Clipboard</>}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
