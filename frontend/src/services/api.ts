import type { Event } from '../types/Event';
import type { Fight } from '../types/Fight';
import type { Fighter } from '../types/Fighter';
import type { FighterFrame } from '../types/FighterFrame';
import type { Round } from '../types/Round';

export interface CreateEventPayload {
  frame: number;
  description: string;
  fighter_id?: number | null;
  action?: string | null;
  success?: boolean | null;
}

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

export const fetchFighters = async (search?: string): Promise<Fighter[]> => {
  const params = search ? `?search=${encodeURIComponent(search)}` : '';
  const response = await fetch(`/fighters/${params}`);
  if (!response.ok) throw new Error(`Failed to fetch fighters: ${response.statusText}`);
  return response.json();
};

export const createFighter = async (data: {
  first_name: string;
  last_name: string;
  nickname?: string;
}): Promise<Fighter> => {
  const response = await fetch('/fighters/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!response.ok) throw new Error(`Failed to create fighter: ${response.statusText}`);
  return response.json();
};

export const uploadFight = async (
  file: File,
  redFighterId?: number,
  blueFighterId?: number,
  mode: 'ai' | 'manual' = 'ai',
): Promise<Fight> => {
  const form = new FormData();
  form.append('file', file);
  if (redFighterId != null) form.append('red_fighter_id', String(redFighterId));
  if (blueFighterId != null) form.append('blue_fighter_id', String(blueFighterId));
  form.append('mode', mode);
  const response = await fetch('/fights/upload', { method: 'POST', body: form });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail ?? `Upload failed: ${response.statusText}`);
  }
  return response.json();
};

export const finishLabeling = async (fightId: number): Promise<Fight> => {
  const response = await fetch(`/fights/${fightId}/finish-labeling`, { method: 'POST' });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail ?? `Failed to finish labeling: ${response.statusText}`);
  }
  return response.json();
};

export const createEvent = async (fightId: number, payload: CreateEventPayload): Promise<Event> => {
  const response = await fetch(`/fights/${fightId}/events/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail ?? `Failed to create event: ${response.statusText}`);
  }
  return response.json();
};

export const deleteEvent = async (eventId: number): Promise<void> => {
  const response = await fetch(`/events/${eventId}`, { method: 'DELETE' });
  if (!response.ok) throw new Error(`Failed to delete event: ${response.statusText}`);
};
