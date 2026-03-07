import type { Event } from '../types/Event';

export const fetchEvents = async (): Promise<Event[]> => {
  const response = await fetch('/events/');
  
  if (!response.ok) {
    throw new Error(`Failed to fetch events: ${response.statusText}`);
  }

  return response.json();
};