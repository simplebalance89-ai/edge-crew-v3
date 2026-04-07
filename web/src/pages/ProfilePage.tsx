import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { User as UserIcon, LogOut, Check, X, Minus } from 'lucide-react'
import { login, getBankroll, getUserPicks, gradePick, adjustBankroll } from '@/services/api'
import { useAppStore } from '@/store/useAppStore'
import type { Bankroll, LockedPick } from '@/types'

const CREW_MEMBERS = ['Peter', 'Chinny', 'Jimmy'] as const

export default function ProfilePage() {
  const { user, setUser } = useAppStore()
  const [selectedUser, setSelectedUser] = useState<string>('')
  const [pin, setPin] = useState('')
  const [loginError, setLoginError] = useState('')
  const queryClient = useQueryClient()

  // Fetch bankroll when logged in
  const { data: bankroll } = useQuery<Bankroll>({
    queryKey: ['bankroll', user?.username],
    queryFn: () => getBankroll(user!.username),
    enabled: !!user?.username,
    refetchInterval: 10000,
  })

  // Fetch picks when logged in
  const { data: picks } = useQuery<LockedPick[]>({
    queryKey: ['userPicks', user?.username],
    queryFn: () => getUserPicks(user!.username),
    enabled: !!user?.username,
    refetchInterval: 10000,
  })

  // Manual bankroll adjust
  const adjustMutation = useMutation({
    mutationFn: (delta: number) => adjustBankroll(user!.username, delta),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['bankroll', user?.username] })
    },
  })

  const handleAdjust = (sign: 1 | -1) => {
    const raw = window.prompt(`Enter amount to ${sign > 0 ? 'add to' : 'subtract from'} bankroll:`, '0')
    if (!raw) return
    const amt = parseFloat(raw)
    if (isNaN(amt) || amt <= 0) return
    adjustMutation.mutate(sign * amt)
  }

  // Grade pick mutation
  const gradePickMutation = useMutation({
    mutationFn: ({ pickId, result }: { pickId: string; result: string }) =>
      gradePick(user!.username, pickId, result),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['userPicks', user?.username] })
      queryClient.invalidateQueries({ queryKey: ['bankroll', user?.username] })
    },
  })

  const handleLogin = async () => {
    if (!selectedUser || pin.length !== 4) {
      setLoginError('Select a user and enter 4-digit PIN')
      return
    }
    setLoginError('')
    try {
      const data = await login(selectedUser.toLowerCase(), pin)
      setUser(data)
      setPin('')
    } catch {
      setLoginError('Invalid PIN')
    }
  }

  const handleLogout = () => {
    setUser(null)
    setSelectedUser('')
    setPin('')
    queryClient.removeQueries({ queryKey: ['bankroll'] })
    queryClient.removeQueries({ queryKey: ['userPicks'] })
  }

  const br = bankroll || user?.bankroll
  const roi = br && br.wagered > 0 ? ((br.profit / br.wagered) * 100) : 0

  // ── Login Screen ──
  if (!user) {
    return (
      <div className="max-w-md mx-auto mt-16">
        <div className="text-center mb-8">
          <div className="w-20 h-20 bg-gradient-to-br from-[#00E5FF] to-[#FF2D78] rounded-full mx-auto mb-4 flex items-center justify-center">
            <UserIcon size={40} className="text-black" />
          </div>
          <h1 className="text-2xl font-black text-[#E8E8EC]">Edge Crew Login</h1>
          <p className="text-[#6E6E80] text-sm mt-1">Select your profile</p>
        </div>

        {/* User Buttons */}
        <div className="flex gap-3 mb-6 justify-center">
          {CREW_MEMBERS.map((name) => (
            <button
              key={name}
              onClick={() => { setSelectedUser(name); setLoginError('') }}
              className={`flex flex-col items-center gap-2 px-6 py-4 rounded-xl font-bold text-sm transition-all ${
                selectedUser === name
                  ? 'bg-gradient-to-br from-[#00E5FF]/20 to-[#FF2D78]/20 border-2 border-[#00E5FF] text-[#00E5FF]'
                  : 'bg-[#0E0E14] text-[#6E6E80] border border-[#1A1A28] hover:border-[#00E5FF]/30 hover:text-white'
              }`}
            >
              <div className={`w-12 h-12 rounded-full flex items-center justify-center text-lg font-black ${
                selectedUser === name ? 'bg-[#00E5FF] text-black' : 'bg-[#1A1A28] text-[#6E6E80]'
              }`}>
                {name[0]}
              </div>
              {name}
            </button>
          ))}
        </div>

        {/* PIN Input */}
        <div className="mb-6">
          <label className="block text-[#6E6E80] text-xs uppercase tracking-wider mb-2 text-center">
            Enter 4-Digit PIN
          </label>
          <input
            type="password"
            maxLength={4}
            value={pin}
            onChange={(e) => setPin(e.target.value.replace(/\D/g, '').slice(0, 4))}
            onKeyDown={(e) => e.key === 'Enter' && handleLogin()}
            placeholder="----"
            className="w-full text-center text-3xl tracking-[1rem] py-4 bg-[#0E0E14] border border-[#1A1A28] rounded-xl text-[#E8E8EC] placeholder-[#2A2A38] focus:outline-none focus:border-[#00E5FF]/50"
          />
        </div>

        {loginError && (
          <p className="text-red-400 text-sm text-center mb-4">{loginError}</p>
        )}

        <button
          onClick={handleLogin}
          disabled={!selectedUser || pin.length !== 4}
          className="w-full py-4 bg-gradient-to-r from-[#00E5FF] to-[#FF2D78] text-black font-black rounded-xl text-lg disabled:opacity-30 disabled:cursor-not-allowed transition-all hover:opacity-90"
        >
          Login
        </button>
      </div>
    )
  }

  // ── Profile Screen ──
  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div className="flex items-center gap-4">
          <div className="w-14 h-14 bg-gradient-to-br from-[#00E5FF] to-[#FF2D78] rounded-full flex items-center justify-center">
            <span className="text-2xl font-black text-black">{user.name[0]}</span>
          </div>
          <div>
            <h1 className="text-2xl font-black text-[#E8E8EC]">{user.name}</h1>
            <p className="text-[#6E6E80] text-sm">Edge Crew Member</p>
          </div>
        </div>
        <button
          onClick={handleLogout}
          className="flex items-center gap-2 px-4 py-2 text-[#6E6E80] hover:text-red-400 transition-all"
        >
          <LogOut size={18} />
          <span className="text-sm font-medium">Logout</span>
        </button>
      </div>

      {/* Bankroll Card */}
      {br && (
        <div className="bg-[#0E0E14] border border-[#1A1A28] rounded-xl p-6 mb-8">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-bold text-[#6E6E80] uppercase tracking-wider">Bankroll</h2>
            <div className="flex gap-2">
              <button
                onClick={() => handleAdjust(1)}
                className="px-3 py-1 rounded-lg bg-green-500/10 border border-green-500/30 text-green-400 text-xs font-bold hover:bg-green-500/20"
              >
                + Add
              </button>
              <button
                onClick={() => handleAdjust(-1)}
                className="px-3 py-1 rounded-lg bg-red-500/10 border border-red-500/30 text-red-400 text-xs font-bold hover:bg-red-500/20"
              >
                - Sub
              </button>
            </div>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-4">
            <div className="text-center">
              <div className="text-xs text-[#6E6E80] uppercase tracking-wider mb-1">Starting</div>
              <div className="text-xl font-black text-[#E8E8EC]">${br.starting.toFixed(0)}</div>
            </div>
            <div className="text-center">
              <div className="text-xs text-[#6E6E80] uppercase tracking-wider mb-1">Current</div>
              <div className={`text-xl font-black ${br.current >= br.starting ? 'text-green-400' : 'text-red-400'}`}>
                ${br.current.toFixed(2)}
              </div>
            </div>
            <div className="text-center">
              <div className="text-xs text-[#6E6E80] uppercase tracking-wider mb-1">Wagered</div>
              <div className="text-xl font-black text-[#E8E8EC]">${br.wagered.toFixed(2)}</div>
            </div>
            <div className="text-center">
              <div className="text-xs text-[#6E6E80] uppercase tracking-wider mb-1">Profit</div>
              <div className={`text-xl font-black ${br.profit >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                {br.profit >= 0 ? '+' : ''}{br.profit.toFixed(2)}
              </div>
            </div>
          </div>
          <div className="flex items-center justify-center gap-6 pt-4 border-t border-[#1A1A28]">
            <div className="text-center">
              <span className="text-green-400 font-black text-lg">{br.wins}</span>
              <span className="text-[#6E6E80] text-xs ml-1">W</span>
            </div>
            <span className="text-[#2A2A38]">-</span>
            <div className="text-center">
              <span className="text-red-400 font-black text-lg">{br.losses}</span>
              <span className="text-[#6E6E80] text-xs ml-1">L</span>
            </div>
            <span className="text-[#2A2A38]">-</span>
            <div className="text-center">
              <span className="text-yellow-400 font-black text-lg">{br.pushes}</span>
              <span className="text-[#6E6E80] text-xs ml-1">P</span>
            </div>
            <span className="text-[#2A2A38]">|</span>
            <div className="text-center">
              <span className={`font-black text-lg ${roi >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                {roi >= 0 ? '+' : ''}{roi.toFixed(1)}%
              </span>
              <span className="text-[#6E6E80] text-xs ml-1">ROI</span>
            </div>
          </div>
        </div>
      )}

      {/* Locked Picks */}
      <div>
        <h2 className="text-sm font-bold text-[#6E6E80] uppercase tracking-wider mb-4">
          Locked Picks ({picks?.length || 0})
        </h2>

        {(!picks || picks.length === 0) ? (
          <div className="bg-[#0E0E14] border border-[#1A1A28] rounded-xl p-8 text-center">
            <p className="text-[#6E6E80]">No picks locked yet. Grade some games and lock in your picks.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {picks.map((pick) => (
              <div
                key={pick.id}
                className={`bg-[#0E0E14] border rounded-xl p-4 flex items-center justify-between ${
                  pick.result === 'W' ? 'border-green-500/30' :
                  pick.result === 'L' ? 'border-red-500/30' :
                  pick.result === 'P' ? 'border-yellow-500/30' :
                  'border-[#1A1A28]'
                }`}
              >
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-xs font-bold text-[#00E5FF] uppercase">{pick.sport}</span>
                    <span className="text-xs text-[#6E6E80]">{pick.type.toUpperCase()}</span>
                    {pick.line !== 0 && (
                      <span className="text-xs text-[#6E6E80]">({pick.line > 0 ? '+' : ''}{pick.line})</span>
                    )}
                  </div>
                  <div className="font-bold text-[#E8E8EC]">{pick.team}</div>
                  <div className="text-xs text-[#6E6E80] mt-1">
                    ${pick.amount.toFixed(0)} @ {pick.odds > 0 ? '+' : ''}{pick.odds}
                    {pick.result !== 'pending' && (
                      <span className={`ml-2 font-bold ${
                        pick.profit > 0 ? 'text-green-400' : pick.profit < 0 ? 'text-red-400' : 'text-yellow-400'
                      }`}>
                        {pick.profit > 0 ? '+' : ''}{pick.profit.toFixed(2)}
                      </span>
                    )}
                  </div>
                </div>

                {pick.result === 'pending' ? (
                  <div className="flex gap-2">
                    <button
                      onClick={() => gradePickMutation.mutate({ pickId: pick.id, result: 'W' })}
                      className="w-10 h-10 rounded-lg bg-green-500/10 border border-green-500/30 text-green-400 hover:bg-green-500/20 flex items-center justify-center transition-all"
                      title="Win"
                    >
                      <Check size={18} />
                    </button>
                    <button
                      onClick={() => gradePickMutation.mutate({ pickId: pick.id, result: 'L' })}
                      className="w-10 h-10 rounded-lg bg-red-500/10 border border-red-500/30 text-red-400 hover:bg-red-500/20 flex items-center justify-center transition-all"
                      title="Loss"
                    >
                      <X size={18} />
                    </button>
                    <button
                      onClick={() => gradePickMutation.mutate({ pickId: pick.id, result: 'P' })}
                      className="w-10 h-10 rounded-lg bg-yellow-500/10 border border-yellow-500/30 text-yellow-400 hover:bg-yellow-500/20 flex items-center justify-center transition-all"
                      title="Push"
                    >
                      <Minus size={18} />
                    </button>
                  </div>
                ) : (
                  <div className={`w-10 h-10 rounded-lg flex items-center justify-center font-black text-lg ${
                    pick.result === 'W' ? 'bg-green-500/10 text-green-400' :
                    pick.result === 'L' ? 'bg-red-500/10 text-red-400' :
                    'bg-yellow-500/10 text-yellow-400'
                  }`}>
                    {pick.result}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
