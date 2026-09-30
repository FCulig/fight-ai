import type { Event, EventKind, EventSource } from '../types/Event';
import type { EvalRunResponse, EvalRunSummary, FixtureSummary } from '../types/EvalRun';
import type { Fight, FightPurpose } from '../types/Fight';
import type { Fighter } from '../types/Fighter';
import type { FighterFrame } from '../types/FighterFrame';
import type { Round } from '../types/Round';
import type { Role, User } from '../types/User';

const API = '/api';

/** Every data call goes through here. A 401 means the session expired or was
 * cleared mid-use: reloading lets AuthProvider re-check /auth/me and show the
 * sign-in page. */
const apiFetch = async (path: string, init?: RequestInit): Promise<Response> => {
  const response = await fetch(`${API}${path}`, init);
  if (response.status === 401) {
    window.location.reload();
    return new Promise<Response>(() => {}); // never settles: the page is going away
  }
  return response;
};

/** `<video src>` and EventSource can't go through apiFetch, but the session
 * cookie still rides along because they are same-origin. */
export const videoUrl = (fightId: number) => `${API}/fights/${fightId}/video`;
export const FIGHT_STREAM_URL = `${API}/fights/stream`;

const errorDetail = async (response: Response, fallback: string): Promise<string> => {
  const body = await response.json().catch(() => null);
  return typeof body?.detail === 'string' ? body.detail : `${fallback}: ${response.statusText}`;
};

export type MeResult =
  | { status: 'signed_in'; user: User }
  | { status: 'signed_out' }
  | { status: 'disabled' };

/** Uses plain fetch, not apiFetch: a 401 here is the normal signed-out
 * answer, and reloading on it would loop. */
export const fetchMe = async (): Promise<MeResult> => {
  const response = await fetch(`${API}/auth/me`);
  if (response.status === 401) return { status: 'signed_out' };
  if (response.status === 403) return { status: 'disabled' };
  if (!response.ok) throw new Error(await errorDetail(response, 'Failed to load your account'));
  return { status: 'signed_in', user: await response.json() };
};

/** A full-page navigation target, not a fetch: the backend redirects to Google. */
export const loginUrl = (next: string) => `${API}/auth/login?next=${encodeURIComponent(next)}`;

export const logout = async (): Promise<void> => {
  await fetch(`${API}/auth/logout`, { method: 'POST' });
};

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
  const response = await apiFetch(`/fights/${fightId}/events/${qs ? `?${qs}` : ''}`);
  if (!response.ok) throw new Error(`Failed to fetch events: ${response.statusText}`);
  return response.json();
};

export const createEvent = async (fightId: number, payload: CreateEventPayload): Promise<Event> => {
  const response = await apiFetch(`/fights/${fightId}/events/`, {
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
  const response = await apiFetch(`/fights/${fightId}/events/${eventId}`, {
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

export const verifyEvent = async (fightId: number, eventId: number, isVerified: boolean | null): Promise<Event> => {
  const response = await apiFetch(`/fights/${fightId}/events/${eventId}/verify`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ is_verified: isVerified }),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail ?? `Failed to verify event: ${response.statusText}`);
  }
  return response.json();
};

export interface ReclassifyEventPayload {
  action: string;
  target: string | null;
  success: boolean | null;
}

export const reclassifyEvent = async (fightId: number, eventId: number, payload: ReclassifyEventPayload): Promise<Event> => {
  const response = await apiFetch(`/fights/${fightId}/events/${eventId}/reclassify`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail ?? `Failed to reclassify event: ${response.statusText}`);
  }
  return response.json();
};

export const deleteEvent = async (fightId: number, eventId: number): Promise<void> => {
  const response = await apiFetch(`/fights/${fightId}/events/${eventId}`, { method: 'DELETE' });
  if (!response.ok) throw new Error(`Failed to delete event: ${response.statusText}`);
};

export const fetchFights = async (): Promise<Fight[]> => {
  const response = await apiFetch('/fights/');
  if (!response.ok) throw new Error(`Failed to fetch fights: ${response.statusText}`);
  return response.json();
};

export interface FetchFighterFramesParams {
  /** 1-based, inclusive — narrows to a window instead of the whole fight
   * (ClipPlayer's ~0.6s clip). Omit both for Player/Annotate's free-scrub
   * timeline, which needs the whole fight. */
  start_frame?: number;
  end_frame?: number;
}

export const fetchFighterFrames = async (fightId: number, params?: FetchFighterFramesParams): Promise<FighterFrame[]> => {
  const query = new URLSearchParams();
  if (params?.start_frame != null) query.append('start_frame', String(params.start_frame));
  if (params?.end_frame != null) query.append('end_frame', String(params.end_frame));
  const qs = query.toString();
  const response = await apiFetch(`/fights/${fightId}/frames/${qs ? `?${qs}` : ''}`);
  if (!response.ok) throw new Error(`Failed to fetch fighter frames: ${response.statusText}`);
  return response.json();
};

export const fetchRounds = async (fightId: number): Promise<Round[]> => {
  const response = await apiFetch(`/fights/${fightId}/rounds/`);
  if (!response.ok) throw new Error(`Failed to fetch rounds: ${response.statusText}`);
  return response.json();
};

export const fetchFighters = async (search?: string): Promise<Fighter[]> => {
  const params = search ? `?search=${encodeURIComponent(search)}` : '';
  const response = await apiFetch(`/fighters/${params}`);
  if (!response.ok) throw new Error(`Failed to fetch fighters: ${response.statusText}`);
  return response.json();
};

export const createFighter = async (data: {
  first_name: string;
  last_name: string;
  nickname?: string;
}): Promise<Fighter> => {
  const response = await apiFetch('/fighters/', {
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
  const response = await apiFetch('/fights/upload', { method: 'POST', body: form });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail ?? `Upload failed: ${response.statusText}`);
  }
  return response.json();
};

export const finishLabeling = async (fightId: number): Promise<Fight> => {
  const response = await apiFetch(`/fights/${fightId}/finish-labeling`, { method: 'POST' });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail ?? `Failed to finish labeling: ${response.statusText}`);
  }
  return response.json();
};

