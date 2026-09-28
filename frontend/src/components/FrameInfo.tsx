interface FrameInfoProps {
  currentFrame: number;
  currentMs: number;
  fps: number;
}

export default function FrameInfo({ currentFrame, currentMs, fps }: FrameInfoProps) {
  return (
    <div
      style={{
        display: 'flex',
        gap: 20,
        fontSize: 11,
        color: 'var(--text-disabled)',
        fontFamily: 'var(--mono)',
        fontVariantNumeric: 'tabular-nums',
        padding: '2px 4px',
      }}
    >
      <span>
        Frame: <strong>{currentFrame}</strong>
      </span>
      <span>
        Time: <strong>{currentMs}ms</strong>
      </span>
      <span>
        FPS: <strong>{fps}</strong>
      </span>
    </div>
  );
}
