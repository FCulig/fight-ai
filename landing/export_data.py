"""Writes landing/app/data.js from the fight-ai database. Run from the repo root:
    ai/.venv/bin/python landing/export_data.py
"""
import os, json, psycopg2
from dotenv import load_dotenv
load_dotenv('backend/.env')
c = psycopg2.connect(os.environ['DATABASE_URL']); cur = c.cursor()
OUT = 'landing/app/data.js'

# --- exchange: fight 52, 50 fps, sampled every 2nd frame = 25 Hz (the strike model's rate)
FID, START, END, STEP = 52, 38606, 38826, 2
cur.execute("select fps from fights where id=%s", (FID,)); fps = cur.fetchone()[0]
cur.execute("select frame, corner, x1,y1,x2,y2, keypoints, confidence from fighter_frames where fight_id=%s and frame between %s and %s", (FID, START, END))
by = {}
for fr, co, x1, y1, x2, y2, k, bc in cur.fetchall():
    by[(fr, co)] = (x1, y1, x2, y2, k, bc)
frames = list(range(START, END + 1, STEP))
xs, ys = [], []
tracks = [[], []]
for fr in frames:
    for co in (0, 1):
        v = by.get((fr, co)) or by.get((fr + 1, co)) or by.get((fr - 1, co))
        if not v or not v[4]:
            tracks[co].append(None); continue
        x1, y1, x2, y2, k, bc = v
        row = [round(x1), round(y1), round(x2), round(y2), min(99, int((bc or 0) * 100))]
        for x, y, cf in k:
            row += [round(x), round(y), min(99, int(cf * 100))]
        tracks[co].append(row)
        xs += [x1, x2]; ys += [y1, y2]
cur.execute("""select frame, corner, action, target from fight_events where fight_id=%s and source='label' and kind='point'
  and is_verified is true and frame between %s and %s order by frame""", (FID, START, END))
events = [dict(f=f, c=co, a=a, t=t) for f, co, a, t in cur.fetchall()]
exchange = dict(fps=fps, start=START, step=STEP, box=[round(min(xs)), round(min(ys)), round(max(xs)), round(max(ys))], red=tracks[0], blue=tracks[1], events=events)

# --- whole fight: fight 62 (ai_labeled) pipeline output
FID2 = 62
cur.execute("select fps, red_fighter_id, blue_fighter_id, decoded_frames from fights where id=%s", (FID2,))
fps2, red_id, blue_id, total = cur.fetchone()
cur.execute("select round_number, start_frame, end_frame from rounds where fight_id=%s order by round_number", (FID2,))
rounds = [list(r) for r in cur.fetchall()]
cur.execute("""select frame, fighter_id, action, success from fight_events where fight_id=%s and source='prediction' and kind='point'
  and action is not null and action not like 'round%%' order by frame""", (FID2,))
strikes = []
for f, fid, a, s in cur.fetchall():
    co = 0 if fid == red_id else 1 if fid == blue_id else None
    if co is None: continue
    strikes.append([f, co, a, None if s is None else int(s)])
fight = dict(fps=fps2, frames=total, rounds=rounds, strikes=strikes)

with open(OUT, 'w') as fh:
    fh.write('// Generated from the fight-ai database. Real data, no video.\n')
    fh.write(f'// EXCHANGE: fight {FID} frames {START}-{END}, both corners: box [x1, y1, x2, y2, conf*100] + 17 keypoints [x, y, conf*100],\n')
    fh.write(f'//   sampled every {STEP} frames (25 Hz), with the verified hand-labelled strikes in that span.\n')
    fh.write(f'// FIGHT: fight {FID2} (ai_labeled) pipeline predictions: rounds and strikes [frame, corner, action, landed].\n')
    fh.write('window.EXCHANGE = ' + json.dumps(exchange, separators=(',', ':')) + ';\n')
    fh.write('window.FIGHT = ' + json.dumps(fight, separators=(',', ':')) + ';\n')
print(f'{OUT}: {len(frames)} samples, {len(events)} strikes in the exchange, {len(strikes)} strikes in the fight')
