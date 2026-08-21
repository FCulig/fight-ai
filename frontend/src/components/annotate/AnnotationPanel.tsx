import { useState, useEffect, useMemo } from 'react';
import type { LabelEvent } from '../../types/LabelEvent';
import type { LabelSpan } from '../../types/LabelSpan';
import type { Round } from '../../types/Round';
import { FILTERS, categoryForAction, matchFilter } from './taxonomy';
import AnnotationTimeline from './AnnotationTimeline';
import AnnotationList from './AnnotationList';

interface ViewBtnProps {
  active: boolean;
  onClick: () => void;
  icon: string;
  label: string;
}

function ViewBtn({ active, onClick, icon, label }: ViewBtnProps) {
  return (
    <button
      onClick={onClick}
      style={{
        display: 'inline-flex', alignItems: 'center', gap: 6, padding: '6px 12px', borderRadius: 7, cursor: 'pointer',
        fontSize: 12, fontWeight: 700, border: 'none', background: active ? 'var(--accent)' : 'transparent',
        color: active ? 'var(--cyan-on)' : 'var(--text-muted)', fontFamily: 'inherit',
        transition: 'color .12s, background .12s',
      }}
    >
      <span className="material-symbols-outlined" style={{ fontSize: 16 }}>{icon}</span>{label}
    </button>
  );
}

interface AnnotationPanelProps {
  events: LabelEvent[];
  spans: LabelSpan[];
  rounds: Round[];
  duration: number;
  fps: number;
  currentFrame: number;
  onSeek: (frame: number) => void;
  onSetPlaying: (playing: boolean) => void;
  onDelete: (id: number) => void;
  onUpdateSpan: (id: number, patch: { start_frame?: number; end_frame?: number }) => void;
  onDeleteSpan: (id: number) => void;
  flashId: number | null;
  selectedEventId: number | null;
  onSelectEvent: (id: number | null) => void;
  redName: string;
  blueName: string;
}

export default function AnnotationPanel({
  events, spans, rounds, duration, fps, currentFrame, onSeek, onSetPlaying, onDelete, onUpdateSpan, onDeleteSpan,
  flashId, selectedEventId, onSelectEvent, redName, blueName,
}: AnnotationPanelProps) {
  const [view, setView] = useState<'timeline' | 'list'>(() => (localStorage.getItem('annot-view') as 'timeline' | 'list') || 'timeline');
  const [filter, setFilter] = useState('all');
  useEffect(() => { localStorage.setItem('annot-view', view); }, [view]);

  const shown = useMemo(
    () => [...events].filter(e => matchFilter(categoryForAction(e.action), filter)).sort((a, b) => a.frame - b.frame),
    [events, filter],
  );

  return (
    <div className="glass" style={{ borderRadius: 16, padding: '16px 18px 18px', marginTop: 16 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 14, flexWrap: 'wrap' }}>
        <span style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--accent)', boxShadow: '0 0 8px var(--accent)' }} />
        <span className="font-display" style={{ fontSize: 21, letterSpacing: '0.04em', color: 'var(--text-primary)' }}>ANNOTATION TIMELINE</span>
        <span style={{ fontSize: 11.5, color: 'var(--text-disabled)', fontWeight: 700 }}>{events.length} events</span>
        <span style={{ flex: 1 }} />
        <div style={{ display: 'flex', gap: 6 }}>
          {FILTERS.map(f => (
            <button key={f.key} className={'pill' + (filter === f.key ? ' active' : '')} onClick={() => setFilter(f.key)}>{f.label}</button>
          ))}
        </div>
        <div style={{ display: 'flex', gap: 3, padding: 3, borderRadius: 9, background: 'var(--surface-inner)', border: '1px solid var(--border-glass)' }}>
          <ViewBtn active={view === 'timeline'} onClick={() => setView('timeline')} icon="view_timeline" label="Timeline" />
          <ViewBtn active={view === 'list'} onClick={() => setView('list')} icon="view_list" label="List" />
        </div>
      </div>
      {view === 'timeline' ? (
        <AnnotationTimeline
          events={events}
          spans={spans}
          rounds={rounds}
          duration={duration}
          fps={fps}
          currentFrame={currentFrame}
          onSeek={onSeek}
          onSetPlaying={onSetPlaying}
          onUpdateSpan={onUpdateSpan}
          onDeleteSpan={onDeleteSpan}
          flashId={flashId}
          selectedEventId={selectedEventId}
          onSelectEvent={onSelectEvent}
          filter={filter}
          redName={redName}
          blueName={blueName}
        />
      ) : (
        <AnnotationList shown={shown} fps={fps} onSeek={onSeek} onDelete={onDelete} flashId={flashId} />
      )}
    </div>
  );
}
