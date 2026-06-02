import type { Event } from '../types/Event';
import type { Fight } from '../types/Fight';
import type { FighterFrame } from '../types/FighterFrame';
import type { Round } from '../types/Round';

export const fetchEvents = async (): Promise<Event[]> => {
  const response = await fetch('/events/');
  if (!response.ok) throw new Error(`Failed to fetch events: ${response.statusText}`);
  return response.json();
};

export const fetchFightEvents = async (fightId: number): Promise<Event[]> => {
  const response = await fetch(`/fights/${fightId}/events/`);
  if (!response.ok) throw new Error(`Failed to fetch events: ${response.statusText}`);
  return response.json();
};

export const fetchFights = async (): Promise<Fight[]> => {
  const response = await fetch('/fights/');
  if (!response.ok) throw new Error(`Failed to fetch fights: ${response.statusText}`);
  return response.json();
};

export const fetchFighterFrames = async (fightId: number): Promise<FighterFrame[]> => {
  const response = await fetch(`/fights/${fightId}/frames/`);
  if (!response.ok) throw new Error(`Failed to fetch fighter frames: ${response.statusText}`);
  return response.json();
};

export const fetchRounds = async (fightId: number): Promise<Round[]> => {
  const response = await fetch(`/fights/${fightId}/rounds/`);
  if (!response.ok) throw new Error(`Failed to fetch rounds: ${response.statusText}`);
  return response.json();
};
