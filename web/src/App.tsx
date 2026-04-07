import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import HomePage from './pages/HomePage'
import GameDetailPage from './pages/GameDetailPage'
import PicksPage from './pages/PicksPage'
import ProfilePage from './pages/ProfilePage'
import { useAppStore } from './store/useAppStore'

function App() {
  const user = useAppStore((s) => s.user)

  // Gate the entire app behind PIN login
  if (!user) {
    return (
      <Layout>
        <ProfilePage />
      </Layout>
    )
  }

  return (
    <Layout>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/game/:id" element={<GameDetailPage />} />
        <Route path="/picks" element={<PicksPage />} />
        <Route path="/profile" element={<ProfilePage />} />
      </Routes>
    </Layout>
  )
}

export default App
