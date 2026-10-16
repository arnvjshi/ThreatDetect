'use client';

import { useEffect, useState } from 'react';
import type { ReactElement } from 'react';

import clsx from 'clsx';

import { UserProfile } from '@/lib/types';
import { getBackendHttpUrl } from '@/lib/api';

export function UserInfoCard(): ReactElement {
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const loadProfile = async () => {
      const storedEmail = globalThis.localStorage?.getItem('userEmail') || '';
      if (!storedEmail) {
        setError('No user profile saved yet. Register an email to create one.');
        setLoading(false);
        return;
      }

      try {
        const response = await fetch(`${getBackendHttpUrl()}/users/email/${encodeURIComponent(storedEmail)}`, {
          cache: 'no-store',
        });
        if (!response.ok) {
          throw new Error('Unable to load user profile');
        }
        const data = (await response.json()) as UserProfile;
        setProfile(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unable to load user profile');
      } finally {
        setLoading(false);
      }
    };

    loadProfile();
  }, []);

  if (loading) {
    return <div className="glass-card subtle-ring p-6 text-sm text-slate-300">Loading profile...</div>;
  }

  return (
    <div className="glass-card subtle-ring p-6 space-y-5">
      {error && <div className="rounded-2xl border border-amber-400/20 bg-amber-400/10 px-4 py-3 text-sm text-amber-100">{error}</div>}
      {profile ? (
        <>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
              <p className="metric-label">Registered email</p>
              <p className="mt-2 text-sm text-white">{profile.email}</p>
            </div>
            <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
              <p className="metric-label">Name</p>
              <p className="mt-2 text-sm text-white">{profile.name}</p>
            </div>
          </div>
          <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
            <p className="metric-label">Camera</p>
            <p className="mt-2 text-sm text-white">{profile.camera_name}</p>
          </div>
          <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
            <p className="metric-label">Session state</p>
            <p className="mt-2 text-sm text-slate-300">This profile is the email target for high-threat alerts and the default camera owner in the dashboard.</p>
          </div>
          <div className="flex flex-wrap gap-3">
            <a href="/register" className={clsx('control-button')}>Update profile</a>
            <a href="/" className={clsx('control-button', 'bg-cyan-500/15 text-cyan-100')}>Back to dashboard</a>
          </div>
        </>
      ) : null}
    </div>
  );
}
