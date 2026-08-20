import { ThreatEvent } from './types';

const httpBase = process.env.NEXT_PUBLIC_BACKEND_HTTP_URL ?? 'http://localhost:8000';

export async function fetchEvents(threatLevel?: string): Promise<ThreatEvent[]> {
  const url = new URL(`${httpBase}/events`);
  if (threatLevel) {
    url.searchParams.set('threat_level', threatLevel);
  }
  const response = await fetch(url, { cache: 'no-store' });
  if (!response.ok) {
    return [];
  }
  return response.json();
}

export async function fetchEvent(id: string): Promise<ThreatEvent | null> {
  const response = await fetch(`${httpBase}/events/${id}`, { cache: 'no-store' });
  if (!response.ok) {
    return null;
  }
  return response.json();
}

export async function deleteEvent(id: string): Promise<boolean> {
  const response = await fetch(`${httpBase}/events/${id}`, { method: 'DELETE' });
  return response.ok;
}
