// Generates the screens' API fixtures from scratch: invented fighters, fights,
// labels, predictions, eval runs and users, shaped like the real API (see
// frontend/src/types and services/api.ts) but containing no real data. Seeded,
// so rebuilds are stable. Keypoints aren't stored: harness.ts draws them.
// Run from the repo root: node .design-sync/screens/synth.mjs
import { mkdirSync, writeFileSync } from 'node:fs';

let seed = 20261018;
const rnd = () => {
  seed |= 0; seed = (seed + 0x6d2b79f5) | 0;
  let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
  t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
  return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
};
const int = (a, b) => a + Math.floor(rnd() * (b - a + 1));
const pick = arr => arr[Math.floor(rnd() * arr.length)];
const weighted = pairs => {
  let r = rnd() * pairs.reduce((s, [, w]) => s + w, 0);
  for (const [v, w] of pairs) if ((r -= w) <= 0) return v;
  return pairs[0][0];
};
const iso = (day, h = 10, m = 0) => new Date(Date.UTC(2026, 7, 1 + day, h, m, int(0, 59))).toISOString().replace('Z', '');

// ── Fighters and fights (ids match the screen routes in screens.config.mjs) ──
const FIGHTERS = [
  [101, 'Marko Vidovic'], [102, 'Tomas Albrecht'], [103, 'Rafael Monteiro'], [104, 'Kenji Arai'],
  [105, 'Luka Brandt'], [106, 'Oskar Lindqvist'], [107, 'Dario Pecek'], [108, 'Samir Haddad'],
  [109, 'Nikola Ferenc'], [110, 'Jonah Whitfield'], [111, 'Adrian Kos'], [112, 'Mateo Ruiz'],
  [113, 'Ivo Stanic'], [114, 'Cole Harrington'],
];
const nameOf = id => FIGHTERS.find(f => f[0] === id)[1];

// [id, purpose, state, red, blue, fps, w, h, rounds, lastRoundSecs, addedDay, labeled]
const FIGHT_SPECS = [
  [42, 'training_data', 'labeling_complete', 101, 102, 50, 1280, 720, 1, 170, 14, true],
  [44, 'training_data', 'labeling_complete', 103, 104, 50, 1280, 720, 2, 95, 14, true],
  [52, 'training_data', 'labeling_complete', 105, 106, 50, 1280, 720, 3, 300, 21, true],
  [54, 'training_data', 'labeling_complete', 107, 108, 24, 1280, 720, 5, 300, 22, true],
  [58, 'training_data', 'labeling_complete', 109, 110, 50, 1280, 720, 1, 140, 42, true],
  [60, 'reference', 'labeling_complete', 111, 112, 50, 1920, 1080, 3, 300, 42, true],
  [62, 'ai_labeled', 'completed', 111, 112, 50, 1920, 1080, 3, 300, 43, false],
  [65, 'ai_labeled', 'completed', 111, 112, 50, 1920, 1080, 3, 300, 56, false],
  [68, 'training_data', 'labeling_in_progress', 113, 114, 25, 1920, 1080, 3, 160, 70, false],
];

const ROUND_SECS = 300, BREAK_SECS = 60, LEAD_IN = 20, TAIL = 25;
const fights = [], roundsBy = {};
for (const [id, purpose, state, red, blue, fps, width, height, n, last, day, labeled] of FIGHT_SPECS) {
  const rounds = [];
  let t = LEAD_IN;
  for (let r = 1; r <= n; r++) {
    const len = r === n ? last : ROUND_SECS;
    rounds.push({ id: id * 10 + r, fight_id: id, round_number: r, start_frame: Math.floor(t * fps) + 1, end_frame: Math.floor((t + len) * fps) });
    t += len + BREAK_SECS;
  }
  const frames = rounds.at(-1).end_frame + TAIL * fps;
  roundsBy[id] = rounds;
  fights.push({
    id, video_path: `fight_videos/${nameOf(red).split(' ')[1].toUpperCase()}vs${nameOf(blue).split(' ')[1].toUpperCase()}.mp4`,
    fps, width, height, created_at: iso(day), state, labeled_at: labeled ? iso(day + 1, 18) : null, purpose,
    reported_frames: frames, decoded_frames: frames, segmentation_needs_review: false, segmentation_review_reason: null,
    red_fighter_id: red, blue_fighter_id: blue, red_fighter_name: nameOf(red), blue_fighter_name: nameOf(blue), uploaded_by: null,
  });
}
const fightById = Object.fromEntries(fights.map(f => [f.id, f]));

