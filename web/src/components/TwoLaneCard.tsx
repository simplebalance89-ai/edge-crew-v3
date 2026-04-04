import { useState } from 'react'
import { ChevronDown, ChevronUp, Zap, Brain } from 'lucide-react'
import type { ConvergenceResult } from '@/types'
import { CONVERGENCE_COLORS } from '@/types'

interface TwoLaneCardProps {
  data: ConvergenceResult
  onClick?: () => void
}

export default function TwoLaneCard({ data, onClick }: TwoLaneCardProps) {
  const [expanded, setExpanded] = useState(false)
  
  const { ourProcess, aiProcess, convergence, homeTeam, awayTeam } = data
  const statusColors = CONVERGENCE_COLORS[convergence.status] || CONVERGENCE_COLORS.DIVERGENT
  
  return (
    <div 
      className="bg-[#1a1a1a] border border-white/10 rounded-xl overflow-hidden animate-slide-up cursor-pointer hover:border-white/20 transition-all"
      onClick={onClick}
    >
      {/* Header - Matchup */}
      <div className="p-4 border-b border-white/10">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="font-bold text-lg">{awayTeam} @ {homeTeam}</h3>
            <p className="text-sm text-white/50">7:30 PM EST</p>
          </div>
          <div 
            className="px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider"
            style={{
              background: statusColors.bg,
              border: `1px solid ${statusColors.border}`,
              color: statusColors.text,
            }}
          >
            {convergence.status}
          </div>
        </div>
      </div>

      {/* TWO LANE FORK - The Core Architecture */}
      <div className="p-4">
        <div className="grid grid-cols-2 gap-4">
          
          {/* LEFT LANE - OUR PROCESS */}
          <div className="bg-[#f72585]/5 border border-[#f72585]/20 rounded-lg p-4">
            <div className="flex items-center gap-2 mb-3">
              <Zap size={16} className="text-[#f72585]" />
              <span className="text-[10px] font-black text-[#f72585] uppercase tracking-wider">
                Our Process
              </span>
            </div>
            
            <div className="text-center">
              <div className="text-3xl font-black text-[#f72585]">
                {ourProcess.score.toFixed(1)}
              </div>
              <div 
                className="inline-block px-3 py-1 rounded mt-1 font-bold"
                style={{
                  background: `rgba(247, 37, 133, 0.2)`,
                  color: '#f72585',
                }}
              >
                {ourProcess.grade}
              </div>
            </div>
            
            <div className="mt-3 text-xs text-white/60 text-center">
              Confidence: {ourProcess.confidence}%
            </div>
          </div>

          {/* RIGHT LANE - AI PROCESS */}
          <div className="bg-[#00d4aa]/5 border border-[#00d4aa]/20 rounded-lg p-4">
            <div className="flex items-center gap-2 mb-3">
              <Brain size={16} className="text-[#00d4aa]" />
              <span className="text-[10px] font-black text-[#00d4aa] uppercase tracking-wider">
                AI Process
              </span>
            </div>
            
            <div className="text-center">
              <div className="text-3xl font-black text-[#00d4aa]">
                {aiProcess.score.toFixed(1)}
              </div>
              <div 
                className="inline-block px-3 py-1 rounded mt-1 font-bold"
                style={{
                  background: `rgba(0, 212, 170, 0.2)`,
                  color: '#00d4aa',
                }}
              >
                {aiProcess.grade}
              </div>
            </div>
            
            <div className="mt-3 text-xs text-white/60 text-center">
              Model: {aiProcess.model || 'DeepSeek'}
            </div>
          </div>
        </div>

        {/* CONVERGENCE - Where lanes merge */}
        <div 
          className="mt-4 p-4 rounded-lg text-center"
          style={{
            background: statusColors.bg,
            border: `1px solid ${statusColors.border}`,
          }}
        >
          <div className="text-[10px] uppercase tracking-widest mb-1" style={{ color: statusColors.text }}>
            Convergence
          </div>
          <div className="flex items-center justify-center gap-4">
            <div>
              <div className="text-2xl font-black" style={{ color: statusColors.text }}>
                {convergence.consensusScore.toFixed(1)}
              </div>
              <div className="text-xs text-white/60">Consensus</div>
            </div>
            <div className="h-8 w-px bg-white/20" />
            <div>
              <div className="text-2xl font-black" style={{ color: statusColors.text }}>
                {convergence.consensusGrade}
              </div>
              <div className="text-xs text-white/60">Grade</div>
            </div>
            <div className="h-8 w-px bg-white/20" />
            <div>
              <div className="text-2xl font-black" style={{ color: statusColors.text }}>
                ±{convergence.delta.toFixed(1)}
              </div>
              <div className="text-xs text-white/60">Delta</div>
            </div>
          </div>
        </div>

        {/* Expandable Details */}
        {expanded && (
          <div className="mt-4 pt-4 border-t border-white/10 space-y-3">
            <div>
              <p className="text-xs text-white/40 uppercase tracking-wider mb-1">Our Process Thesis</p>
              <p className="text-sm text-white/80">{ourProcess.thesis || 'Strong rest advantage + home court edge'}</p>
            </div>
            <div>
              <p className="text-xs text-white/40 uppercase tracking-wider mb-1">AI Process Thesis</p>
              <p className="text-sm text-white/80">{aiProcess.thesis || 'Market mispricing on injury news'}</p>
            </div>
          </div>
        )}

        {/* Expand Toggle */}
        <button 
          className="w-full mt-3 py-2 flex items-center justify-center gap-1 text-xs text-white/40 hover:text-white/60 transition-colors"
          onClick={(e) => {
            e.stopPropagation()
            setExpanded(!expanded)
          }}
        >
          {expanded ? (
            <>Less <ChevronUp size={14} /></>
          ) : (
            <>More <ChevronDown size={14} /></>
          )}
        </button>
      </div>
    </div>
  )
}
