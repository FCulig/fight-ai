import { useRef, useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useFights } from '../hooks/useFights';
import { useEvents } from '../hooks/useEvents';
import { useFighterFrames } from '../hooks/useFighterFrames';
import { useRounds } from '../hooks/useRounds';
import { useWindowWidth } from '../hooks/useWindowWidth';
import { createEvent, deleteEvent, finishLabeling, type CreateEventPayload } from '../services/api';
import type { Event } from '../types/Event';
import { isFightViewable, isLabelingReady, STATE_LABELS } from '../types/Fight';
import VideoControls from '../components/VideoControls';
import FrameInfo from '../components/FrameInfo';
import type { FighterOverlayHandle } from '../components/FighterOverlay';
import AnnotateStage from '../components/annotate/AnnotateStage';
import FighterSelectCard from '../components/annotate/FighterSelectCard';
import EventPalette from '../components/annotate/EventPalette';
import FightEndModal, { type FightEndResult } from '../components/annotate/FightEndModal';
import KeyboardLegend from '../components/annotate/KeyboardLegend';
import AnnotationPanel from '../components/annotate/AnnotationPanel';
import SaveStatus from '../components/annotate/SaveStatus';
import { KEYMAP, colorForAction, iconForAction, successForAction, type Corner, type ToolItem } from '../components/annotate/taxonomy';