// ── Events ──
const LABEL_STRIKES = [
  ['jab', 30, true], ['cross', 13, true], ['left_hook', 10, true], ['right_hook', 10, true],
  ['left_uppercut', 2, true], ['right_uppercut', 3, true], ['calf_kick', 3, 'leg'], ['low_kick', 2, 'leg'],
  ['middle_kick', 3, 'body'], ['high_kick', 1, 'head'], ['clinch_punch', 2, null], ['ground_punch', 4, null],
  ['ground_knee', 1, null], ['knee', 1, null], ['takedown_attempt', 2, null], ['takedown_landed', 1, null],
  ['takedown_defended', 1, null], ['submission_attempt', 0.5, null], ['knockdown', 0.3, null],
];
const PRED_STRIKES = [['jab_head', 40], ['hook_head', 20], ['cross_head', 12], ['jab_body', 7], ['middle_kick', 6],
  ['uppercut_head', 4], ['head_kick', 2], ['uppercut_body', 1], ['low_kick', 1], ['clinch_knee', 1]];

let eventId = 3000;
const base = (fight, source, kind, frame, over = {}) => ({
  id: eventId++, fight_id: fight.id, source, kind, frame, end_frame: null, description: null, fighter_id: null,
  corner: null, action: null, target: null, success: null, state: null, value: null, labeler: null,
  created_at: fight.created_at, is_verified: null, ...over,
});

const eventsBy = {};
function labelEvents(fight, { complete }) {
  const out = [], rounds = roundsBy[fight.id], fps = fight.fps;
  const verify = fight.purpose === 'training_data';
  const last = complete ? rounds.at(-1) : rounds[0];
  for (const r of rounds) out.push(base(fight, 'label', 'round', r.start_frame, { end_frame: r.end_frame, value: String(r.round_number) }));
  for (const r of complete ? rounds : rounds.slice(0, 1)) {
    out.push(base(fight, 'label', 'point', r.start_frame, { action: 'state_striking' }));
    if (!complete) { out.push(base(fight, 'label', 'point', r.start_frame + Math.floor((r.end_frame - r.start_frame) * 0.88), { action: 'state_clinch' })); continue; }
    let f = r.start_frame + int(2, 6) * fps, inGround = false;
    while (f < r.end_frame - fps) {
      if (rnd() < 0.025) {
        const st = inGround ? 'state_striking' : pick(['state_clinch', 'state_ground']);
        inGround = st === 'state_ground';
        out.push(base(fight, 'label', 'point', f, { action: st }));
      } else {
        const [action, , tgt] = weighted(LABEL_STRIKES.map(s => [s, s[1]]));
        const target = tgt === true ? (rnd() < 0.82 ? 'head' : 'body') : typeof tgt === 'string' ? tgt : null;
        const verdict = verify ? weighted([[true, 78], [false, 9], [null, 13]]) : null;
        out.push(base(fight, 'label', 'point', f, {
          corner: rnd() < 0.5 ? 0 : 1, action, target, is_verified: verdict,
          success: action === 'knockdown' || action === 'takedown_landed' ? true : null,
        }));
      }
      f += Math.floor(fps * (2 + rnd() * 9));
    }
    if (rnd() < 0.4) {
      const s = r.start_frame + int(30, 200) * fps;
      out.push(base(fight, 'label', 'corner_swap', s, { end_frame: s + int(3, 12) * fps }));
    }
  }
  if (complete) {
    const end = last.end_frame;
    out.push(base(fight, 'label', 'point', end, { corner: 0, action: 'fight_end', description: `Fight ended — ${fight.red_fighter_name} by decision` }));
    out.push(base(fight, 'label', 'excluded', end + 1, { end_frame: end + fight.fps * 10, value: 'post fight_end' }));
  }
  return out.sort((a, b) => a.frame - b.frame);
}

