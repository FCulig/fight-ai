import type { Event } from '../types/Event';
import type { FighterStats } from '../mocks/fightMock';

function emptyStats(): FighterStats {
  return { sig: [0, 0], total: [0, 0], head: 0, body: 0, leg: 0, distance: 0, clinch: 0, ground: 0, td: [0, 0], ctrl: 0, kd: 0, sub: 0, acc: 0 };
}

// Resolves which corner an event belongs to, for EITHER source: predictions
// carry a resolved `fighter_id` (compared against fights.red_fighter_id),
// labels carry a raw `corner` track-slot (0=red/1=blue) directly.
function attributedCorner(e: Event, redFighterId: number | null | undefined): 'red' | 'blue' | null {
  if (e.source === 'prediction') {
    if (e.fighter_id == null) return null;
    return e.fighter_id === redFighterId ? 'red' : 'blue';
  }
  if (e.corner === 0) return 'red';
  if (e.corner === 1) return 'blue';
  return null;
}

// Target region: label rows already carry an explicit `target` (head/body/
// leg) — see taxonomy.ts's logTool(), which populates it even for kicks'
// fixedTarget. Predictions never populate `target`, so it's derived from the
// action string (`{type}_head`/`{type}_body`, or the kick's own name).
function targetFor(e: Event): 'head' | 'body' | 'leg' | null {
  if (e.target === 'head' || e.target === 'body' || e.target === 'leg') return e.target;
  const a = e.action;
  if (!a) return null;
  if (a.endsWith('_head') || a === 'head_kick') return 'head';
  if (a.endsWith('_body') || a === 'middle_kick') return 'body';
  if (a === 'low_kick') return 'leg';
  return null;
}

const CLINCH_ACTIONS = new Set(['clinch_punch', 'clinch_knee']);
const GROUND_ACTIONS = new Set(['ground_punch', 'ground_knee']);

// Landed-vs-missed is only ever recorded on prediction rows (`success`);
// labels defer that judgment entirely (taxonomy.ts: "MVP target is count
// strikes thrown"), so every logged label strike counts as landed here —
// consistent with what the label palette actually tracks.
function isLanded(e: Event): boolean {
  if (e.source === 'label') return true;
  if (CLINCH_ACTIONS.has(e.action ?? '') || GROUND_ACTIONS.has(e.action ?? '')) return true;
  return e.success === true;
}

function isStrikeAction(action: string | null): boolean {
  if (!action) return false;
  if (action.startsWith('round_') || action.startsWith('state_')) return false;
  if (action === 'takedown_initiated' || action === 'clinch_initiated') return false;
  if (action.startsWith('takedown_') || action === 'submission_attempt' || action === 'fight_end') return false;
  return true; // jab/cross/hook/uppercut(_head|_body)?, kicks, clinch_*/ground_*, elbow, knockdown
}

