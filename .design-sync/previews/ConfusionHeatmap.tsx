import { ConfusionHeatmap } from 'fightlytics';

// Keys are "<truth>><predicted>"; orange is the model's colour.
export const StrikeFamilies = () => (
  <div style={{ width: 520 }}>
    <ConfusionHeatmap confusion={{
      'cross>cross': 34, 'cross>jab': 6, 'cross>hook': 3,
      'hook>hook': 21, 'hook>cross': 5, 'hook>uppercut': 2,
      'jab>jab': 41, 'jab>cross': 8,
      'kick>kick': 18, 'kick>knee': 1,
      'uppercut>uppercut': 7, 'uppercut>hook': 4,
    }} />
  </div>
);

export const FightStates = () => (
  <div style={{ width: 420 }}>
    <ConfusionHeatmap confusion={{
      'CLINCH>CLINCH': 820, 'CLINCH>STRIKING': 210, 'CLINCH>GROUND': 40,
      'GROUND>GROUND': 1430, 'GROUND>CLINCH': 95,
      'STRIKING>STRIKING': 5210, 'STRIKING>CLINCH': 330,
    }} />
  </div>
);

export const Empty = () => <ConfusionHeatmap confusion={{}} emptyLabel="No specific-family matches yet." />;
