import type { Event } from '../types/Event';
import type { FighterStats } from '../mocks/fightMock';

function emptyStats(): FighterStats {
  return { sig: [0, 0], total: [0, 0], head: 0, body: 0, leg: 0, distance: 0, clinch: 0, ground: 0, td: [0, 0], ctrl: 0, kd: 0, sub: 0, acc: 0 };
}

export function deriveLiveStats(
  events: Event[],
  currentFrame: number,
  fps: number,
): { red: FighterStats; blue: FighterStats } {
  return deriveStatsForRange(events, 0, currentFrame, fps);
}

// Aggregates events with startFrame <= e.frame <= endFrame. Used for "Whole Fight"
// (0..Infinity), a single round (round.start_frame..round.end_frame), and "Live"
// (0..currentFrame, via deriveLiveStats above).
export function deriveStatsForRange(
  events: Event[],
  startFrame: number,
  endFrame: number,
  fps: number,
): { red: FighterStats; blue: FighterStats } {
  const red = emptyStats();
  const blue = emptyStats();

  // Track GROUND state intervals to compute control time per fighter.
  // initiator = the fighter who took down the opponent (they control).
  let groundStart: number | null = null;
  let groundInitiator: 'red' | 'blue' | null = null;

  const filtered = events.filter(e => e.frame >= startFrame && e.frame <= endFrame);

  for (const e of filtered) {
    const desc = e.description;

    // ── Round boundaries: skip ──────────────────────────────────────
    if (/^Round \d+ (started|ended)$/i.test(desc)) continue;

    // ── Fight state changes ─────────────────────────────────────────
    if (/^Fight state changed to/i.test(desc)) {
      const isGround = /FightState\.GROUND/i.test(desc);

      if (isGround && groundStart === null) {
        groundStart = e.frame;
        const m = desc.match(/takedown initiated by (fighter_red|fighter_blue)/i);
        groundInitiator = m ? (m[1].toLowerCase().includes('red') ? 'red' : 'blue') : null;
      } else if (!isGround && groundStart !== null) {
        // State leaving GROUND — credit ctrl time to the initiator
        const seconds = (e.frame - groundStart) / fps;
        if (groundInitiator === 'red') red.ctrl += seconds;
        else if (groundInitiator === 'blue') blue.ctrl += seconds;
        groundStart = null;
        groundInitiator = null;

        // Takedown credit: already counted when we detected the takedown event below
      }

      // Count takedown attempts/landed from state transition descriptions
      const tdM = desc.match(/takedown initiated by (fighter_red|fighter_blue)/i);
      if (tdM) {
        const initiator = tdM[1].toLowerCase().includes('red') ? red : blue;
        initiator.td[0] += 1; // landed (state changed = takedown succeeded)
        initiator.td[1] += 1; // attempted
      }
      continue;
    }

    // ── Strike events ───────────────────────────────────────────────
    // Pattern: "fighter_red threw a jab_head (landed)"
    //          "fighter_blue threw a clinch_punch"
    const strikeM = desc.match(/^(fighter_red|fighter_blue) threw a (\S+?)(?:\s+\((landed|missed|unconfirmed)\))?$/i);
    if (!strikeM) continue;

    const isRed = strikeM[1].toLowerCase() === 'fighter_red';
    const st = isRed ? red : blue;
    const strikeType = strikeM[2].toLowerCase(); // e.g. "jab_head", "clinch_punch", "low_kick"
    const outcome = strikeM[3]?.toLowerCase() ?? null; // "landed" | "missed" | "unconfirmed" | null (clinch/ground)

    // Open-range strikes have an outcome suffix; clinch/ground strikes don't
    const isOpenRange = outcome !== null;
    const isClinch = strikeType.startsWith('clinch_');
    const isGround = strikeType.startsWith('ground_');

    // Attempted = every throw
    st.sig[1] += 1;
    st.total[1] += 1;

    // Landed = open-range explicit landed, or clinch/ground (always counted as landed)
    const landed = outcome === 'landed' || isClinch || isGround;
    if (landed) {
      st.sig[0] += 1;
      st.total[0] += 1;
    }

    // Position breakdown (only for landed)
    if (landed) {
      if (isClinch) st.clinch += 1;
      else if (isGround) st.ground += 1;
      else st.distance += 1;
    }

    // Target breakdown (only for landed open-range strikes)
    if (landed && isOpenRange) {
      if (strikeType.endsWith('_head') || strikeType === 'head_kick') st.head += 1;
      else if (strikeType.endsWith('_body') || strikeType === 'middle_kick') st.body += 1;
      else if (strikeType === 'low_kick') st.leg += 1;
    }
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

const STRIKE_RE = /^(fighter_red|fighter_blue) threw a (\S+?)(?:\s+\((landed|missed|unconfirmed)\))?$/i;

// Buckets significant strikes landed per fighter into bucketSeconds-wide windows,
// for the MOMENTUM pace chart. durationSeconds sizes the bucket array even past
// the last event (e.g. while the fight is still being reviewed).
export function derivePaceBuckets(
  events: Event[],
  fps: number,
  durationSeconds: number,
  bucketSeconds = 30,
): { red: number[]; blue: number[] } {
  const lastEventSeconds = events.reduce((max, e) => Math.max(max, e.frame / fps), 0);
  const totalSeconds = Math.max(durationSeconds, lastEventSeconds);
  const bucketCount = Math.max(2, Math.ceil(totalSeconds / bucketSeconds));

  const red = new Array<number>(bucketCount).fill(0);
  const blue = new Array<number>(bucketCount).fill(0);

  for (const e of events) {
    const m = e.description.match(STRIKE_RE);
    if (!m) continue;

    const strikeType = m[2].toLowerCase();
    const outcome = m[3]?.toLowerCase() ?? null;
    const landed = outcome === 'landed' || strikeType.startsWith('clinch_') || strikeType.startsWith('ground_');
    if (!landed) continue;

    const bucket = Math.min(bucketCount - 1, Math.floor(e.frame / fps / bucketSeconds));
    const arr = m[1].toLowerCase() === 'fighter_red' ? red : blue;
    arr[bucket] += 1;
  }

  return { red, blue };
}
