import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import './App.css';
import Header from './components/Header';
import FightList from './pages/FightList';
import Player from './pages/Player';
import Library from './pages/Library';
import Annotate from './pages/Annotate';
import PipelineAccuracy from './pages/PipelineAccuracy';
import TrainingDataQA from './pages/TrainingDataQA';
import Users from './pages/Users';
import AuthProvider from './components/AuthProvider';
import RequireRole from './components/RequireRole';

export default function App() {
  return (
    <BrowserRouter>
      {/* Fixed background layer — flat black, no orbs/grain (brand.css, Sept 2026) */}
      <div style={{ position: 'fixed', inset: 0, zIndex: 0, background: 'var(--bg-base)', pointerEvents: 'none' }} />

      {/* App shell — renders only once /api/auth/me says who is signed in */}
      <AuthProvider>
        <div style={{ position: 'relative', zIndex: 1, display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>
          <Header />
          <Routes>
            <Route path="/" element={<FightList />} />
            <Route path="/fights/:id" element={<Player />} />
            <Route path="/fights/:id/annotate" element={<RequireRole role="labeller"><Annotate /></RequireRole>} />
            <Route path="/library" element={<Library />} />
            <Route path="/accuracy" element={<PipelineAccuracy />} />
            <Route path="/training-data" element={<RequireRole role="labeller"><TrainingDataQA /></RequireRole>} />
            <Route path="/training-data/:action" element={<RequireRole role="labeller"><TrainingDataQA /></RequireRole>} />
            <Route path="/training-data/:action/:eventId" element={<RequireRole role="labeller"><TrainingDataQA /></RequireRole>} />
            <Route path="/users" element={<RequireRole role="admin"><Users /></RequireRole>} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </div>
      </AuthProvider>
    </BrowserRouter>
  );
}
