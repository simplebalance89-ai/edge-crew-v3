import { useState } from 'react'
import { Trophy, Receipt, X, Copy, Check } from 'lucide-react'
import { generateBetSlip } from '@/services/api'
import type { BetSlip } from '@/types'

export default function PicksPage() {
  const [betSlip, setBetSlip] = useState<BetSlip | null>(null)
  const [slipLoading, setSlipLoading] = useState(false)
  const [slipError, setSlipError] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)

  const handleGenerateSlip = async () => {
    setSlipLoading(true)
    setSlipError(null)
    try {
      const slip = await generateBetSlip('Peter')
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
      `HARD ROCK SPORTSBOOK — BET SLIP`,
      `Slip ID: ${betSlip.slip_id}`,
      `Generated: ${betSlip.generated}`,
      `User: ${betSlip.user}`,
      `${'─'.repeat(40)}`,
      ...betSlip.picks.map((p, i) =>
        `${i + 1}. ${p.game}\n   ${p.pick} (${p.type}) — ${p.amount} @ ${p.book}`
      ),
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

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-black">My Picks</h1>
        <button
          onClick={handleGenerateSlip}
          disabled={slipLoading}
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

      {slipError && (
        <div className="mb-4 p-3 bg-rose-500/10 border border-rose-500/30 rounded-lg text-sm text-rose-400">
          {slipError}
        </div>
      )}

      <div className="grid grid-cols-3 gap-4 mb-8">
        <div className="bg-[#1a1a1a] border border-white/10 rounded-xl p-4 text-center">
          <div className="text-3xl font-black text-green-400">24</div>
          <div className="text-xs text-white/50 uppercase tracking-wider">Wins</div>
        </div>
        <div className="bg-[#1a1a1a] border border-white/10 rounded-xl p-4 text-center">
          <div className="text-3xl font-black text-red-400">12</div>
          <div className="text-xs text-white/50 uppercase tracking-wider">Losses</div>
        </div>
        <div className="bg-[#1a1a1a] border border-white/10 rounded-xl p-4 text-center">
          <div className="text-3xl font-black text-[#d4a017]">+18%</div>
          <div className="text-xs text-white/50 uppercase tracking-wider">ROI</div>
        </div>
      </div>

      <div className="bg-[#1a1a1a] border border-white/10 rounded-xl p-8 text-center">
        <Trophy size={48} className="mx-auto mb-4 text-[#d4a017]" />
        <h2 className="text-xl font-bold mb-2">No picks yet</h2>
        <p className="text-white/60">
          Grade some games and lock in your picks to track performance.
        </p>
      </div>

      {/* ─── Bet Slip Modal ─── */}
      {betSlip && betSlip.picks && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm" onClick={() => setBetSlip(null)}>
          <div className="bg-[#0E0E14] border border-[#D4A017]/40 rounded-2xl w-full max-w-lg mx-4 overflow-hidden shadow-2xl" onClick={e => e.stopPropagation()}>
            {/* Header */}
            <div className="bg-gradient-to-r from-[#D4A017] to-[#F5C842] px-6 py-4 flex items-center justify-between">
              <div>
                <div className="text-black font-black text-lg tracking-wide">HARD ROCK SPORTSBOOK</div>
                <div className="text-black/60 text-xs font-bold">Edge Crew Bet Slip</div>
              </div>
              <button onClick={() => setBetSlip(null)} className="text-black/60 hover:text-black">
                <X size={20} />
              </button>
            </div>

            {/* Meta */}
            <div className="px-6 py-3 border-b border-white/10 flex justify-between text-xs text-white/50">
              <span>ID: {betSlip.slip_id}</span>
              <span>{betSlip.generated}</span>
            </div>

            {/* Picks */}
            <div className="px-6 py-4 space-y-3 max-h-80 overflow-y-auto">
              {betSlip.picks.map((p, i) => (
                <div key={i} className="bg-white/[0.04] border border-white/10 rounded-xl p-3">
                  <div className="text-xs text-white/40 mb-1">{p.game}</div>
                  <div className="flex items-center justify-between">
                    <div>
                      <span className="text-white font-bold text-sm">{p.pick}</span>
                      <span className="ml-2 text-[10px] px-2 py-0.5 bg-[#D4A017]/15 text-[#D4A017] rounded-full font-bold">{p.type}</span>
                    </div>
                    <div className="text-right">
                      <div className="text-white font-bold text-sm">{p.amount}</div>
                      <div className="text-[10px] text-white/40">{p.book}</div>
                    </div>
                  </div>
                </div>
              ))}
            </div>

            {/* Footer */}
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