/** labeling_complete → labeling_in_progress, so Annotate re-opens the fight for
 * editing; finishLabeling() is the way back. */
export const reopenLabeling = async (fightId: number): Promise<Fight> => {
  const response = await apiFetch(`/fights/${fightId}/reopen-labeling`, { method: 'POST' });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail ?? `Failed to reopen labeling: ${response.statusText}`);
  }
  return response.json();
};

export const deleteFight = async (fightId: number): Promise<void> => {
  const response = await apiFetch(`/fights/${fightId}`, { method: 'DELETE' });
  if (!response.ok) throw new Error(`Failed to delete fight: ${response.statusText}`);
};

export const fetchFixtures = async (): Promise<FixtureSummary[]> => {
  const response = await apiFetch('/eval-runs/fixtures');
  if (!response.ok) throw new Error(`Failed to fetch fixtures: ${response.statusText}`);
  return response.json();
};

export const fetchEvalRuns = async (
  referenceFightId: number,
  scoredFightId?: number,
): Promise<EvalRunSummary[]> => {
  const query = new URLSearchParams({ reference_fight_id: String(referenceFightId) });
  if (scoredFightId != null) query.append('scored_fight_id', String(scoredFightId));
  const response = await apiFetch(`/eval-runs/?${query.toString()}`);
  if (!response.ok) throw new Error(`Failed to fetch eval runs: ${response.statusText}`);
  return response.json();
};

export const fetchEvalRun = async (runId: number): Promise<EvalRunResponse> => {
  const response = await apiFetch(`/eval-runs/${runId}`);
  if (!response.ok) throw new Error(`Failed to fetch eval run: ${response.statusText}`);
  return response.json();
};

export const createEvalRun = async (
  referenceFightId: number,
  scoredFightId: number,
  toleranceSecs?: number,
): Promise<EvalRunResponse> => {
  const response = await apiFetch('/eval-runs/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      reference_fight_id: referenceFightId,
      scored_fight_id: scoredFightId,
      tolerance_secs: toleranceSecs ?? null,
    }),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail ?? `Failed to run scoring: ${response.statusText}`);
  }
  return response.json();
};

export const fetchUsers = async (): Promise<User[]> => {
  const response = await apiFetch('/users/');
  if (!response.ok) throw new Error(await errorDetail(response, 'Failed to fetch users'));
  return response.json();
};

/** Pre-provisions an email so its first sign-in lands with this role. */
export const createUser = async (email: string, role: Role): Promise<User> => {
  const response = await apiFetch('/users/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, role }),
  });
  if (!response.ok) throw new Error(await errorDetail(response, 'Failed to add user'));
  return response.json();
};

export const updateUser = async (
  userId: number,
  patch: { role?: Role; is_active?: boolean },
): Promise<User> => {
  const response = await apiFetch(`/users/${userId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(patch),
  });
  if (!response.ok) throw new Error(await errorDetail(response, 'Failed to update user'));
  return response.json();
};
