import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import './App.css';
import Header from './components/Header';
import FightList from './pages/FightList';
import Player from './pages/Player';
import Library from './pages/Library';
import Annotate from './pages/Annotate';

export default function App() {
  return (
    <BrowserRouter>
      {/* Fixed background layer */}
      <div style={{ position: 'fixed', inset: 0, zIndex: 0, background: '#050709', overflow: 'hidden', pointerEvents: 'none' }}>
        {/* Ambient orbs */}
        <div style={{
          position: 'absolute', width: 700, height: 700, borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(0,180,255,0.13) 0%, transparent 68%)',
          top: -180, left: -150,
          animation: 'orb-drift-a 18s ease-in-out infinite',
        }} />
        <div style={{
          position: 'absolute', width: 600, height: 600, borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(124,58,237,0.11) 0%, transparent 68%)',
          bottom: -120, right: -100,
          animation: 'orb-drift-b 22s ease-in-out infinite',
        }} />
        <div style={{
          position: 'absolute', width: 400, height: 400, borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(255,100,50,0.08) 0%, transparent 68%)',
          top: '40%', right: '20%',
          animation: 'orb-drift-c 26s ease-in-out infinite',
        }} />

        {/* Film grain */}
        <div className="grain-overlay" />
      </div>

      {/* App shell */}
      <div style={{ position: 'relative', zIndex: 1, display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>
        <Header />
        <Routes>
          <Route path="/" element={<FightList />} />
          <Route path="/fights/:id" element={<Player />} />
          <Route path="/fights/:id/annotate" element={<Annotate />} />
          <Route path="/library" element={<Library />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </div>
    </BrowserRouter>
  );
}
