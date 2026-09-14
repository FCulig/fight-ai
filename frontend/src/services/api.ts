import type { Event, EventKind, EventSource } from '../types/Event';
import type { Fight, FightPurpose } from '../types/Fight';
import type { Fighter } from '../types/Fighter';
import type { FighterFrame } from '../types/FighterFrame';
import type { Round } from '../types/Round';

export interface FetchEventsParams {
  source?: EventSource;
  kind?: EventKind;
  fighter_id?: number;
  action?: string;
  success?: boolean;
}

export interface CreateEventPayload {
  kind?: EventKind; // defaults to 'point' server-side
  frame: number;
  end_frame?: number | null;
  description?: string | null;
  corner?: number | null;
  action?: string | null;
  target?: string | null;
  success?: boolean | null;
  labeler?: string | null;
  value?: string | null;
}

export interface UpdateEventPayload {
  frame?: number;
  end_frame?: number;
  value?: string;
}

export const fetchEvents = async (fightId: number, params?: FetchEventsParams): Promise<Event[]> => {
  const query = new URLSearchParams();
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined) query.append(key, String(value));
    });
  }
  const qs = query.toString();
  const response = await fetch(`/fights/${fightId}/events/${qs ? `?${qs}` : ''}`);
  if (!response.ok) throw new Error(`Failed to fetch events: ${response.statusText}`);
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

export const updateEvent = async (fightId: number, eventId: number, payload: UpdateEventPayload): Promise<Event> => {
  const response = await fetch(`/fights/${fightId}/events/${eventId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail ?? `Failed to update event: ${response.statusText}`);
  }
  return response.json();
};

export const deleteEvent = async (fightId: number, eventId: number): Promise<void> => {
  const response = await fetch(`/fights/${fightId}/events/${eventId}`, { method: 'DELETE' });
  if (!response.ok) throw new Error(`Failed to delete event: ${response.statusText}`);
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
  redFighterId: number | undefined,
  blueFighterId: number | undefined,
  purpose: FightPurpose,
): Promise<Fight> => {
  const form = new FormData();
  form.append('file', file);
  if (redFighterId != null) form.append('red_fighter_id', String(redFighterId));
  if (blueFighterId != null) form.append('blue_fighter_id', String(blueFighterId));
  // `purpose` also picks the pipeline track server-side: only 'ai_labeled'
  // runs strike detection and the state machine.
  form.append('purpose', purpose);
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

export const deleteFight = async (fightId: number): Promise<void> => {
  const response = await fetch(`/fights/${fightId}`, { method: 'DELETE' });
  if (!response.ok) throw new Error(`Failed to delete fight: ${response.statusText}`);
};
