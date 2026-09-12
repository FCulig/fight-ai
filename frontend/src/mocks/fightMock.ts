export interface FormResult {
  r: 'W' | 'L';
  m: string;
  o: string;
}

export interface FighterProfile {
  id: string;
  name: string;
  first: string;
  record: string;
  nick: string;
  country: string;
  corner: string;
  reach: string;
  height: string;
  age: number;
  color: string;
  form: FormResult[];
}

export interface FighterStats {
  sig: [number, number];
  total: [number, number];
  head: number;
  body: number;
  leg: number;
  distance: number;
  clinch: number;
  ground: number;
  td: [number, number];
  ctrl: number;
  kd: number;
  sub: number;
  acc: number;
}

export interface ScopeStats {
  red: FighterStats;
  blue: FighterStats;
}

export const ctrlFmt = (s: number) =>
  `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;

export const fighters: { red: FighterProfile; blue: FighterProfile } = {
  red: {
    id: 'red',
    name: 'BATUR',
    first: 'Adam',
    record: '14-3-0',
    nick: 'The Anvil',
    country: 'KAZ',
    corner: 'Red corner',
    reach: '74"',
    height: "6'1\"",
    age: 29,
    color: 'var(--f-red)',
    form: [
      { r: 'W', m: 'KO',  o: 'Reyes'   },
      { r: 'W', m: 'DEC', o: 'Volkov'  },
      { r: 'L', m: 'SUB', o: 'Pavlik'  },
      { r: 'W', m: 'KO',  o: 'Ngannou' },
      { r: 'W', m: 'TKO', o: 'Lewis'   },
    ],
  },
  blue: {
    id: 'blue',
    name: 'STAMATOVIC',
    first: 'Luka',
    record: '11-2-0',
    nick: 'Vuk',
    country: 'SRB',
    corner: 'Blue corner',
    reach: '76"',
    height: "6'3\"",
    age: 27,
    color: 'var(--f-blue)',
    form: [
      { r: 'W', m: 'SUB', o: 'Hardy'       },
      { r: 'W', m: 'TKO', o: 'Rozenstruik' },
      { r: 'W', m: 'DEC', o: 'Tuivasa'     },
      { r: 'L', m: 'DEC', o: 'Gane'        },
      { r: 'W', m: 'KO',  o: 'Spivak'      },
    ],
  },
};

export const DURATION = 677;
export const R1_END = 313;

// Overlays a real fighter name (from Fight.red_fighter_name / blue_fighter_name,
// "First Last") onto a mock profile, splitting it the same way the mock data is
// shaped: surname as the big display `name`, given name(s) as `first`. Falls back
// to the mock profile untouched when the fight has no linked fighter yet.
// Everything else on FighterProfile (nickname, record, reach, height, age,
// country, form) has no backend source — see TODO_BACKEND_DATA.md #1.
export function withRealName(profile: FighterProfile, fullName: string | null | undefined): FighterProfile {
  if (!fullName?.trim()) return profile;
  const parts = fullName.trim().split(/\s+/);
  const last = parts[parts.length - 1];
  const first = parts.slice(0, -1).join(' ') || last;
  return { ...profile, name: last.toUpperCase(), first };
}
