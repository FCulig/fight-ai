interface FrameInfoProps {
  currentFrame: number;
  currentMs: number;
  fps: number;
}

export default function FrameInfo({ currentFrame, currentMs, fps }: FrameInfoProps) {
  return (
    <div
      style={{
        marginTop: 8,
        display: 'flex',
        gap: 20,
        fontSize: 12,
        color: '#888',
        fontFamily: 'monospace',
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
