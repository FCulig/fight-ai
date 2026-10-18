import { FightEndModal } from 'fightlytics';

// Annotate's "End of fight" dialog: method, winner, optional detail.
export const EndOfFight = () => (
  <FightEndModal currentRound={2} timeLabel="3:41" redName="Adesanya" blueName="Pereira" onClose={() => {}} onConfirm={() => {}} />
);
