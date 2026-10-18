import { SaveStatus } from 'fightlytics';

export const Saved = () => <SaveStatus saving={false} />;
export const Saving = () => <SaveStatus saving />;
