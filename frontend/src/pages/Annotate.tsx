import { useRef, useState, useEffect, useMemo } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useFights } from '../hooks/useFights';
import { useEvents } from '../hooks/useEvents';
import { useFighterFrames } from '../hooks/useFighterFrames';
import { useRounds } from '../hooks/useRounds';
import { useWindowWidth } from '../hooks/useWindowWidth';
import { useAuth } from '../hooks/useAuth';
import {
  createEvent, updateEvent, deleteEvent, finishLabeling, deleteFight, reopenLabeling, videoUrl,
  type CreateEventPayload,
} from '../services/api';
import type { SpanKind } from '../components/annotate/taxonomy';
import { isEditingLabels, isFightViewable, isLabelEditable, isLabelingReady, needsRoundReview, STATE_LABELS } from '../types/Fight';
import type { Event } from '../types/Event';
import { describeEvent } from '../utils/describeEvent';
import { isFrameSwapped } from '../utils/cornerSwap';
import ConfirmDialog from '../components/ConfirmDialog';
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
import FightPurposeBadge from '../components/FightPurposeBadge';
import { KEYMAP, colorForAction, iconForAction, successForAction, type Corner, type ToolItem } from '../components/annotate/taxonomy';

export default function Annotate() {
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

  const { fights, setFights } = useFights();
  const selectedFight = fights.find(f => f.id === fightId) ?? null;
  const { events: allEvents, setEvents: setAllEvents } = useEvents(fightId, { source: 'label' });
  const events = useMemo(() => allEvents.filter(e => e.kind === 'point'), [allEvents]);
  const spans = useMemo(() => allEvents.filter(e => e.kind !== 'point'), [allEvents]);
  const { frameMap } = useFighterFrames(fightId);
  const { rounds } = useRounds(fightId);
  const width = useWindowWidth();
  const narrow = width < 1100;

  const fps = selectedFight?.fps ?? 30;
  fpsRef.current = fps;

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
  const videoSrc = selectedFight ? videoUrl(selectedFight.id) : undefined;

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

  // The labeller's round spans win over the AI's, which may have collapsed
  // the fight into one round. The AI rounds cover the moment before the
  // spans have loaded.
  const currentRound = spans.find(
    s => s.kind === 'round' && s.end_frame != null && currentFrame >= s.frame && currentFrame <= s.end_frame,
  )?.value
    ?? rounds.find(r => currentFrame >= r.start_frame && currentFrame <= r.end_frame)?.round_number
    ?? '-';

  const redName = selectedFight?.red_fighter_name ?? 'Red corner';
  const blueName = selectedFight?.blue_fighter_name ?? 'Blue corner';

  // Reconstructs each point event's display text on the fly (description is
  // only ever stored for fight_end) — including the swap-corrected fighter
  // name for any event whose own frame falls inside a corner_swap span, so
  // reviewing the timeline reflects a swap the moment it's marked, even for
  // strikes logged before the span existed.
  const cornerSwapSpans = useMemo(
    () => spans.filter(s => s.kind === 'corner_swap').map(s => ({ frame: s.frame, end_frame: s.end_frame })),
    [spans],
  );
  const describe = (e: Event) => describeEvent(e, {
    redName, blueName, swapped: isFrameSwapped(e.frame, cornerSwapSpans),
  });

  // ---- annotation logging state ----
  const [selected, setSelected] = useState<Corner | null>(null);
  const [toast, setToast] = useState<{ text: string; color: string; icon: string } | null>(null);
  const [flashId, setFlashId] = useState<number | null>(null);
  const [hint, setHint] = useState(false);
  const [endOpen, setEndOpen] = useState(false);
  const [savingCount, setSavingCount] = useState(0);
  const [finishing, setFinishing] = useState(false);
  const [reopening, setReopening] = useState(false);
  const [reopenError, setReopenError] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deletingFight, setDeletingFight] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  // Timeline clip selected by click — Delete removes it. Separate from
  // `flashId` (a transient highlight after creation) and from `selected`
  // (the red/blue corner for the *next* logged event).
  const [selectedEventId, setSelectedEventId] = useState<number | null>(null);

  const frameRef = useRef(1);
  frameRef.current = currentFrame;
  const selRef = useRef<Corner | null>(null);
  selRef.current = selected;
  const endOpenRef = useRef(false);
  endOpenRef.current = endOpen;
  const confirmDeleteRef = useRef(false);
  confirmDeleteRef.current = confirmDelete;
  const selectedEventIdRef = useRef<number | null>(null);
  selectedEventIdRef.current = selectedEventId;
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
      const created = await createEvent(fightId, { kind: 'point', ...payload });
      setAllEvents(prev => [...prev, created]);
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
    if (!fightId) return;
    setSavingCount(c => c + 1);
    try {
      await deleteEvent(fightId, eventId);
      setAllEvents(prev => prev.filter(e => e.id !== eventId));
      sessionIdsRef.current = sessionIdsRef.current.filter(x => x !== eventId);
      if (selectedEventIdRef.current === eventId) setSelectedEventId(null);
    } catch {
      showToast('Failed to delete event', 'var(--f-red)', 'error');
    } finally {
      setSavingCount(c => c - 1);
    }
  };

  // corner_swap / excluded are start/end toggles: one key opens a span at the
  // playhead, the next press of the same key closes it. `openSpanRef` tracks
  // the in-flight span id per kind so the second press knows what to close.
  const openSpanRef = useRef<Partial<Record<SpanKind, number>>>({});
  const SPAN_LABEL: Record<SpanKind, string> = { round: 'Round', corner_swap: 'Corner swap', excluded: 'Excluded' };

  // openSpanRef only lives in memory — leaving Annotate and coming back (or a
  // reload) resets it to {} even though an unclosed span from the previous
  // session is still sitting in the loaded data with end_frame=null. Reseed
  // it once that data arrives, or the next O/P press opens a second span
  // instead of closing the first.
  useEffect(() => {
    for (const kind of ['corner_swap', 'excluded'] as const) {
      if (openSpanRef.current[kind] != null) continue;
      const open = spans.find(s => s.kind === kind && s.end_frame == null);
      if (open) openSpanRef.current[kind] = open.id;
    }
  }, [spans]);

  const toggleSpan = async (kind: SpanKind) => {
    if (!fightId) return;
    const openId = openSpanRef.current[kind];
    const frame = frameRef.current;
    if (openId != null) {
      try {
        const start = spans.find(s => s.id === openId)?.frame ?? frame;
        const patch = frame < start ? { frame, end_frame: start } : { end_frame: frame };
        const updated = await updateEvent(fightId, openId, patch);
        setAllEvents(prev => prev.map(s => (s.id === openId ? updated : s)));
        showToast(`${SPAN_LABEL[kind]} span closed`, 'var(--slate-400)', 'flag');
      } catch {
        showToast('Failed to close span', 'var(--f-red)', 'error');
      } finally {
        delete openSpanRef.current[kind];
      }
      return;
    }
    try {
      const created = await createEvent(fightId, {
        kind, frame, value: kind === 'excluded' ? 'replay' : null,
      });
      setAllEvents(prev => [...prev, created]);
      openSpanRef.current[kind] = created.id;
      showToast(`${SPAN_LABEL[kind]} span opened`, 'var(--slate-400)', 'flag');
    } catch {
      showToast('Failed to open span', 'var(--f-red)', 'error');
    }
  };

  const updateSpan = async (spanId: number, patch: { frame?: number; end_frame?: number }) => {
    if (!fightId) return;
    try {
      const updated = await updateEvent(fightId, spanId, patch);
      setAllEvents(prev => prev.map(s => (s.id === spanId ? updated : s)));
    } catch {
      showToast('Failed to update span', 'var(--f-red)', 'error');
    }
  };

  const removeSpan = async (spanId: number) => {
    if (!fightId) return;
    try {
      await deleteEvent(fightId, spanId);
      setAllEvents(prev => prev.filter(s => s.id !== spanId));
      for (const [kind, id] of Object.entries(openSpanRef.current)) {
        if (id === spanId) delete openSpanRef.current[kind as SpanKind];
      }
      if (spans.find(s => s.id === spanId)?.kind === 'round') {
        await renumberRounds(spans.filter(s => s.kind === 'round' && s.id !== spanId));
      }
    } catch {
      showToast('Failed to delete span', 'var(--f-red)', 'error');
    }
  };

  // A round span's `value` is its round number, which eval and export read.
  // Keep it equal to the span's position in time, so adding or deleting a
  // round renumbers the ones after it.
  const renumberRounds = async (roundSpans: Event[]) => {
    if (!fightId) return;
    const stale = [...roundSpans]
      .sort((a, b) => a.frame - b.frame)
      .map((s, i) => ({ s, value: String(i + 1) }))
      .filter(({ s, value }) => s.value !== value);
    const updated = await Promise.all(stale.map(({ s, value }) => updateEvent(fightId, s.id, { value })));
    const byId = new Map(updated.map(u => [u.id, u]));
    setAllEvents(prev => prev.map(e => byId.get(e.id) ?? e));
  };

  // K starts a new round at the playhead. Inside a round span it splits that
  // span there, which is how a fight that segmentation collapsed into one
  // round gets its real rounds back. Outside every round it adds one running
  // up to the next round (or the end of the video). Either way the labeller
  // then drags the edges to cut out the break between rounds.
  const addRound = async () => {
    if (!fightId) return;
    const frame = frameRef.current;
    const roundSpans = spans.filter(s => s.kind === 'round');
    const containing = roundSpans.find(s => s.end_frame != null && s.frame <= frame && frame <= s.end_frame);
    if (containing?.frame === frame) {
      showToast('A round already starts here', 'var(--f-red)', 'error');
      return;
    }
    const nextStart = Math.min(...roundSpans.filter(s => s.frame > frame).map(s => s.frame));
    const end = containing?.end_frame
      ?? (Number.isFinite(nextStart) ? nextStart - 1 : Math.max(frame, Math.floor(duration * fps)));
    setSavingCount(c => c + 1);
    try {
      let next = roundSpans;
      if (containing) {
        const shortened = await updateEvent(fightId, containing.id, { end_frame: frame - 1 });
        next = next.map(s => (s.id === shortened.id ? shortened : s));
        setAllEvents(prev => prev.map(e => (e.id === shortened.id ? shortened : e)));
      }
      const created = await createEvent(fightId, { kind: 'round', frame, end_frame: end });
      setAllEvents(prev => [...prev, created]);
      await renumberRounds([...next, created]);
      showToast(containing ? 'Round split at playhead' : 'Round added', 'var(--green-500)', 'flag');
    } catch {
      showToast('Failed to add round', 'var(--f-red)', 'error');
    } finally {
      setSavingCount(c => c - 1);
    }
  };

  const undo = () => {
    const lastId = sessionIdsRef.current[sessionIdsRef.current.length - 1];
    if (lastId == null) return;
    removeEvent(lastId);
  };

  const logTool = (item: ToolItem, shiftKey = false) => {
    if (!selectedFight) return;
    const corner = selRef.current;
    if (item.needsFighter && !corner) {
      setHint(true);
      clearTimeout(hintTimer.current);
      hintTimer.current = setTimeout(() => setHint(false), 1100);
      showToast('Select a fighter first', 'var(--f-red)', 'error');
      return;
    }
    // Fighter-independent tools (fight state) must not pick up whichever corner
    // happens to be selected — neither in the stored corner nor in the toast.
    const cornerIdx = item.needsFighter ? (corner === 'red' ? 0 : 1) : null;
    const fighterName = item.needsFighter ? (corner === 'red' ? redName : blueName) : '';
    const target = item.hasTarget ? (shiftKey ? 'body' : 'head') : item.fixedTarget ?? null;
    // `description` is only kept as a local for the toast text below — it's
    // no longer sent to the backend. Every action here except fight_end is
    // fully reconstructable from action/target/corner (see describeEvent.ts),
    // so storing a frozen copy would only go stale the next time a
    // corner_swap span is added or edited.
    const description = item.text(fighterName, target ?? undefined);
    const color = colorForAction(item.action);
    const icon = iconForAction(item.action);
    addEvent({
      frame: frameRef.current,
      corner: cornerIdx,
      action: item.action,
      target,
      success: successForAction(item.action),
    }).then(created => {
      if (!created) return;
      if (!item.needsFighter) { showToast(description, color, icon); return; }
      const targetSuffix = item.hasTarget ? ` · ${target === 'body' ? 'Body' : 'Head'}` : '';
      showToast(`${item.name} · ${fighterName}${targetSuffix}`, color, icon);
    });
  };

  const confirmFightEnd = (result: FightEndResult) => {
    const winnerCorner = result.winner === 'red' ? 0 : result.winner === 'blue' ? 1 : null;
    const winnerName = result.winner === 'red' ? redName : result.winner === 'blue' ? blueName : null;
    const outcome = result.method === 'Draw' || !winnerName
      ? 'Draw'
      : result.method === 'Decision' ? `${winnerName} by decision` : `${winnerName} by ${result.method}`;
    const description = `Fight ended — ${outcome}${result.detail ? ' (' + result.detail + ')' : ''}`;
    const endFrame = frameRef.current;
    addEvent({
      frame: endFrame,
      description,
      corner: winnerCorner,
      action: 'fight_end',
      success: null,
    }).then(created => {
      if (!created) return;
      showToast(`Fight ended · ${result.method}`, 'var(--purple-600)', 'sports_score');

      // The round span was seeded from the AI's scheduled-length guess,
      // which now runs past the real end of the fight — auto-exclude the
      // tail so it isn't scored/trained on as if it were live action.
      // Visible and editable in the timeline like any other excluded span,
      // not a silent adjustment (TODO.md #4).
      if (!fightId) return;
      const containingRound = spans.find(
        s => s.kind === 'round' && s.frame <= endFrame &&
             (s.end_frame == null || endFrame <= s.end_frame),
      );
      if (containingRound?.end_frame != null && containingRound.end_frame > endFrame) {
        createEvent(fightId, {
          kind: 'excluded',
          frame: endFrame + 1,
          end_frame: containingRound.end_frame,
          value: 'post fight_end',
        }).then(span => setAllEvents(prev => [...prev, span]));
      }
    });
    setEndOpen(false);
  };

  const handleFinishLabeling = async () => {
    if (!fightId) return;
    setFinishing(true);
    try {
      await finishLabeling(fightId);
      // replace: Back from the Player must not land on this page again, which
      // for a now-finished fight is just the "already labeled" screen.
      navigate(`/fights/${fightId}`, { replace: true });
    } catch (err) {
      showToast(err instanceof Error ? err.message : 'Failed to finish labeling', 'var(--f-red)', 'error');
      setFinishing(false);
    }
  };

  // Same transition the Player's "Edit labels" button makes, for a direct
  // visit to /annotate on a finished fight. Patching the one row in place
  // flips `ready`, so this page re-renders straight into the editor.
  const handleReopenLabeling = async () => {
    if (!fightId) return;
    setReopening(true);
    setReopenError(null);
    try {
      const reopened = await reopenLabeling(fightId);
      setFights(prev => prev.map(f => (f.id === reopened.id ? reopened : f)));
    } catch (err) {
      setReopenError(err instanceof Error ? err.message : 'Failed to open the fight for editing');
    } finally {
      setReopening(false);
    }
  };

  const handleDeleteFight = async () => {
    if (!fightId) return;
    setDeletingFight(true);
    setDeleteError(null);
    try {
      // The DELETE unlinks the file this <video> is streaming — stop playback
      // (and the requestVideoFrameCallback loop) before pulling it out from under us.
      videoRef.current?.pause();
      setIsPlaying(false);
      await deleteFight(fightId);
      // replace: Back must not return to a now-dead /fights/{id}/annotate.
      navigate('/', { replace: true });
    } catch (err) {
      setDeleteError(err instanceof Error ? err.message : 'Failed to delete fight');
      setDeletingFight(false);
    }
  };

  // stable "latest callback" ref so the global keydown listener (registered once)
  // always calls the current render's closures, without re-registering constantly
  const fnsRef = useRef({ togglePlay, stepFrame, logTool, undo, setSelected, toggleSpan, removeEvent, addRound });
  fnsRef.current = { togglePlay, stepFrame, logTool, undo, setSelected, toggleSpan, removeEvent, addRound };

  useEffect(() => {
    if (!ready) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      const target = e.target as HTMLElement;
      const tag = target.tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA' || target.isContentEditable) return;
      // Any modal swallows every shortcut — otherwise z/o/p/digits keep logging
      // label events behind the overlay, and Escape would double-fire.
      if (endOpenRef.current || confirmDeleteRef.current) return;

      const fns = fnsRef.current;
      const k = e.key;
      const time = (frameRef.current - 1) / fpsRef.current;

      if (k === ' ') { e.preventDefault(); fns.togglePlay(); return; }
      if (k === 'ArrowLeft') { e.preventDefault(); handleSeek(Math.max(0, time - (e.shiftKey ? 5 : 1))); return; }
      if (k === 'ArrowRight') { e.preventDefault(); handleSeek(time + (e.shiftKey ? 5 : 1)); return; }
      if (k === ',') { e.preventDefault(); fns.stepFrame(-1); return; }
      if (k === '.') { e.preventDefault(); fns.stepFrame(1); return; }
      if (k === 'Escape') { fns.setSelected(null); setSelectedEventId(null); return; }

      const lk = k.length === 1 ? k.toLowerCase() : k;
      if (lk === 'r') { fns.setSelected('red'); return; }
      if (lk === 'b') { fns.setSelected('blue'); return; }
      // Backspace/Delete: delete the selected timeline clip if one is
      // selected, else undo the last event logged this session. On Mac the
      // one physical "delete" key sends Backspace (e.key === 'Delete' is
      // only the separate forward-delete, Fn+Delete) — so this has to be
      // one binding that branches on selection, not two separate keys.
      if (k === 'Backspace' || k === 'Delete') {
        e.preventDefault();
        if (selectedEventIdRef.current != null) fns.removeEvent(selectedEventIdRef.current);
        else fns.undo();
        return;
      }
      if (lk === 'z') { e.preventDefault(); fns.undo(); return; }
      if (lk === 'o') { e.preventDefault(); fns.toggleSpan('corner_swap'); return; }
      if (lk === 'p') { e.preventDefault(); fns.toggleSpan('excluded'); return; }
      if (lk === 'k') { e.preventDefault(); fns.addRound(); return; }

      // Digit keys need e.code, not e.key: Shift+1 types '!' on a US layout,
      // so reading e.key would break the KEYMAP lookup for the target modifier.
      const toolKey = e.code.startsWith('Digit') ? e.code.slice(5) : lk;
      const tool = KEYMAP[toolKey];
      if (tool) { e.preventDefault(); fns.logTool(tool, e.shiftKey); }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [ready]);

  // ---- guard states ----
  if (selectedFight === null) {
    return (
      <div style={{ display: 'flex', flex: 1, alignItems: 'center', justifyContent: 'center', minHeight: 'calc(100vh - 58px)', padding: 24 }}>
        <span className="material-symbols-outlined" style={{ fontSize: 32, color: 'var(--text-muted)', animation: 'spin 1.5s linear infinite' }}>progress_activity</span>
      </div>
    );
  }

  if (isFightViewable(selectedFight.state)) {
    return (
      <div style={{ display: 'flex', flex: 1, alignItems: 'center', justifyContent: 'center', minHeight: 'calc(100vh - 58px)', padding: 24 }}>
        <div className="glass" style={{ textAlign: 'center', borderRadius: 12, padding: '48px 56px', maxWidth: 420 }}>
          <span className="material-symbols-outlined" style={{ fontSize: 40, color: 'var(--text-primary)', display: 'block', marginBottom: 16 }}>check_circle</span>
          <h2 className="font-display" style={{ fontSize: 24, lineHeight: 1.05, margin: '0 0 10px', color: 'var(--text-primary)' }}>This fight is already labeled</h2>
          <p style={{ fontSize: 14, color: 'var(--text-muted)', margin: '0 0 20px', lineHeight: 1.6 }}>Open it in the Player to review the tagged events.</p>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, justifyContent: 'center' }}>
            <button onClick={() => navigate(`/fights/${selectedFight.id}`)} className="btn-glass" style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '8px 16px', fontSize: 13, fontWeight: 500, whiteSpace: 'nowrap' }}>
              <span className="material-symbols-outlined" style={{ fontSize: 16 }}>play_circle</span>
              Open Player
            </button>
            {isLabelEditable(selectedFight) && (
              <button onClick={handleReopenLabeling} disabled={reopening} className="btn-glass" style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '8px 16px', fontSize: 13, fontWeight: 500, whiteSpace: 'nowrap', cursor: reopening ? 'not-allowed' : 'pointer', opacity: reopening ? 0.6 : 1 }}>
                <span className="material-symbols-outlined" style={{ fontSize: 16 }}>{reopening ? 'progress_activity' : 'edit'}</span>
                Edit labels
              </button>
            )}
          </div>
          {reopenError && (
            <p style={{ fontSize: 12, fontWeight: 500, color: 'var(--red-500)', margin: '14px 0 0' }}>{reopenError}</p>
          )}
        </div>
      </div>
    );
  }

  if (!ready) {
    return (
      <div style={{ display: 'flex', flex: 1, alignItems: 'center', justifyContent: 'center', minHeight: 'calc(100vh - 58px)', padding: 24 }}>
        <div className="glass" style={{ textAlign: 'center', borderRadius: 12, padding: '48px 56px', maxWidth: 420 }}>
          <span className="material-symbols-outlined" style={{ fontSize: 40, color: 'var(--text-muted)', display: 'block', marginBottom: 16, animation: 'spin 1.5s linear infinite' }}>progress_activity</span>
          <h2 className="font-display" style={{ fontSize: 24, lineHeight: 1.05, margin: '0 0 10px', color: 'var(--text-primary)' }}>
            {STATE_LABELS[selectedFight.state] ?? 'Detecting fighters'}
          </h2>
          <p style={{ fontSize: 14, color: 'var(--text-muted)', margin: '0 0 20px', lineHeight: 1.6 }}>
            Fighters are still being detected — labeling opens once that's done.
          </p>
          <button onClick={() => navigate('/')} className="btn-glass" style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '8px 16px', fontSize: 13, fontWeight: 500 }}>
            <span className="material-symbols-outlined" style={{ fontSize: 16 }}>arrow_back</span>
            Back to fights
          </button>
        </div>
      </div>
    );
  }

  return (
    <div style={{ position: 'relative', zIndex: 1, width: '100%', boxSizing: 'border-box', maxWidth: 1560, margin: '0 auto', padding: narrow ? '16px 14px 48px' : '22px 30px 70px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
        <button onClick={() => navigate('/')} className="icon-btn" style={{ width: 38, height: 38 }}>
          <span className="material-symbols-outlined" style={{ fontSize: 20 }}>arrow_back</span>
        </button>
        <div>
          <div className="font-display" style={{ fontSize: 30, color: 'var(--text-primary)', lineHeight: 1 }}>
            {isEditingLabels(selectedFight) ? 'Edit labels' : 'Self-annotate'}
          </div>
          <div style={{ fontSize: 12.5, color: 'var(--text-muted)', fontWeight: 500, marginTop: 3 }}>{redName} vs {blueName}</div>
        </div>
        <FightPurposeBadge purpose={selectedFight.purpose} />
        <span style={{ flex: 1 }} />
        <SaveStatus saving={savingCount > 0} />
        <button
          onClick={handleFinishLabeling}
          disabled={finishing}
          className="btn-primary"
          style={{
            display: 'inline-flex', alignItems: 'center', gap: 8,
            fontWeight: 600, fontSize: 13, padding: '9px 16px',
            cursor: finishing ? 'not-allowed' : 'pointer', opacity: finishing ? 0.5 : 1, fontFamily: 'inherit',
          }}
        >
          <span className="material-symbols-outlined" style={{ fontSize: 18 }}>{finishing ? 'progress_activity' : 'task_alt'}</span>
          Finish labeling
        </button>
        {can('admin') && (
          <button
            onClick={() => { setDeleteError(null); setConfirmDelete(true); }}
            title="Delete this fight"
            style={{
              width: 38, height: 38, flexShrink: 0, display: 'grid', placeItems: 'center',
              borderRadius: 6, border: '1px solid var(--f-red-dim)',
              background: 'rgba(239,68,68,0.08)', color: 'var(--red-500)',
              cursor: 'pointer', fontFamily: 'inherit',
            }}
          >
            <span className="material-symbols-outlined" style={{ fontSize: 20 }}>delete</span>
          </button>
        )}
      </div>

      <ConfirmDialog
        open={confirmDelete}
        title="Delete fight?"
        message={
          <>
            <strong style={{ color: 'var(--text-primary)' }}>{redName} vs {blueName}</strong> will be
            permanently deleted — the source video file, every hand label and span you have annotated
            so far, plus all pipeline predictions, rounds and tracked fighter frames. This cannot be undone.
          </>
        }
        confirmLabel="Delete fight"
        confirmIcon="delete_forever"
        danger
        busy={deletingFight}
        error={deleteError}
        onCancel={() => setConfirmDelete(false)}
        onConfirm={handleDeleteFight}
      />

      {needsRoundReview(selectedFight) && (
        <div style={{
          display: 'flex',
          alignItems: 'flex-start',
          gap: 10,
          marginBottom: 14,
          padding: '11px 14px',
          borderRadius: 6,
          border: '1px solid color-mix(in srgb, var(--warn) 25%, transparent)',
          background: 'color-mix(in srgb, var(--warn) 7%, transparent)',
        }}>
          <span className="material-symbols-outlined" style={{ fontSize: 19, color: 'var(--warn)', flexShrink: 0 }}>
            rule
          </span>
          <div style={{ minWidth: 0 }}>
            <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--warn)', marginBottom: 2 }}>
              Round boundaries are unverified
            </div>
            <div style={{ fontSize: 12.5, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
              {selectedFight.segmentation_review_reason
                ?? 'Segmentation could not confirm these rounds against the scoreboard.'}
              {' '}Check the Rounds lane below and drag the edges before labelling. If a round is missing,
              move the playhead to where it starts and press <span className="kbd">K</span> to split it off.
            </div>
          </div>
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: narrow ? 'minmax(0, 1fr)' : 'minmax(0, 1fr) 460px', gap: 16, alignItems: 'stretch' }}>
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
          <div className="glass" style={{ padding: '18px 18px 20px', borderRadius: 12 }}>
            <div className="label" style={{ marginBottom: 11 }}>Active fighter</div>
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
        spans={spans}
        rounds={rounds}
        duration={duration}
        fps={fps}
        currentFrame={currentFrame}
        onSeek={seekToFrame}
        onSetPlaying={setIsPlaying}
        onDelete={removeEvent}
        onUpdateSpan={updateSpan}
        onDeleteSpan={removeSpan}
        onAddRound={addRound}
        flashId={flashId}
        selectedEventId={selectedEventId}
        onSelectEvent={setSelectedEventId}
        redName={redName}
        blueName={blueName}
        describe={describe}
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
