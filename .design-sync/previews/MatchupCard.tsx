import { MatchupCard } from 'fightlytics';

const fighters = {
  red: { id: 'red', name: 'BATUR', first: 'Adam', record: '14-3-0', nick: 'The Anvil', country: 'KAZ', corner: 'Red corner',
    reach: '74"', height: "6'1\"", age: 29, color: 'var(--f-red)',
    form: [{ r: 'W', m: 'KO', o: 'Reyes' }, { r: 'W', m: 'DEC', o: 'Volkov' }, { r: 'L', m: 'SUB', o: 'Pavlik' }, { r: 'W', m: 'KO', o: 'Ngannou' }, { r: 'W', m: 'TKO', o: 'Lewis' }] },
  blue: { id: 'blue', name: 'STAMATOVIC', first: 'Luka', record: '11-2-0', nick: 'Vuk', country: 'SRB', corner: 'Blue corner',
    reach: '76"', height: "6'3\"", age: 27, color: 'var(--f-blue)',
    form: [{ r: 'W', m: 'SUB', o: 'Hardy' }, { r: 'W', m: 'TKO', o: 'Rozenstruik' }, { r: 'W', m: 'DEC', o: 'Tuivasa' }, { r: 'L', m: 'DEC', o: 'Gane' }, { r: 'W', m: 'KO', o: 'Spivak' }] },
} as const;

// Tale of the tape: names, records, height/reach/age edges and recent form.
export const TaleOfTheTape = () => (
  <div style={{ width: 1180 }}><MatchupCard fighters={fighters as never} /></div>
);