// Aggregates events with startFrame <= e.frame <= endFrame. Used for "Whole Fight"
// (0..Infinity), a single round (round.start_frame..round.end_frame), and "Live"
// (0..currentFrame, via deriveLiveStats above).
export function deriveStatsForRange(
  events: Event[],
  startFrame: number,
  endFrame: number,
  fps: number,
  redFighterId?: number | null,
): { red: FighterStats; blue: FighterStats } {
  const red = emptyStats();
  const blue = emptyStats();

  // Track GROUND state intervals to compute control time per fighter.
  // initiator = the fighter who took down the opponent (they control).
  // Prediction-only: `state`/`takedown_initiated`/`clinch_initiated` have no
  // label-side equivalent correlating a state span back to its initiator.
  let groundStart: number | null = null;
  let groundInitiator: 'red' | 'blue' | null = null;

  const filtered = events.filter(e => e.frame >= startFrame && e.frame <= endFrame);

  for (const e of filtered) {
    if (e.action === 'round_start' || e.action === 'round_end') continue;

    if (e.source === 'prediction' && e.state) {
      const isGround = e.state === 'GROUND';
      if (isGround && groundStart === null) {
        groundStart = e.frame;
        groundInitiator = attributedCorner(e, redFighterId);
      } else if (!isGround && groundStart !== null) {
        const seconds = (e.frame - groundStart) / fps;
        if (groundInitiator === 'red') red.ctrl += seconds;
        else if (groundInitiator === 'blue') blue.ctrl += seconds;
        groundStart = null;
        groundInitiator = null;
      }
      if (e.action === 'takedown_initiated') {
        const corner = attributedCorner(e, redFighterId);
        const initiator = corner === 'red' ? red : corner === 'blue' ? blue : null;
        if (initiator) {
          initiator.td[0] += 1;
          initiator.td[1] += 1;
        }
      }
      continue;
    }

    if (!isStrikeAction(e.action)) continue;
    const corner = attributedCorner(e, redFighterId);
    if (!corner) continue;
    const st = corner === 'red' ? red : blue;
    const action = e.action as string;

    const isClinch = CLINCH_ACTIONS.has(action);
    const isGroundStrike = GROUND_ACTIONS.has(action);
    const isOpenRange = !isClinch && !isGroundStrike;
    const landed = isLanded(e);

    st.sig[1] += 1;
    st.total[1] += 1;

    if (landed) {
      st.sig[0] += 1;
      st.total[0] += 1;

      if (isClinch) st.clinch += 1;
      else if (isGroundStrike) st.ground += 1;
      else st.distance += 1;

      if (isOpenRange) {
        const target = targetFor(e);
        if (target === 'head') st.head += 1;
        else if (target === 'body') st.body += 1;
        else if (target === 'leg') st.leg += 1;
      }
    }

    if (action === 'knockdown') st.kd += 1;
    if (action === 'submission_attempt') st.sub += 1;
  }

  // If still in GROUND state at endFrame, credit elapsed ctrl up to there.
  // endFrame may be Infinity (whole-fight scope) — cap at the last real event
  // frame so an unclosed ground state doesn't produce infinite control time.
  if (groundStart !== null && groundInitiator !== null) {
    const cap = Number.isFinite(endFrame) ? endFrame : filtered[filtered.length - 1]?.frame ?? groundStart;
    const seconds = (cap - groundStart) / fps;
    if (groundInitiator === 'red') red.ctrl += seconds;
    else blue.ctrl += seconds;
  }

  // Accuracy
  red.acc  = red.sig[1]  > 0 ? Math.round((red.sig[0]  / red.sig[1])  * 100) : 0;
  blue.acc = blue.sig[1] > 0 ? Math.round((blue.sig[0] / blue.sig[1]) * 100) : 0;

  // ctrl: round to nearest second
  red.ctrl  = Math.round(red.ctrl);
  blue.ctrl = Math.round(blue.ctrl);

  return { red, blue };
}

export function deriveLiveStats(
  events: Event[],
  currentFrame: number,
  fps: number,
  redFighterId?: number | null,
): { red: FighterStats; blue: FighterStats } {
  return deriveStatsForRange(events, 0, currentFrame, fps, redFighterId);
}

// Buckets significant strikes landed per fighter into bucketSeconds-wide windows,
// for the MOMENTUM pace chart. durationSeconds sizes the bucket array even past
// the last event (e.g. while the fight is still being reviewed).
export function derivePaceBuckets(
  events: Event[],
  fps: number,
  durationSeconds: number,
  redFighterId?: number | null,
  bucketSeconds = 30,
): { red: number[]; blue: number[] } {
  const lastEventSeconds = events.reduce((max, e) => Math.max(max, e.frame / fps), 0);
  const totalSeconds = Math.max(durationSeconds, lastEventSeconds);
  const bucketCount = Math.max(2, Math.ceil(totalSeconds / bucketSeconds));

  const red = new Array<number>(bucketCount).fill(0);
  const blue = new Array<number>(bucketCount).fill(0);

  for (const e of events) {
    if (!isStrikeAction(e.action) || !isLanded(e)) continue;
    const corner = attributedCorner(e, redFighterId);
    if (!corner) continue;

    const bucket = Math.min(bucketCount - 1, Math.floor(e.frame / fps / bucketSeconds));
    (corner === 'red' ? red : blue)[bucket] += 1;
  }

  return { red, blue };
}
