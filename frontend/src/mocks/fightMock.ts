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

export const stats: Record<'fight' | 1 | 2, ScopeStats> = {
  fight: {
    red:  { sig: [84, 171], total: [96, 189], head: 52, body: 21, leg: 11, distance: 61, clinch: 14, ground: 9,  td: [2, 5], ctrl: 102, kd: 0, sub: 1, acc: 49 },
    blue: { sig: [71, 142], total: [81, 158], head: 40, body: 19, leg: 12, distance: 48, clinch: 13, ground: 10, td: [3, 6], ctrl: 158, kd: 1, sub: 1, acc: 50 },
  },
  1: {
    red:  { sig: [41, 82], total: [47, 90], head: 25, body: 10, leg: 6, distance: 30, clinch: 7, ground: 4, td: [1, 2], ctrl: 48, kd: 0, sub: 0, acc: 50 },
    blue: { sig: [38, 70], total: [44, 79], head: 22, body: 9,  leg: 7, distance: 24, clinch: 8, ground: 6, td: [2, 3], ctrl: 96, kd: 1, sub: 1, acc: 54 },
  },
  2: {
    red:  { sig: [43, 89], total: [49, 99], head: 27, body: 11, leg: 5, distance: 31, clinch: 7, ground: 5, td: [1, 3], ctrl: 54, kd: 0, sub: 1, acc: 48 },
    blue: { sig: [33, 72], total: [37, 79], head: 18, body: 10, leg: 5, distance: 24, clinch: 5, ground: 4, td: [1, 3], ctrl: 62, kd: 0, sub: 0, acc: 46 },
  },
};

// Sig strikes landed per 30s bucket (23 buckets for ~677s fight)
export const pace = {
  red:  [2, 3, 1, 4, 2, 3, 1, 2, 3, 2, 4, 1, 0, 3, 2, 1, 3, 2, 3, 4, 2, 1, 2],
  blue: [1, 2, 3, 2, 3, 1, 3, 2, 1, 3, 2, 1, 0, 2, 3, 2, 1, 3, 2, 1, 2, 3, 1],
};

export const paceBucket = 30;
export const DURATION = 677;
export const R1_END = 313;
