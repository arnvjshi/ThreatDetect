import { ThreatEvent } from './types';

/**
 * Returns the backend HTTP base URL.
 * - On the server (inside Docker): uses INTERNAL_BACKEND_URL or 'http://backend:8000'
 *   so server-side rendering connects directly across the Docker bridge network.
 * - On the client (browser): uses window.location.hostname:8000 so it automatically
 *   works with raspberrypi.local, any DHCP IP assigned by the router, or localhost.
 */
export function getBackendHttpUrl(): string {
  if (typeof window === 'undefined') {
    return process.env.INTERNAL_BACKEND_URL || (process.env.NODE_ENV === 'production' ? 'http://backend:8000' : (process.env.NEXT_PUBLIC_BACKEND_HTTP_URL || 'http://localhost:8000'));
  }
  if (typeof window !== 'undefined' && window.location?.hostname) {
    const proto = window.location.protocol === 'https:' ? 'https:' : 'http:';
    return `${proto}//${window.location.hostname}:8000`;
  }
  return process.env.NEXT_PUBLIC_BACKEND_HTTP_URL || 'http://localhost:8000';
}

/**
 * Returns the backend WebSocket base URL.
 * In the browser, dynamically uses the current hostname with port 8000.
 */
export function getBackendWsUrl(): string {
  if (typeof window !== 'undefined' && window.location?.hostname) {
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${proto}//${window.location.hostname}:8000`;
  }
  return process.env.NEXT_PUBLIC_BACKEND_WS_URL || 'ws://localhost:8000';
}

export async function fetchEvents(threatLevel?: string): Promise<ThreatEvent[]> {
  try {
    const base = getBackendHttpUrl();
    const url = new URL(`${base}/events`);
    if (threatLevel) {
      url.searchParams.set('threat_level', threatLevel);
    }
    const response = await fetch(url.toString(), {
      cache: 'no-store',
      signal: AbortSignal.timeout(5000),
    });
    if (!response.ok) {
      console.warn(`fetchEvents returned status ${response.status}`);
      return [];
    }
    return await response.json();
  } catch (err: unknown) {
    if (err && typeof err === 'object' && 'digest' in err && err.digest === 'DYNAMIC_SERVER_USAGE') {
      throw err;
    }
    console.error('fetchEvents failed:', err);
    return [];
  }
}

export async function fetchEvent(id: string): Promise<ThreatEvent | null> {
  try {
    const base = getBackendHttpUrl();
    const response = await fetch(`${base}/events/${id}`, {
      cache: 'no-store',
      signal: AbortSignal.timeout(5000),
    });
    if (!response.ok) {
      return null;
    }
    return await response.json();
  } catch (err: unknown) {
    if (err && typeof err === 'object' && 'digest' in err && err.digest === 'DYNAMIC_SERVER_USAGE') {
      throw err;
    }
    console.error(`fetchEvent(${id}) failed:`, err);
    return null;
  }
}

export async function deleteEvent(id: string): Promise<boolean> {
  try {
    const base = getBackendHttpUrl();
    const response = await fetch(`${base}/events/${id}`, { method: 'DELETE' });
    return response.ok;
  } catch (err) {
    console.error(`deleteEvent(${id}) failed:`, err);
    return false;
  }
}