function predictionEvents(fight) {
  const out = [], fps = fight.fps;
  for (const r of roundsBy[fight.id]) {
    out.push(base(fight, 'prediction', 'point', r.start_frame, { action: 'round_start' }));
    let f = r.start_frame + int(3, 8) * fps;
    while (f < r.end_frame - fps) {
      const red = rnd() < 0.5;
      out.push(base(fight, 'prediction', 'point', f, {
        fighter_id: red ? fight.red_fighter_id : fight.blue_fighter_id,
        action: weighted(PRED_STRIKES), success: weighted([[true, 30], [false, 35], [null, 35]]),
      }));
      f += Math.floor(fps * (1.5 + rnd() * 9));
    }
    out.push(base(fight, 'prediction', 'point', r.end_frame, { action: 'round_end' }));
  }
  return out;
}

for (const f of fights) {
  const labels = f.purpose === 'ai_labeled' ? [] : labelEvents(f, { complete: f.state === 'labeling_complete' });
  eventsBy[f.id] = [...labels, ...(f.purpose === 'ai_labeled' ? predictionEvents(f) : [])];
}

// The Training Data review screen opens /training-data/jab/<this id>: a pending jab.
const reviewJab = eventsBy[54].find(e => e.action === 'jab' && e.is_verified === null);

// ── Eval runs (reference 60 scored against ai_labeled 62 then 65) ──
const SHA = () => Array.from({ length: 40 }, () => '0123456789abcdef'[int(0, 15)]).join('');
const summary = (id, version, scored, f1, p, r, tp, fp, fn, day) => ({
  id, reference_fight_id: 60, scored_fight_id: scored, pipeline_version: version, git_sha: SHA(), constants_sha256: SHA() + SHA().slice(0, 24),
  tolerance_secs: 0.25, tolerance_frames: 12, scored_minutes: 15.2, generated_at: iso(day, 11), triggered_by: null,
  f1, precision: p, recall: r, tp, fp, fn, offset_bias_frames: tp ? int(-2, 2) : null, offset_jitter_frames: tp ? int(2, 5) : null,
});
const runs = [
  summary(1, 1, 62, 0, 0, 0, 0, 0, 241, 44),
  summary(2, 1, 62, 31.4, 38.2, 26.6, 64, 104, 177, 47),
  summary(3, 1, 62, 44.9, 46.1, 43.6, 105, 123, 136, 51),
  summary(7, 2, 65, 58.7, 52.3, 66.8, 161, 147, 80, 57),
];
const FAM = ['jab', 'cross', 'hook', 'uppercut', 'kick', 'knee'];
const confusion = {};
for (const t of FAM) for (const p of FAM) { const n = t === p ? int(6, 48) : rnd() < 0.45 ? int(1, 9) : 0; if (n) confusion[`${t}>${p}`] = n; }
const latest = runs.at(-1);
const strikeItem = (withAction) => {
  const family = pick(FAM), target = family === 'kick' ? pick(['head', 'body', 'leg']) : pick(['head', 'head', 'body']);
  return { frame: int(1100, 45000), fighter: pick(['red', 'blue']), family, target, landed: withAction ? pick([true, false]) : null,
    ...(withAction ? { action: `${family}_${target}` } : {}) };
};
const runDetail = {
  ...latest,
  report: {
    video: fightById[65].video_path, fps: 50, scored_minutes: latest.scored_minutes,
    strikes: {
      detection: { tp: latest.tp, fp: latest.fp, fn: latest.fn }, tolerance_frames: 12,
      fighter_correct: 139, fighter_total: 161, family_correct: 92, family_total: 158, target_correct: 133, target_total: 158,
      landed_correct: 0, landed_total: 0, nonspecific_matches: 3, family_confusion: confusion,
      matched_offsets: Array.from({ length: latest.tp }, () => Math.round((rnd() + rnd() + rnd() - 1.5) * 8)),
      missed: Array.from({ length: latest.fn }, () => strikeItem(false)).sort((a, b) => a.frame - b.frame),
      spurious: Array.from({ length: latest.fp }, () => strikeItem(true)).sort((a, b) => a.frame - b.frame),
    },
    state: {
      frames_scored: 45600, frames_correct: 40210, confusion: { 'STRIKING>STRIKING': 38900, 'STRIKING>CLINCH': 2100, 'CLINCH>CLINCH': 1310, 'CLINCH>STRIKING': 1650, 'GROUND>GROUND': 0, 'CLINCH>GROUND': 140 },
      gt_transitions_per_min: 0.9, pred_transitions_per_min: 2.4, gt_median_dwell_secs: 41.5, pred_median_dwell_secs: 14.2,
    },
    rounds: { matched: [[1, 0.97, 0.4, -0.6, false], [2, 0.95, 1.1, -0.2, false], [3, 0.92, -0.8, 1.4, true]], gt_count: 3, pred_count: 3 },
  },
};

