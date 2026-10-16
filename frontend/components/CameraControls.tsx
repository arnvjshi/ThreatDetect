'use client';

import { useState, useEffect } from 'react';
import type { JSX } from 'react';
import clsx from 'clsx';
import { getBackendHttpUrl } from '@/lib/api';

const DEFAULT_CAMERA_SOURCE = process.env.NEXT_PUBLIC_DEFAULT_CAMERA_SOURCE || '0';
const DEFAULT_ESP32_BASE_URL = process.env.NEXT_PUBLIC_DEFAULT_ESP32_BASE_URL || 'http://threatdetect-cam.local';

export function CameraControls(): Readonly<JSX.Element> {
  const [loading, setLoading] = useState(false);
  const [running, setRunning] = useState(false);
  const [userEmail, setUserEmail] = useState('');
  const [cameraMode, setCameraMode] = useState<'normal' | 'esp32'>('normal');
  const [cameraSource, setCameraSource] = useState(DEFAULT_CAMERA_SOURCE);
  const [esp32BaseUrl, setEsp32BaseUrl] = useState(DEFAULT_ESP32_BASE_URL);
  const [connectionStatus, setConnectionStatus] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    if (typeof globalThis !== 'undefined' && globalThis.localStorage) {
      const email = globalThis.localStorage.getItem('userEmail') || '';
      const savedMode = (globalThis.localStorage.getItem('cameraMode') as 'normal' | 'esp32' | null) || 'normal';
      const savedSource = globalThis.localStorage.getItem('cameraSource') || DEFAULT_CAMERA_SOURCE;
      const savedBaseUrl = globalThis.localStorage.getItem('esp32BaseUrl') || DEFAULT_ESP32_BASE_URL;
      setUserEmail(email);
      setCameraMode(savedMode);
      setCameraSource(savedSource);
      setEsp32BaseUrl(savedBaseUrl);
    }
  }, []);

  const handleStart = async () => {
    if (!userEmail) {
      setError('Please register first to start the camera');
      return;
    }

    setLoading(true);
    setConnectionStatus('');
    setError('');

    const normalizedSource =
      cameraMode === 'esp32' ? `${esp32BaseUrl.replace(/\/$/, '')}/stream` : cameraSource.trim() || '0';
    const flashUrl = cameraMode === 'esp32' ? `${esp32BaseUrl.replace(/\/$/, '')}/flash` : '';

    try {
      const response = await fetch(`${getBackendHttpUrl()}/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          source: normalizedSource,
          owner_email: userEmail,
          camera_mode: cameraMode,
          flash_url: flashUrl,
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to start camera');
      }

      setRunning(true);
      if (typeof globalThis !== 'undefined' && globalThis.localStorage) {
        globalThis.localStorage.setItem('cameraMode', cameraMode);
        globalThis.localStorage.setItem('cameraSource', normalizedSource);
        globalThis.localStorage.setItem('esp32BaseUrl', esp32BaseUrl);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start camera');
    } finally {
      setLoading(false);
    }
  };

  const handleStop = async () => {
    setLoading(true);
    setConnectionStatus('');
    setError('');

    try {
      const response = await fetch(`${getBackendHttpUrl()}/stop`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });

      if (!response.ok) {
        throw new Error('Failed to stop camera');
      }

      setRunning(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to stop camera');
    } finally {
      setLoading(false);
    }
  };

  const handleCheckEsp32 = async () => {
    const base = esp32BaseUrl.replace(/\/$/, '');
    setConnectionStatus('Checking ESP32 connection...');
    setError('');

    try {
      const response = await fetch(`${base}/status`, { method: 'GET' });
      if (!response.ok) {
        throw new Error('Status endpoint not reachable');
      }
      const payload = (await response.json()) as { ip?: string; hostname?: string; camera_ready?: boolean; camera_error?: string };
      if (payload.camera_ready === false) {
        setConnectionStatus(
          `ESP32 reachable but camera is not initialized (${payload.camera_error ?? 'unknown error'}). Recheck board model/pins/power.`
        );
        return;
      }
      setConnectionStatus(`Connected: ${payload.hostname ?? 'esp32cam.local'} (${payload.ip ?? 'unknown ip'})`);
    } catch {
      setConnectionStatus('ESP32 not reachable. Check WiFi/AP isolation or use current IP from router.');
    }
  };

  return (
    <div className="space-y-4">
      {error && (
        <div className="p-3 bg-red-500/20 border border-red-500/30 rounded-lg">
          <p className="text-red-300 text-xs">{error}</p>
        </div>
      )}

      {connectionStatus && (
        <div className="p-3 bg-slate-500/20 border border-slate-500/30 rounded-lg">
          <p className="text-slate-200 text-xs">{connectionStatus}</p>
        </div>
      )}

      {userEmail && (
        <div className="p-3 bg-cyan-500/20 border border-cyan-500/30 rounded-lg">
          <p className="text-cyan-300 text-xs">Email: {userEmail}</p>
        </div>
      )}

      <div className="space-y-2">
        <label htmlFor="camera-mode" className="text-xs font-medium uppercase tracking-[0.24em] text-slate-400">
          Camera type
        </label>
        <select
          id="camera-mode"
          value={cameraMode}
          onChange={(event) => setCameraMode(event.target.value as 'normal' | 'esp32')}
          className="w-full rounded-lg border border-white/10 bg-black/40 px-3 py-2 text-sm text-white outline-none transition focus:border-cyan-400/60 focus:ring-2 focus:ring-cyan-400/20"
        >
          <option value="normal">Normal camera / webcam</option>
          <option value="esp32">ESP32-CAM</option>
        </select>
      </div>

      {cameraMode === 'normal' ? (
        <div className="space-y-2">
          <label htmlFor="camera-source" className="text-xs font-medium uppercase tracking-[0.24em] text-slate-400">
            Camera source
          </label>
          <input
            id="camera-source"
            value={cameraSource}
            onChange={(event) => setCameraSource(event.target.value)}
            placeholder="0 or 1"
            className="w-full rounded-lg border border-white/10 bg-black/40 px-3 py-2 text-sm text-white outline-none transition focus:border-cyan-400/60 focus:ring-2 focus:ring-cyan-400/20"
          />
          <p className="text-xs text-slate-400">Use 0 for your default webcam or 1 if you have a second camera attached.</p>
        </div>
      ) : (
        <div className="space-y-2">
          <label htmlFor="esp32-base-url" className="text-xs font-medium uppercase tracking-[0.24em] text-slate-400">
            ESP32-CAM base URL
          </label>
          <input
            id="esp32-base-url"
            value={esp32BaseUrl}
            onChange={(event) => setEsp32BaseUrl(event.target.value)}
            placeholder="http://threatdetect-cam.local"
            className="w-full rounded-lg border border-white/10 bg-black/40 px-3 py-2 text-sm text-white outline-none transition focus:border-cyan-400/60 focus:ring-2 focus:ring-cyan-400/20"
          />
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setEsp32BaseUrl('http://threatdetect-cam.local')}
              className="rounded-lg border border-white/10 bg-white/5 px-3 py-1 text-xs text-slate-200 hover:bg-white/10"
            >
              Use threatdetect-cam.local
            </button>
            <button
              type="button"
              onClick={handleCheckEsp32}
              className="rounded-lg border border-cyan-500/30 bg-cyan-500/10 px-3 py-1 text-xs text-cyan-100 hover:bg-cyan-500/20"
            >
              Check connection
            </button>
          </div>
          <p className="text-xs text-slate-400">The app will use /stream for video and /flash for the LED trigger. Hostname works even if IP changes.</p>
        </div>
      )}

      <button
        onClick={handleStart}
        disabled={loading || running || !userEmail}
        className={clsx(
          'w-full py-2 px-4 rounded-lg font-medium transition-all duration-200',
          running || !userEmail
            ? 'bg-gray-700 text-gray-400 cursor-not-allowed'
            : 'bg-cyan-600 hover:bg-cyan-700 text-white',
          'focus:outline-none focus:ring-2 focus:ring-cyan-500',
          loading && 'opacity-50'
        )}
      >
        {loading && running === false ? 'Starting...' : 'Start camera'}
      </button>

      <button
        onClick={handleStop}
        disabled={loading || running === false}
        className={clsx(
          'w-full py-2 px-4 rounded-lg font-medium transition-all duration-200',
          running === false
            ? 'bg-gray-700 text-gray-400 cursor-not-allowed'
            : 'bg-red-600 hover:bg-red-700 text-white',
          'focus:outline-none focus:ring-2 focus:ring-red-500',
          loading && 'opacity-50'
        )}
      >
        {loading && running ? 'Stopping...' : 'Stop camera'}
      </button>

      {!userEmail && (
        <div className="p-3 bg-amber-500/20 border border-amber-500/30 rounded-lg">
          <p className="text-amber-300 text-xs">
            <a href="/register" className="underline font-medium">
              Register first
            </a>{' '}
            to enable alerts
          </p>
        </div>
      )}
    </div>
  );
}
