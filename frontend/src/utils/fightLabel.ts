import type { Fight } from '../types/Fight';

/** "RED vs BLUE" when both fighters are known, else the video's filename stem. */
export function fightLabel(fight: Fight): string {
  if (fight.red_fighter_name && fight.blue_fighter_name) {
    return `${fight.red_fighter_name} vs ${fight.blue_fighter_name}`;
  }
  return fight.video_path.split('/').pop()?.replace(/\.[^/.]+$/, '') ?? fight.video_path;
}
