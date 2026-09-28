import type { FighterStats } from '../../mocks/fightMock';

interface Tile {
  value: string;
  unit?: string;
  label: string;
  note: string;
}

function TileCard({ value, unit, label, note }: Tile) {
  return (
    <div className="glass" style={{ padding: '20px 20px 18px', display: 'flex', flexDirection: 'column', gap: 8 }}>
      <div className="font-display" style={{ fontSize: 'clamp(40px, 4.4vw, 56px)', lineHeight: 0.92, color: 'var(--text-primary)' }}>
        {value}{unit && <small style={{ fontSize: '.34em', letterSpacing: '-0.03em', color: 'var(--accent)', marginLeft: '.08em' }}>{unit}</small>}
      </div>
      <div style={{ fontSize: 13.5, fontWeight: 700, color: 'var(--text-primary)' }}>{label}</div>
      <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-muted)', lineHeight: 1.4 }}>{note}</div>
    </div>
  );
}

interface SummaryTilesProps {
  red: FighterStats;
  blue: FighterStats;
  redName: string;
  blueName: string;
  scopeLabel: string;
}

/** The design's four "Report" hero tiles — every number here is a plain sum
 * or ratio over the same real per-fighter FighterStats FighterColumn already
 * renders (see utils/liveStats.ts deriveStatsForRange); nothing new is
 * fetched or fabricated. */
export default function SummaryTiles({ red, blue, redName, blueName, scopeLabel }: SummaryTilesProps) {
  const sigLanded = red.sig[0] + blue.sig[0];
  const sigAttempted = red.sig[1] + blue.sig[1];
  const combinedAcc = sigAttempted > 0 ? Math.round((sigLanded / sigAttempted) * 100) : 0;
  const ctrlTotal = red.ctrl + blue.ctrl;
  const ctrlLeaderName = red.ctrl >= blue.ctrl ? redName : blueName;
  const ctrlLeaderShare = ctrlTotal > 0 ? Math.round((Math.max(red.ctrl, blue.ctrl) / ctrlTotal) * 100) : 0;
  const kdTotal = red.kd + blue.kd;
  const kdByName = red.kd > blue.kd ? redName : blueName;

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 12 }}>
      <TileCard
        value={String(sigLanded)}
        label="Significant strikes"
        note={`${redName} ${red.sig[0]} · ${blueName} ${blue.sig[0]} in ${scopeLabel}`}
      />
      <TileCard
        value={String(combinedAcc)}
        unit="%"
        label="Combined accuracy"
        note={`${sigAttempted} significant attempts thrown`}
      />
      <TileCard
        value={(ctrlTotal / 60).toFixed(1)}
        unit="min"
        label="Control time"
        note={ctrlTotal > 0 ? `${ctrlLeaderName} held ${ctrlLeaderShare}% of it` : 'No ground control recorded'}
      />
      <TileCard
        value={String(kdTotal)}
        label="Knockdowns"
        note={kdTotal > 0 ? `${kdByName} scored ${kdTotal === 1 ? 'a' : kdTotal} knockdown${kdTotal === 1 ? '' : 's'}` : 'Nobody touched the canvas'}
      />
    </div>
  );
}