export default function Annotate() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const fightId = id ? Number(id) : null;

  const videoRef = useRef<HTMLVideoElement>(null);
  const overlayRef = useRef<FighterOverlayHandle>(null);
  const rafRef = useRef<number | null>(null);
  const fpsRef = useRef<number>(30);
  const lastFrameRef = useRef<number>(-1);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);

  const { fights } = useFights();
  const selectedFight = fights.find(f => f.id === fightId) ?? null;
  const { events: fetchedEvents, loading: eventsLoading } = useEvents(fightId);
  const { frameMap } = useFighterFrames(fightId);
  const { rounds } = useRounds(fightId);
  const width = useWindowWidth();
  const narrow = width < 1100;

  const fps = selectedFight?.fps ?? 30;
  fpsRef.current = fps;

  // Local mutable copy for optimistic add/remove — useEvents itself exposes no setter.
  const [events, setEvents] = useState<Event[]>([]);
  useEffect(() => {
    if (!eventsLoading) setEvents(fetchedEvents);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [eventsLoading, fightId]);

  const ready = selectedFight !== null && isLabelingReady(selectedFight.state);

  useEffect(() => {
    const video = videoRef.current;
    if (!video || !ready) return;
    if (!isPlaying) {
      if (rafRef.current !== null) {
        video.cancelVideoFrameCallback(rafRef.current);
        rafRef.current = null;
      }
      return;
    }
    const tick = (_now: DOMHighResTimeStamp, metadata: VideoFrameCallbackMetadata) => {
      const frame = Math.floor(metadata.mediaTime * fpsRef.current) + 1;
      overlayRef.current?.draw(frame);
      if (frame !== lastFrameRef.current) {
        lastFrameRef.current = frame;
        setCurrentTime(metadata.mediaTime);
      }
      rafRef.current = video.requestVideoFrameCallback(tick);
    };
    rafRef.current = video.requestVideoFrameCallback(tick);
    return () => {
      if (rafRef.current !== null) {
        video.cancelVideoFrameCallback(rafRef.current);
        rafRef.current = null;
      }
    };
  }, [isPlaying, ready]);

  const currentFrame = Math.floor(currentTime * fps) + 1;
  const currentMs = Math.floor(currentTime * 1000);
  const videoSrc = selectedFight ? `/fights/${selectedFight.id}/video` : undefined;

  const togglePlay = () => {
    const video = videoRef.current;
    if (!video) return;
    if (isPlaying) video.pause(); else video.play();
    setIsPlaying(!isPlaying);
  };

  const stepFrame = (delta: number) => {
    const video = videoRef.current;
    if (!video) return;
    video.pause();
    setIsPlaying(false);
    const newTime = Math.min(Math.max(video.currentTime + delta / fps, 0), video.duration);
    video.currentTime = newTime;
    setCurrentTime(newTime);
    overlayRef.current?.draw(Math.floor(newTime * fpsRef.current) + 1);
  };

  const handleSeek = (time: number) => {
    const video = videoRef.current;
    if (!video) return;
    video.currentTime = time;
    setCurrentTime(time);
    overlayRef.current?.draw(Math.floor(time * fpsRef.current) + 1);
  };

  const seekToFrame = (frame: number) => handleSeek(Math.max(0, (frame - 1) / fps));

  const currentRound = rounds.find(r => currentFrame >= r.start_frame && currentFrame <= r.end_frame)?.round_number ?? '-';

  const redName = selectedFight?.red_fighter_name ?? 'Red corner';
  const blueName = selectedFight?.blue_fighter_name ?? 'Blue corner';

  // ---- annotation logging state ----
  const [selected, setSelected] = useState<Corner | null>(null);
  const [toast, setToast] = useState<{ text: string; color: string; icon: string } | null>(null);
  const [flashId, setFlashId] = useState<number | null>(null);
  const [hint, setHint] = useState(false);
  const [endOpen, setEndOpen] = useState(false);
  const [savingCount, setSavingCount] = useState(0);
  const [finishing, setFinishing] = useState(false);

  const frameRef = useRef(1);
  frameRef.current = currentFrame;
  const selRef = useRef<Corner | null>(null);
  selRef.current = selected;
  const endOpenRef = useRef(false);
  endOpenRef.current = endOpen;
  const sessionIdsRef = useRef<number[]>([]);

  const toastTimer = useRef<ReturnType<typeof setTimeout>>(undefined);
  const hintTimer = useRef<ReturnType<typeof setTimeout>>(undefined);
  const flashTimer = useRef<ReturnType<typeof setTimeout>>(undefined);

  const showToast = (text: string, color: string, icon: string) => {
    setToast({ text, color, icon });
    clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast(null), 1100);
  };

  const flash = (eventId: number) => {
    setFlashId(eventId);
    clearTimeout(flashTimer.current);
    flashTimer.current = setTimeout(() => setFlashId(null), 700);
  };

  const addEvent = async (payload: CreateEventPayload) => {
    if (!fightId) return null;
    setSavingCount(c => c + 1);
    try {
      const created = await createEvent(fightId, payload);
      setEvents(prev => [...prev, created]);
      sessionIdsRef.current.push(created.id);
      flash(created.id);
      return created;
    } catch {
      showToast('Failed to save event', 'var(--f-red)', 'error');
      return null;
    } finally {
      setSavingCount(c => c - 1);
    }
  };

  const removeEvent = async (eventId: number) => {
    setSavingCount(c => c + 1);
    try {
      await deleteEvent(eventId);
      setEvents(prev => prev.filter(e => e.id !== eventId));
      sessionIdsRef.current = sessionIdsRef.current.filter(x => x !== eventId);
    } catch {
      showToast('Failed to delete event', 'var(--f-red)', 'error');
    } finally {
      setSavingCount(c => c - 1);
    }
  };

  const undo = () => {
    const lastId = sessionIdsRef.current[sessionIdsRef.current.length - 1];
    if (lastId == null) return;
    removeEvent(lastId);
  };

  const logTool = (item: ToolItem) => {
    if (!selectedFight) return;
    const corner = selRef.current;
    if (item.needsFighter && !corner) {
      setHint(true);
      clearTimeout(hintTimer.current);
      hintTimer.current = setTimeout(() => setHint(false), 1100);
      showToast('Select a fighter first', 'var(--f-red)', 'error');
      return;
    }
    const fighterId = item.needsFighter
      ? (corner === 'red' ? selectedFight.red_fighter_id : selectedFight.blue_fighter_id)
      : null;
    const fighterName = corner === 'red' ? redName : corner === 'blue' ? blueName : '';
    const description = item.text(fighterName);
    const color = colorForAction(item.action);
    const icon = iconForAction(item.action);
    addEvent({
      frame: frameRef.current,
      description,
      fighter_id: fighterId,
      action: item.action,
      success: successForAction(item.action),
    }).then(created => {
      if (created) showToast(`${item.name}${fighterName ? ' · ' + fighterName : ''}`, color, icon);
    });
  };

  const confirmFightEnd = (result: FightEndResult) => {
    const winnerId = result.winner === 'red' ? selectedFight?.red_fighter_id ?? null
      : result.winner === 'blue' ? selectedFight?.blue_fighter_id ?? null : null;
    const winnerName = result.winner === 'red' ? redName : result.winner === 'blue' ? blueName : null;
    const outcome = result.method === 'Draw' || !winnerName
      ? 'Draw'
      : result.method === 'Decision' ? `${winnerName} by decision` : `${winnerName} by ${result.method}`;
    const description = `Fight ended — ${outcome}${result.detail ? ' (' + result.detail + ')' : ''}`;
    addEvent({
      frame: frameRef.current,
      description,
      fighter_id: winnerId,
      action: 'fight_end',
      success: null,
    }).then(created => {
      if (created) showToast(`Fight ended · ${result.method}`, 'var(--purple-600)', 'sports_score');
    });
    setEndOpen(false);
  };

  const handleFinishLabeling = async () => {
    if (!fightId) return;
    setFinishing(true);
    try {
      await finishLabeling(fightId);
      navigate(`/fights/${fightId}`);
    } catch (err) {
      showToast(err instanceof Error ? err.message : 'Failed to finish labeling', 'var(--f-red)', 'error');
      setFinishing(false);
    }
  };

  // stable "latest callback" ref so the global keydown listener (registered once)
  // always calls the current render's closures, without re-registering constantly
  const fnsRef = useRef({ togglePlay, stepFrame, logTool, undo, setSelected });
  fnsRef.current = { togglePlay, stepFrame, logTool, undo, setSelected };

  useEffect(() => {
    if (!ready) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      const target = e.target as HTMLElement;
      const tag = target.tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA' || target.isContentEditable) return;
      if (endOpenRef.current) return;

      const fns = fnsRef.current;
      const k = e.key;
      const time = (frameRef.current - 1) / fpsRef.current;

      if (k === ' ') { e.preventDefault(); fns.togglePlay(); return; }
      if (k === 'ArrowLeft') { e.preventDefault(); handleSeek(Math.max(0, time - (e.shiftKey ? 5 : 1))); return; }
      if (k === 'ArrowRight') { e.preventDefault(); handleSeek(time + (e.shiftKey ? 5 : 1)); return; }
      if (k === ',') { e.preventDefault(); fns.stepFrame(-1); return; }
      if (k === '.') { e.preventDefault(); fns.stepFrame(1); return; }
      if (k === 'Escape') { fns.setSelected(null); return; }

      const lk = k.length === 1 ? k.toLowerCase() : k;
      if (lk === 'r') { fns.setSelected('red'); return; }
      if (lk === 'b') { fns.setSelected('blue'); return; }
      if (k === 'Backspace' || lk === 'z') { e.preventDefault(); fns.undo(); return; }

      const tool = KEYMAP[lk];
      if (tool) { e.preventDefault(); fns.logTool(tool); }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [ready]);

  // ---- guard states ----
  if (selectedFight === null) {
    return (
      <div style={{ display: 'flex', flex: 1, alignItems: 'center', justifyContent: 'center', minHeight: 'calc(100vh - 58px)', padding: 24 }}>
        <span className="material-symbols-outlined" style={{ fontSize: 32, color: '#64748b', animation: 'spin 1.5s linear infinite' }}>progress_activity</span>
      </div>
    );
  }

  if (isFightViewable(selectedFight.state)) {
    return (
      <div style={{ display: 'flex', flex: 1, alignItems: 'center', justifyContent: 'center', minHeight: 'calc(100vh - 58px)', padding: 24 }}>
        <div style={{
          textAlign: 'center', background: 'rgba(255,255,255,0.04)', backdropFilter: 'blur(24px) saturate(160%)',
          border: '1px solid rgba(255,255,255,0.07)', borderRadius: 20, padding: '48px 56px', maxWidth: 420,
        }}>
          <span className="material-symbols-outlined" style={{ fontSize: 40, color: 'var(--accent)', display: 'block', marginBottom: 16 }}>check_circle</span>
          <h2 style={{ fontSize: 20, fontWeight: 800, margin: '0 0 10px', color: '#f1f5f9' }}>This fight is already labeled</h2>
          <p style={{ fontSize: 14, color: '#475569', margin: '0 0 20px', lineHeight: 1.6 }}>Open it in the Player to review the tagged events.</p>
          <button onClick={() => navigate(`/fights/${selectedFight.id}`)} className="btn-glass" style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '8px 16px', fontSize: 13, fontWeight: 600, borderRadius: 8 }}>
            <span className="material-symbols-outlined" style={{ fontSize: 16 }}>play_circle</span>
            Open Player
          </button>
        </div>
      </div>
    );
  }

  if (!ready) {
    return (
      <div style={{ display: 'flex', flex: 1, alignItems: 'center', justifyContent: 'center', minHeight: 'calc(100vh - 58px)', padding: 24 }}>
        <div style={{
          textAlign: 'center', background: 'rgba(255,255,255,0.04)', backdropFilter: 'blur(24px) saturate(160%)',
          border: '1px solid rgba(255,255,255,0.07)', borderRadius: 20, padding: '48px 56px', maxWidth: 420,
        }}>
          <span className="material-symbols-outlined" style={{ fontSize: 40, color: '#64748b', display: 'block', marginBottom: 16, animation: 'spin 1.5s linear infinite' }}>progress_activity</span>
          <h2 style={{ fontSize: 20, fontWeight: 800, margin: '0 0 10px', color: '#f1f5f9' }}>
            {STATE_LABELS[selectedFight.state] ?? 'Detecting fighters'}
          </h2>
          <p style={{ fontSize: 14, color: '#475569', margin: '0 0 20px', lineHeight: 1.6 }}>
            Fighters are still being detected — labeling opens once that's done.
          </p>
          <button onClick={() => navigate('/')} className="btn-glass" style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '8px 16px', fontSize: 13, fontWeight: 600, borderRadius: 8 }}>
            <span className="material-symbols-outlined" style={{ fontSize: 16 }}>arrow_back</span>
            Back to fights
          </button>
        </div>
      </div>
    );
  }

  return (
    <div style={{ position: 'relative', zIndex: 1, maxWidth: 1560, margin: '0 auto', padding: narrow ? '16px 14px 48px' : '22px 30px 70px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
        <button onClick={() => navigate('/')} className="icon-btn" style={{ width: 38, height: 38 }}>
          <span className="material-symbols-outlined" style={{ fontSize: 20 }}>arrow_back</span>
        </button>
        <div>
          <div className="font-display" style={{ fontSize: 30, letterSpacing: '0.03em', color: '#f1f5f9', lineHeight: 1 }}>SELF-ANNOTATE</div>
          <div style={{ fontSize: 12.5, color: '#64748b', fontWeight: 600, marginTop: 3 }}>{redName} vs {blueName}</div>
        </div>
        <span style={{ flex: 1 }} />
        <SaveStatus saving={savingCount > 0} />
        <button
          onClick={handleFinishLabeling}
          disabled={finishing}
          style={{
            display: 'inline-flex', alignItems: 'center', gap: 8, background: 'linear-gradient(135deg, #00daf3, #0099b0)',
            color: '#001f24', fontWeight: 700, fontSize: 13, border: 'none', borderRadius: 10, padding: '9px 16px',
            cursor: finishing ? 'not-allowed' : 'pointer', opacity: finishing ? 0.5 : 1,
            boxShadow: finishing ? 'none' : '0 0 16px rgba(0,218,243,0.25)', fontFamily: 'inherit',
          }}
        >
          <span className="material-symbols-outlined" style={{ fontSize: 18 }}>{finishing ? 'progress_activity' : 'task_alt'}</span>
          Finish Labeling
        </button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: narrow ? '1fr' : '1fr 460px', gap: 16, alignItems: 'stretch' }}>
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          <AnnotateStage
            videoRef={videoRef}
            overlayRef={overlayRef}
            src={videoSrc}
            isPlaying={isPlaying}
            onTimeUpdate={() => { const v = videoRef.current; if (v) setCurrentTime(v.currentTime); }}
            onLoadedMetadata={() => { const v = videoRef.current; if (v) setDuration(v.duration); }}
            onPlay={() => setIsPlaying(true)}
            onPause={() => setIsPlaying(false)}
            onTogglePlay={togglePlay}
            onStepForward={() => stepFrame(1)}
            onStepBackward={() => stepFrame(-1)}
            frameMap={frameMap}
            fightWidth={selectedFight.width}
            fightHeight={selectedFight.height}
            currentRound={currentRound}
            selectedCorner={selected}
            redName={redName}
            blueName={blueName}
            toast={toast}
          />

          <VideoControls
            isPlaying={isPlaying}
            currentTime={currentTime}
            duration={duration}
            onTogglePlay={togglePlay}
            onSeek={handleSeek}
            onStepBackward={() => stepFrame(-1)}
            onStepForward={() => stepFrame(1)}
          />

          <FrameInfo currentFrame={currentFrame} currentMs={currentMs} fps={fps} />

          <KeyboardLegend />
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div className="glass" style={{ padding: '18px 18px 20px', borderRadius: 14 }}>
            <div className="label" style={{ fontSize: 9.5, marginBottom: 11 }}>Active fighter</div>
            <FighterSelectCard
              selected={selected}
              onSelect={c => setSelected(s => (s === c ? null : c))}
              redName={redName}
              blueName={blueName}
              hint={hint}
            />
            <hr className="divider" style={{ margin: '18px 0 16px' }} />
            <EventPalette selected={selected !== null} onLog={logTool} onFightEnd={() => setEndOpen(true)} />
          </div>
        </div>
      </div>

      <AnnotationPanel
        events={events}
        rounds={rounds}
        duration={duration}
        fps={fps}
        currentFrame={currentFrame}
        onSeek={seekToFrame}
        onSetPlaying={setIsPlaying}
        onDelete={removeEvent}
        flashId={flashId}
        redFighterId={selectedFight.red_fighter_id}
        blueFighterId={selectedFight.blue_fighter_id}
        redName={redName}
        blueName={blueName}
      />

      {endOpen && (
        <FightEndModal
          currentRound={currentRound}
          timeLabel={`${Math.floor(currentTime / 60)}:${String(Math.floor(currentTime % 60)).padStart(2, '0')}`}
          redName={redName}
          blueName={blueName}
          onClose={() => setEndOpen(false)}
          onConfirm={confirmFightEnd}
        />
      )}
    </div>
  );
}
