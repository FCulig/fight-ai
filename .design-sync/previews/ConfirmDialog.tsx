import { ConfirmDialog } from 'fightlytics';

const noop = () => {};

// The app's delete flow (Player, FightList): danger, spelled-out consequences.
export const DeleteFight = () => (
  <ConfirmDialog
    open
    title="Delete fight?"
    message={<><strong style={{ color: 'var(--text-primary)' }}>Adesanya vs. Pereira</strong> will be permanently deleted — the source video file, all pipeline predictions, hand labels, rounds, and tracked fighter frames. This cannot be undone.</>}
    confirmLabel="Delete fight"
    confirmIcon="delete_forever"
    danger
    onCancel={noop}
    onConfirm={noop}
  />
);

export const Neutral = () => (
  <ConfirmDialog
    open
    title="Finish labelling?"
    message="The fight is marked as ground truth. You can reopen it later from the Annotate header."
    confirmLabel="Finish labelling"
    onCancel={noop}
    onConfirm={noop}
  />
);

export const BusyWithError = () => (
  <ConfirmDialog
    open
    title="Delete fight?"
    message="The source video and every event for this fight will be removed."
    confirmLabel="Delete fight"
    confirmIcon="delete_forever"
    danger
    busy
    error="Couldn't reach the server. Try again."
    onCancel={noop}
    onConfirm={noop}
  />
);