// ── Users ──
const me = { id: 3, email: 'dev-admin@fightai.local', name: 'Dev admin', role: 'admin', is_active: true, created_at: iso(61), last_login_at: iso(78, 9, 30) };
const users = [
  me,
  { id: 4, email: 'dev-labeller@fightai.local', name: 'Dev labeller', role: 'labeller', is_active: true, created_at: iso(61), last_login_at: iso(78, 9, 34) },
  { id: 1, email: 'coach@example.com', name: 'Head coach', role: 'admin', is_active: true, created_at: iso(30), last_login_at: iso(77, 18, 2) },
  { id: 5, email: 'analyst@example.com', name: 'Video analyst', role: 'labeller', is_active: true, created_at: iso(48), last_login_at: iso(76, 14, 41) },
  { id: 6, email: 'guest@example.com', name: 'Guest viewer', role: 'viewer', is_active: false, created_at: iso(55), last_login_at: iso(60, 8, 12) },
];
const waitlist = [
  { id: 1, email: 'gym.owner@example.com', created_at: iso(76, 8, 59) },
  { id: 2, email: 'judge@example.org', created_at: iso(77, 13, 1) },
  { id: 3, email: 'fan@example.net', created_at: iso(78, 7, 15) },
];

// ── Fixture map: exact request path + query → response ──
const fixtures = {};
const put = (key, body, status = 200) => { fixtures[key] = { status, body }; };
put('/api/auth/me', me);
put('/api/fights/', fights);
put('/api/users/', users);
put('/api/users/waitlist', waitlist);
put('/api/eval-runs/fixtures', [{ reference_fight_id: 60, video_path: fightById[60].video_path, labeled_at: fightById[60].labeled_at, is_measurable: true, latest_run: latest }]);
put('/api/eval-runs/?reference_fight_id=60', runs);
for (const r of runs) put(`/api/eval-runs/${r.id}`, r.id === latest.id ? runDetail : { ...r, report: runDetail.report });
for (const f of fights) {
  put(`/api/fights/${f.id}`, f);
  put(`/api/fights/${f.id}/rounds/`, roundsBy[f.id]);
  const ev = eventsBy[f.id];
  for (const source of ['label', 'prediction']) {
    const bySource = ev.filter(e => e.source === source);
    put(`/api/fights/${f.id}/events/?source=${source}`, bySource);
    for (const kind of ['point', 'round', 'corner_swap', 'excluded']) put(`/api/fights/${f.id}/events/?source=${source}&kind=${kind}`, bySource.filter(e => e.kind === kind));
  }
  put(`/api/fights/${f.id}/events/`, ev);
}

const out = new URL('../.cache/screens/', import.meta.url);
mkdirSync(out, { recursive: true });
writeFileSync(new URL('fixtures.json', out), JSON.stringify(fixtures));
writeFileSync(new URL('synth-meta.json', out), JSON.stringify({ reviewJabId: reviewJab.id }));
console.log(`${Object.keys(fixtures).length} synthetic responses, review jab #${reviewJab.id} → .design-sync/.cache/screens/fixtures.json`);
