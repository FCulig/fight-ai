import { useState } from 'react';
import { ModeCard } from 'fightlytics';

// UploadDialog's mode picker: two cards side by side, one active.
export const ModePicker = () => {
  const [mode, setMode] = useState<'manual' | 'ai'>('ai');
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, width: 560 }}>
      <ModeCard active={mode === 'manual'} onClick={() => setMode('manual')} icon="draw" title="Self-annotate"
        desc="You tag every strike, takedown and position change yourself on the timeline."
        points={[{ icon: 'tune', text: 'Full editorial control' }, { icon: 'schedule', text: 'Hands-on, slower' }]} />
      <ModeCard active={mode === 'ai'} onClick={() => setMode('ai')} icon="auto_awesome" title="AI annotation"
        desc="Our model detects and labels every event automatically — ready to review in minutes."
        points={[{ icon: 'bolt', text: 'Fastest · fully automatic' }, { icon: 'edit', text: 'Editable afterwards' }]} />
    </div>
  );
};

export const ComingSoon = () => (
  <div style={{ width: 274 }}>
    <ModeCard active={false} onClick={() => {}} icon="sensors" title="Live analysis" comingSoon
      desc="Follow a fight as it happens, strike by strike."
      points={[{ icon: 'bolt', text: 'Real-time feed' }]} />
  </div>
);
