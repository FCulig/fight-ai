// One entry per Claude Design screen. `start` (seconds) moves the stub video's
// playhead after load. `{reviewJabId}` is filled from synth.mjs's output.
export const SCREENS = [
  { name: 'Fight list', file: 'Fight List', path: '/' },
  { name: 'Player', file: 'Analysis Player', path: '/fights/62', start: 400 },
  { name: 'Annotate', file: 'Annotate', path: '/fights/68/annotate', role: 'labeller', start: 150 },
  { name: 'Training data', file: 'Training Data', path: '/training-data', role: 'labeller' },
  { name: 'Training data: jab review', file: 'Training Data Review', path: '/training-data/jab/{reviewJabId}', role: 'labeller' },
  { name: 'Pipeline accuracy', file: 'Pipeline Accuracy', path: '/accuracy' },
  { name: 'Users', file: 'Users', path: '/users' },
  { name: 'Sign in', file: 'Sign In', path: '/', signedOut: true },
];
