import { useState } from 'react';

const END_METHODS = ['KO/TKO', 'Submission', 'Decision', 'Draw', 'DQ'];

export interface FightEndResult {
  method: string;
  winner: 'red' | 'blue' | 'none';
  detail: string;
}

interface WinnerBtnProps {
  selected: boolean;
  disabled: boolean;
  onClick: () => void;
  label: string;
  color?: string;
}

function WinnerBtn({ selected, disabled, onClick, label, color }: WinnerBtnProps) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      style={{
        flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 7,
        padding: '10px 8px', borderRadius: 9, cursor: disabled ? 'not-allowed' : 'pointer',
        border: `1.5px solid ${selected ? (color ?? 'var(--accent)') : 'var(--border-glass)'}`,
        background: selected ? `color-mix(in srgb, ${color ?? 'var(--accent)'} 14%, transparent)` : 'var(--surface-inner)',
        opacity: disabled ? 0.35 : 1, transition: 'all .12s', fontFamily: 'inherit',
      }}
    >
      {color && <span style={{ width: 9, height: 9, borderRadius: 2, background: color }} />}
      <span style={{ fontSize: 12.5, fontWeight: 700, color: 'var(--text-primary)' }}>{label}</span>
    </button>
  );
}

interface FightEndModalProps {
  currentRound: number | string;
  timeLabel: string;
  redName: string;
  blueName: string;
  onClose: () => void;
  onConfirm: (result: FightEndResult) => void;
}

export default function FightEndModal({ currentRound, timeLabel, redName, blueName, onClose, onConfirm }: FightEndModalProps) {
  const [method, setMethod] = useState('KO/TKO');
  const [winner, setWinner] = useState<'red' | 'blue' | 'none'>('red');
  const [detail, setDetail] = useState('');
  const isDraw = method === 'Draw';
  // Draw forces the winner to "none" without a separate state-sync effect.
  const effectiveWinner = isDraw ? 'none' : winner;

  return (
    <div
      onClick={onClose}
      style={{
        position: 'fixed', inset: 0, zIndex: 200, display: 'grid', placeItems: 'center',
        background: 'rgba(4,6,9,0.66)', backdropFilter: 'blur(6px)', animation: 'feed-in .18s ease-out',
      }}
    >
      <div onClick={e => e.stopPropagation()} className="glass" style={{ width: 440, maxWidth: '92vw', padding: '22px 24px 24px', borderRadius: 18 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
          <span className="material-symbols-outlined" style={{ fontSize: 22, color: 'var(--purple-600)' }}>sports_score</span>
          <span className="font-display" style={{ fontSize: 24, letterSpacing: '0.03em', color: 'var(--text-primary)' }}>END OF FIGHT</span>
          <button onClick={onClose} className="icon-btn" style={{ marginLeft: 'auto', width: 32, height: 32 }}>
            <span className="material-symbols-outlined" style={{ fontSize: 18 }}>close</span>
          </button>
        </div>
        <div style={{ fontSize: 12, color: 'var(--text-muted)', fontWeight: 600, marginBottom: 18 }}>
          Round {currentRound} · {timeLabel} — how did the fight end?
        </div>

        <div className="label" style={{ fontSize: 9.5, marginBottom: 9 }}>Method</div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 7, marginBottom: 18 }}>
          {END_METHODS.map(m => (
            <button
              key={m}
              onClick={() => setMethod(m)}
              style={{
                padding: '8px 14px', borderRadius: 8, cursor: 'pointer', fontSize: 12.5, fontWeight: 700,
                border: `1.5px solid ${method === m ? 'var(--purple-600)' : 'var(--border-glass)'}`,
                background: method === m ? 'color-mix(in srgb, var(--purple-600) 16%, transparent)' : 'var(--surface-inner)',
                color: method === m ? 'var(--text-primary)' : 'var(--text-secondary)', transition: 'all .12s',
                fontFamily: 'inherit',
              }}
            >{m}</button>
          ))}
        </div>

        <div className="label" style={{ fontSize: 9.5, marginBottom: 9 }}>Winner</div>
        <div style={{ display: 'flex', gap: 8, marginBottom: 18 }}>
          <WinnerBtn selected={effectiveWinner === 'red'} disabled={isDraw} onClick={() => setWinner('red')} label={redName} color="var(--f-red)" />
          <WinnerBtn selected={effectiveWinner === 'blue'} disabled={isDraw} onClick={() => setWinner('blue')} label={blueName} color="var(--f-blue)" />
          <WinnerBtn selected={effectiveWinner === 'none'} disabled={false} onClick={() => setWinner('none')} label="Draw" />
        </div>

        <div className="label" style={{ fontSize: 9.5, marginBottom: 9 }}>
          Detail <span style={{ color: 'var(--text-disabled)', fontWeight: 600, textTransform: 'none', letterSpacing: 0 }}>(optional)</span>
        </div>
        <input
          value={detail}
          onChange={e => setDetail(e.target.value)}
          placeholder="e.g. rear-naked choke, head kick…"
          style={{
            width: '100%', padding: '10px 12px', borderRadius: 9, border: '1px solid var(--border-glass)',
            background: 'var(--surface-inner)', color: 'var(--text-primary)', fontSize: 13,
            fontFamily: 'inherit', outline: 'none', marginBottom: 22, boxSizing: 'border-box',
          }}
        />

        <div style={{ display: 'flex', gap: 10 }}>
          <button
            onClick={onClose}
            style={{
              flex: 1, padding: '11px', borderRadius: 10, cursor: 'pointer', fontWeight: 700, fontSize: 13,
              border: '1px solid var(--border-glass)', background: 'var(--surface-inner)', color: 'var(--text-secondary)',
              fontFamily: 'inherit',
            }}
          >Cancel</button>
          <button
            onClick={() => onConfirm({ method, winner: effectiveWinner, detail })}
            style={{
              flex: 1.4, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 7,
              padding: '11px', borderRadius: 10, cursor: 'pointer', fontWeight: 700, fontSize: 13,
              border: 'none', background: 'linear-gradient(135deg, var(--purple-600), #5b21b6)', color: '#fff',
              boxShadow: '0 0 16px color-mix(in srgb, var(--purple-600) 32%, transparent)', fontFamily: 'inherit',
            }}
          >
            <span className="material-symbols-outlined" style={{ fontSize: 18 }}>check</span>
            Record result
          </button>
        </div>
      </div>
    </div>
  );
}
