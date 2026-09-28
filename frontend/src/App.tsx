import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import './App.css';
import Header from './components/Header';
import FightList from './pages/FightList';
import Player from './pages/Player';
import Library from './pages/Library';
import Annotate from './pages/Annotate';
import PipelineAccuracy from './pages/PipelineAccuracy';
import TrainingDataQA from './pages/TrainingDataQA';

export default function App() {
  return (
    <BrowserRouter>
      {/* Fixed background layer — flat black, no orbs/grain (brand.css, Sept 2026) */}
      <div style={{ position: 'fixed', inset: 0, zIndex: 0, background: 'var(--bg-base)', pointerEvents: 'none' }} />

      {/* App shell */}
      <div style={{ position: 'relative', zIndex: 1, display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>
        <Header />
        <Routes>
          <Route path="/" element={<FightList />} />
          <Route path="/fights/:id" element={<Player />} />
          <Route path="/fights/:id/annotate" element={<Annotate />} />
          <Route path="/library" element={<Library />} />
          <Route path="/accuracy" element={<PipelineAccuracy />} />
          <Route path="/training-data" element={<TrainingDataQA />} />
          <Route path="/training-data/:action" element={<TrainingDataQA />} />
          <Route path="/training-data/:action/:eventId" element={<TrainingDataQA />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </div>
    </BrowserRouter>
  );
}
