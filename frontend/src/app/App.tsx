import { Navigate, Route, Routes } from 'react-router-dom'
import { LandingPage } from '../pages/LandingPage'
import { MapPage } from '../pages/MapPage'

export function App() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/map" element={<MapPage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
