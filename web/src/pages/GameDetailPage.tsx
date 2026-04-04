import { useParams } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import { Link } from 'react-router-dom'

export default function GameDetailPage() {
  const { id } = useParams()

  return (
    <div>
      <Link 
        to="/" 
        className="inline-flex items-center gap-2 text-white/60 hover:text-white mb-6 transition-colors"
      >
        <ArrowLeft size={20} />
        Back to games
      </Link>

      <div className="bg-[#1a1a1a] border border-white/10 rounded-xl p-8 text-center">
        <h1 className="text-2xl font-bold mb-4">Game Detail</h1>
        <p className="text-white/60">Game ID: {id}</p>
        <p className="text-white/40 text-sm mt-4">
          Full game analysis with detailed two-lane breakdown coming soon...
        </p>
      </div>
    </div>
  )
}
