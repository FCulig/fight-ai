import { EdgeRow } from 'fightlytics';

// One tale-of-the-tape row: the bar leans toward the corner with the edge.
export const TapeRows = () => (
  <div style={{ width: 420 }}>
    <EdgeRow t={{ label: 'Height', r: "6'1\"", b: "6'3\"" }} />
    <EdgeRow t={{ label: 'Reach', r: '74"', b: '76"' }} />
    <EdgeRow t={{ label: 'Age', r: 29, b: 27, lowerWins: true }} />
  </div>
);

export const Even = () => (
  <div style={{ width: 420 }}><EdgeRow t={{ label: 'Reach', r: '75"', b: '75"' }} /></div>
);
