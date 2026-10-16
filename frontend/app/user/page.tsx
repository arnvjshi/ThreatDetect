import type { Metadata } from 'next';
import type { JSX } from 'react';

import { DashboardShell } from '@/components/DashboardShell';
import { UserInfoCard } from '@/components/UserInfoCard';

export const metadata: Metadata = {
  title: 'User Info - ThreatDetect',
  description: 'View the registered alert recipient and camera profile',
};

export default function UserPage(): Readonly<JSX.Element> {
  return (
    <DashboardShell>
      <div className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
        <section className="space-y-6">
          <UserInfoCard />
        </section>

        <aside className="space-y-6">
          <div className="glass-card subtle-ring p-6">
            <p className="metric-label">Account</p>
            <h1 className="mt-2 text-2xl font-semibold text-white">Registered profile</h1>
            <p className="mt-3 text-sm leading-6 text-slate-300">This is the alert target and camera owner used by the dashboard.</p>
          </div>
        </aside>
      </div>
    </DashboardShell>
  );
}
