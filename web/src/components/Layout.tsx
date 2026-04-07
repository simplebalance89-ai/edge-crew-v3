import { Link, useLocation } from 'react-router-dom'
import { Trophy, Calendar, User, LogOut, Layers } from 'lucide-react'
import { useAppStore } from '@/store/useAppStore'

interface LayoutProps {
  children: React.ReactNode
}

export default function Layout({ children }: LayoutProps) {
  const location = useLocation()
  const user = useAppStore((s) => s.user)
  const setUser = useAppStore((s) => s.setUser)
  
  const navItems = [
    { path: '/', label: 'Games', icon: Calendar },
    { path: '/parlay', label: 'Build Slip', icon: Layers },
    { path: '/picks', label: 'Picks', icon: Trophy },
    { path: '/profile', label: 'Profile', icon: User },
  ]

  return (
    <div className="min-h-screen bg-[#08080C] text-white">
      {/* Header */}
      <header className="border-b border-[#1A1A28] bg-[#0E0E14]/80 backdrop-blur sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            {/* EC⁸ Logo */}
            <Link to="/" className="flex items-baseline gap-1">
              <span className="text-3xl font-black tracking-tighter bg-gradient-to-r from-[#00E5FF] to-[#FF2D78] bg-clip-text text-transparent">
                EC
              </span>
              <sup className="text-lg font-bold text-[#FF2D78] -ml-1">8</sup>
            </Link>
            
            <nav className="flex items-center gap-1">
              {user && (
                <div className="hidden sm:flex items-center gap-2 mr-3 px-3 py-1.5 rounded-lg bg-[#0E0E14] border border-[#1A1A28]">
                  <div className="w-7 h-7 rounded-full bg-gradient-to-br from-[#00E5FF] to-[#FF2D78] flex items-center justify-center text-xs font-black text-black">
                    {user.name[0]}
                  </div>
                  <span className="text-sm font-bold text-[#E8E8EC]">{user.name}</span>
                  <span className="text-xs text-[#6E6E80]">${(user.bankroll?.current ?? 0).toFixed(0)}</span>
                  <button
                    onClick={() => setUser(null)}
                    className="ml-1 text-[#6E6E80] hover:text-red-400"
                    title="Logout"
                  >
                    <LogOut size={14} />
                  </button>
                </div>
              )}
              {navItems.map(({ path, label, icon: Icon }) => {
                const isActive = location.pathname === path
                return (
                  <Link
                    key={path}
                    to={path}
                    className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium text-sm transition-all ${
                      isActive
                        ? 'bg-[#00E5FF]/10 text-[#00E5FF] border border-[#00E5FF]/30'
                        : 'text-[#6E6E80] hover:text-white hover:bg-white/5'
                    }`}
                  >
                    <Icon size={18} />
                    <span>{label}</span>
                  </Link>
                )
              })}
            </nav>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 py-6">
        {children}
      </main>
      
      {/* Footer with tagline */}
      <footer className="border-t border-[#1A1A28] mt-auto">
        <div className="max-w-7xl mx-auto px-4 py-4 text-center">
          <p className="text-[#6E6E80] text-sm font-light tracking-wide">
            A Century of Edge.
          </p>
        </div>
      </footer>
    </div>
  )
}
