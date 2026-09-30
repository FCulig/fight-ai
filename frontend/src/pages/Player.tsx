import { useRef, useState, useEffect, useMemo } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useEvents } from '../hooks/useEvents';
import { useFights } from '../hooks/useFights';
import { useFighterFrames } from '../hooks/useFighterFrames';
import { useRounds } from '../hooks/useRounds';
import { useWindowWidth } from '../hooks/useWindowWidth';
import { useAuth } from '../hooks/useAuth';
import { isEditingLabels, isFightViewable, isLabelEditable, isLabelingReady } from '../types/Fight';
import { deleteFight, reopenLabeling, videoUrl } from '../services/api';
import ConfirmDialog from '../components/ConfirmDialog';
import VideoPlayer from '../components/VideoPlayer';
import VideoControls from '../components/VideoControls';
import FrameInfo from '../components/FrameInfo';
import FighterOverlay, { type FighterOverlayHandle } from '../components/FighterOverlay';
import LiveFeed from '../components/player/LiveFeed';
import FightReport from '../components/player/FightReport';
import MatchupCard from '../components/player/MatchupCard';
import FightPurposeBadge from '../components/FightPurposeBadge';
import { fighters as mockFighters, withRealName } from '../mocks/fightMock';

const formatDuration = (seconds: number) => {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${String(s).padStart(2, '0')}`;
};

export default function Player() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const fightId = id ? Number(id) : null;
  const { can } = useAuth();

  const videoRef = useRef<HTMLVideoElement>(null);
  const overlayRef = useRef<FighterOverlayHandle>(null);
  const rafRef = useRef<number | null>(null);
  const fpsRef = useRef<number>(30);
  const lastFrameRef = useRef<number>(-1);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [showBoxes, setShowBoxes] = useState(true);
  const [showSkeletons, setShowSkeletons] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [reopening, setReopening] = useState(false);
  const [reopenError, setReopenError] = useState<string | null>(null);

  const { fights } = useFights();
  const selectedFight = fights.find(f => f.id === fightId) ?? null;
  // A fight is never re-run through the pipeline, so exactly one source ever
  // has real content: 'ai_labeled' fights get predictions, everything else
  // (training_data/reference) only ever gets hand labels — the pipeline's
  // reduced track for those never runs strike/state detection.
  const eventSource = selectedFight?.purpose === 'ai_labeled' ? 'prediction' : 'label';
  const { events: fetchedEvents, loading: eventsLoading } = useEvents(fightId, { source: eventSource });
  // Both sources only ever produce kind='point' rows for what LiveFeed/stats
  // need — filter defensively anyway rather than assume that never changes.
  const events = fetchedEvents.filter(e => e.kind === 'point');

  // corner_swap spans always come from Annotate (source='label'), regardless
  // of which source the point-event feed above is using — a display-only
  // correction for FighterOverlay, see its own docs.
  const { events: swapEvents } = useEvents(fightId, { source: 'label', kind: 'corner_swap' });
  const cornerSwapSpans = useMemo(
    () => swapEvents.map(e => ({ frame: e.frame, end_frame: e.end_frame })),
    [swapEvents],
  );
  const { frameMap } = useFighterFrames(fightId);
  const { rounds } = useRounds(fightId);
  const width = useWindowWidth();
  const narrow = width < 1100;

  const fps = selectedFight?.fps ?? 30;
  fpsRef.current = fps;

  const isProcessing = selectedFight !== null && !isFightViewable(selectedFight.state);
  // labeling_in_progress isn't "processing" — the pipeline is done and the
  // fight is waiting in Annotate (e.g. Back was pressed mid-edit). Say so and
  // offer the way back, rather than a spinner that will never resolve.
  const isBeingLabeled = selectedFight !== null && isLabelingReady(selectedFight.state);
  const editingLabels = selectedFight !== null && isEditingLabels(selectedFight);

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;
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
  }, [isPlaying]);

  const currentFrame = Math.floor(currentTime * fps) + 1;
  const currentMs = Math.floor(currentTime * 1000);

  const videoSrc = selectedFight ? videoUrl(selectedFight.id) : undefined;

  const togglePlay = () => {
    const video = videoRef.current;
    if (!video) return;
    isPlaying ? video.pause() : video.play();
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

  const fightName = selectedFight
    ? selectedFight.video_path.split('/').pop()?.replace(/\.[^/.]+$/, '') ?? ''
    : '';

  const handleDelete = async () => {
    if (fightId === null) return;
    setDeleting(true);
    setDeleteError(null);
    try {
      // The DELETE unlinks the file this <video> is streaming — stop playback
      // (and the requestVideoFrameCallback loop) before pulling it out from under us.
      videoRef.current?.pause();
      setIsPlaying(false);
      await deleteFight(fightId);
      // replace: Back must not return to a now-dead /fights/{id}.
      navigate('/', { replace: true });
    } catch (err) {
      setDeleteError(err instanceof Error ? err.message : 'Failed to delete fight');
      setDeleting(false);
    }
  };

  // Flip the fight back to labeling_in_progress first — Annotate only opens
  // on that state — then hand over. Annotate's own Finish Labeling returns it
  // to labeling_complete.
  const handleEditLabels = async () => {
    if (fightId === null) return;
    setReopening(true);
    setReopenError(null);
    try {
      videoRef.current?.pause();
      setIsPlaying(false);
      await reopenLabeling(fightId);
      navigate(`/fights/${fightId}/annotate`);
    } catch (err) {
      setReopenError(err instanceof Error ? err.message : 'Failed to open the fight for editing');
      setReopening(false);
    }
  };

  const currentRound =
    rounds.find(r => currentFrame >= r.start_frame && currentFrame <= r.end_frame)
      ?.round_number ?? '-';

  // Round 1 end in seconds for pace chart playhead
  const r1Round = rounds.find(r => r.round_number === 1);
  const r1EndSeconds = r1Round ? r1Round.end_frame / fps : 0;

  const displayFighters = {
    red: withRealName(mockFighters.red, selectedFight?.red_fighter_name),
    blue: withRealName(mockFighters.blue, selectedFight?.blue_fighter_name),
  };

  if (isProcessing) {
    return (
      <div style={{
        display: 'flex', flex: 1, alignItems: 'center', justifyContent: 'center',
        minHeight: 'calc(100vh - 58px)', padding: 24,
      }}>
        <div className="glass" style={{
          textAlign: 'center',
          borderRadius: 20,
          padding: '48px 56px',
          maxWidth: 420,
        }}>
          <span className="material-symbols-outlined" style={{
            fontSize: 40, color: 'var(--text-muted)', display: 'block', marginBottom: 16,
            animation: isBeingLabeled ? undefined : 'spin 1.5s linear infinite',
          }}>{isBeingLabeled ? 'edit_note' : 'progress_activity'}</span>
          <h2 style={{ fontSize: 20, fontWeight: 800, margin: '0 0 10px', color: 'var(--text-primary)' }}>
            {editingLabels
              ? 'This fight\'s labels are being edited'
              : isBeingLabeled ? 'This fight is being labeled' : 'This fight is still being processed'}
          </h2>
          <p style={{ fontSize: 14, color: 'var(--text-disabled)', margin: '0 0 20px', lineHeight: 1.6 }}>
            {isBeingLabeled
              ? 'Press Finish Labeling on the labeling page to bring it back to the Player.'
              : 'The AI pipeline is analyzing the video. This usually takes a few minutes.'}
          </p>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, justifyContent: 'center' }}>
            <button
              onClick={() => navigate('/')}
              className="btn-glass"
              style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '8px 16px', fontSize: 13, fontWeight: 600, borderRadius: 8, whiteSpace: 'nowrap' }}
            >
              <span className="material-symbols-outlined" style={{ fontSize: 16 }}>arrow_back</span>
              Back to fights
            </button>
            {isBeingLabeled && can('labeller') && (
              <button
                onClick={() => navigate(`/fights/${fightId}/annotate`)}
                className="btn-glass"
                style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '8px 16px', fontSize: 13, fontWeight: 600, borderRadius: 8, whiteSpace: 'nowrap' }}
              >
                <span className="material-symbols-outlined" style={{ fontSize: 16 }}>edit</span>
                {editingLabels ? 'Continue editing' : 'Open labeling'}
              </button>
            )}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div style={{
      position: 'relative',
      zIndex: 1,
      maxWidth: 1500,
      margin: '0 auto',
      padding: narrow ? '16px 14px 48px' : '22px 30px 70px',
    }}>
      {/* Back nav */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16, flexWrap: 'wrap' }}>
        <button
          onClick={() => navigate('/')}
          className="icon-btn"
          title="All fights"
          style={{ width: 38, height: 38 }}
        >
          <span className="material-symbols-outlined" style={{ fontSize: 20 }}>arrow_back</span>
        </button>
        {selectedFight && (
          <div style={{ minWidth: 0 }}>
            <div className="font-display" style={{ fontSize: narrow ? 22 : 30, letterSpacing: '0.02em', color: 'var(--text-primary)', lineHeight: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {displayFighters.red.name} vs {displayFighters.blue.name}
            </div>
            <div style={{ fontSize: 12.5, color: 'var(--text-muted)', fontWeight: 600, marginTop: 3 }}>
              {rounds.length || '—'} round{rounds.length === 1 ? '' : 's'} · {duration ? formatDuration(duration) : fightName} · {fps} fps
            </div>
          </div>
        )}
        {selectedFight && <FightPurposeBadge purpose={selectedFight.purpose} />}
        <span style={{ flex: 1 }} />
        {reopenError && (
          <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--red-500)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {reopenError}
          </span>
        )}
        {selectedFight && isLabelEditable(selectedFight) && can('labeller') && (
          <button
            onClick={handleEditLabels}
            disabled={reopening}
            title="Re-open this fight in the labeling page"
            aria-label="Edit labels"
            className="btn-glass"
            style={{
              flexShrink: 0, display: 'inline-flex', alignItems: 'center', gap: 5,
              padding: narrow ? '7px 10px' : '7px 14px',
              fontSize: 12, fontWeight: 700, fontFamily: 'inherit',
              cursor: reopening ? 'not-allowed' : 'pointer', opacity: reopening ? 0.6 : 1,
            }}
          >
            <span className="material-symbols-outlined" style={{ fontSize: 16 }}>{reopening ? 'progress_activity' : 'edit'}</span>
            {!narrow && 'Edit labels'}
          </button>
        )}
        {selectedFight && can('admin') && (
          <button
            onClick={() => { setDeleteError(null); setConfirmDelete(true); }}
            title="Delete this fight"
            style={{
              flexShrink: 0, display: 'inline-flex', alignItems: 'center', gap: 5,
              padding: narrow ? '6px 8px' : '6px 12px', borderRadius: 999,
              border: '1px solid var(--f-red-dim)', background: 'rgba(239,68,68,0.08)',
              color: 'var(--red-500)', fontSize: 12, fontWeight: 700, cursor: 'pointer', fontFamily: 'inherit',
            }}
          >
            <span className="material-symbols-outlined" style={{ fontSize: 16 }}>delete</span>
            {!narrow && 'Delete'}
          </button>
        )}
      </div>

      <ConfirmDialog
        open={confirmDelete}
        title="DELETE FIGHT?"
        message={
          <>
            <strong style={{ color: 'var(--text-primary)' }}>{fightName}</strong> will be permanently
            deleted — the source video file, all pipeline predictions, hand labels, rounds, and
            tracked fighter frames. This cannot be undone.
          </>
        }
        confirmLabel="Delete fight"
        confirmIcon="delete_forever"
        danger
        busy={deleting}
        error={deleteError}
        onCancel={() => setConfirmDelete(false)}
        onConfirm={handleDelete}
      />

      {/* TOP GRID: video | live feed */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: narrow ? '1fr' : '1fr 410px',
        gap: 16,
        alignItems: 'stretch',
      }}>
        {/* Video column */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {/* Video stage */}
          <VideoPlayer
            ref={videoRef}
            src={videoSrc}
            isPlaying={isPlaying}
            onTimeUpdate={() => { const v = videoRef.current; if (v) setCurrentTime(v.currentTime); }}
            onLoadedMetadata={() => { const v = videoRef.current; if (v) setDuration(v.duration); }}
            onPlay={() => setIsPlaying(true)}
            onPause={() => setIsPlaying(false)}
            onTogglePlay={togglePlay}
            onStepForward={() => stepFrame(1)}
            onStepBackward={() => stepFrame(-1)}
          >
            {selectedFight && (
              <FighterOverlay
                ref={overlayRef}
                frameMap={frameMap}
                fightWidth={selectedFight.width}
                fightHeight={selectedFight.height}
                showBoxes={showBoxes}
                showSkeletons={showSkeletons}
                cornerSwapSpans={cornerSwapSpans}
              />
            )}
            {/* Round chip */}
            <div style={{ position: 'absolute', top: 14, left: 16, display: 'flex', gap: 8, alignItems: 'center', pointerEvents: 'none' }}>
              <span style={{ background: 'rgba(0,0,0,0.55)', backdropFilter: 'blur(8px)', color: '#fff', fontSize: 11, fontWeight: 700, padding: '4px 10px', borderRadius: 6, letterSpacing: '0.06em' }}>
                {currentRound === '-' ? 'LOADING…' : `ROUND ${currentRound}`}
              </span>
            </div>
          </VideoPlayer>

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

          {/* Overlay controls */}
          <div style={{ display: 'flex', gap: 16, padding: '6px 2px' }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer', fontSize: 12, color: 'var(--text-muted)', fontWeight: 500 }}>
              <input
                type="checkbox"
                checked={showBoxes}
                onChange={e => setShowBoxes(e.target.checked)}
                style={{ accentColor: 'var(--accent)', width: 14, height: 14, cursor: 'pointer' }}
              />
              Fighter Boxes
            </label>
            <label style={{ display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer', fontSize: 12, color: 'var(--text-muted)', fontWeight: 500 }}>
              <input
                type="checkbox"
                checked={showSkeletons}
                onChange={e => setShowSkeletons(e.target.checked)}
                style={{ accentColor: 'var(--accent)', width: 14, height: 14, cursor: 'pointer' }}
              />
              Skeletons
            </label>
          </div>
        </div>

        {/* Live feed column */}
        {narrow ? (
          <div style={{ height: 420 }}>
            <LiveFeed
              events={events}
              currentFrame={currentFrame}
              fps={fps}
              onSeek={handleSeek}
              redName={displayFighters.red.name}
              blueName={displayFighters.blue.name}
              redFighterId={selectedFight?.red_fighter_id}
              rounds={rounds}
              cornerSwapSpans={cornerSwapSpans}
            />
          </div>
        ) : (
          <div style={{ position: 'relative' }}>
            <div style={{ position: 'absolute', inset: 0 }}>
              <LiveFeed
                events={events}
                currentFrame={currentFrame}
                fps={fps}
                onSeek={handleSeek}
                redName={displayFighters.red.name}
                blueName={displayFighters.blue.name}
                redFighterId={selectedFight?.red_fighter_id}
                rounds={rounds}
                cornerSwapSpans={cornerSwapSpans}
              />
            </div>
          </div>
        )}
      </div>

      {/* REPORT — summary tiles, head-to-head, per-fighter breakdown, momentum */}
      {!eventsLoading && (
        <FightReport
          currentFrame={currentFrame}
          events={events}
          fps={fps}
          rounds={rounds}
          fighters={displayFighters}
          redFighterId={selectedFight?.red_fighter_id}
          time={currentTime}
          duration={duration}
          r1EndSeconds={r1EndSeconds}
        />
      )}

      {/* MATCHUP */}
      <section style={{ marginTop: 56 }}>
        <span className="eyebrow">Matchup</span>
        <h2 className="font-display" style={{ fontSize: 'clamp(28px, 3.4vw, 40px)', lineHeight: 1, margin: '10px 0 22px', color: 'var(--text-primary)' }}>
          Tale of the tape.
        </h2>
        <MatchupCard fighters={displayFighters} />
      </section>
    </div>
  );
}
