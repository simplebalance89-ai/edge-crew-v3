import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import HomePage from './pages/HomePage'
import GameDetailPage from './pages/GameDetailPage'
import PicksPage from './pages/PicksPage'

function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/game/:id" element={<GameDetailPage />} />
        <Route path="/picks" element={<PicksPage />} />
      </Routes>
    </Layout>
  )
}

export default App
