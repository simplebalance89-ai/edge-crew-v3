import { Trophy } from 'lucide-react'

export default function PicksPage() {
  return (
    <div>
      <h1 className="text-2xl font-black mb-6">My Picks</h1>
      
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
    </div>
  )
}
