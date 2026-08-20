import { notFound } from 'next/navigation';

import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

import { DashboardShell } from '@/components/DashboardShell';
import { DeleteEventButton } from '@/components/DeleteEventButton';
import { VideoPlayer } from '@/components/VideoPlayer';
import { fetchEvent } from '@/lib/api';
import { ThreatBadge } from '@/components/ThreatBadge';
import { formatToIst } from '@/lib/time';

export default async function EventDetailPage({ params }: Readonly<{ params: Promise<{ id: string }> }>) {
  const { id } = await params;
  const event = await fetchEvent(id);
  if (!event) {
    notFound();
  }
  const eventData = event;

  const backendBase = process.env.NEXT_PUBLIC_BACKEND_HTTP_URL ?? 'http://localhost:8000';
  const thumbnailSrc = eventData.thumbnail_url
    ? `${backendBase}${eventData.thumbnail_url}`
    : `${backendBase}/events/${eventData._id}/thumbnail`;

  return (
    <DashboardShell>
      <div className="grid gap-6 xl:grid-cols-[1.4fr_0.9fr]">
        <section className="space-y-6">
          <div className="glass-card subtle-ring p-6">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div className="flex flex-wrap items-center gap-3">
                <ThreatBadge level={eventData.threat_level} />
                <span className="text-xs uppercase tracking-[0.24em] text-slate-400">{formatToIst(eventData.timestamp)} IST</span>
              </div>
              <DeleteEventButton eventId={eventData._id} />
            </div>
            <h1 className="mt-4 text-3xl font-semibold text-white">Event details</h1>
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              className="mt-3 max-w-3xl space-y-3 text-sm leading-6 text-slate-300"
              components={{
                p: ({ children }) => <p className="text-sm leading-6 text-slate-300">{children}</p>,
                strong: ({ children }) => <strong className="font-semibold text-white">{children}</strong>,
                ul: ({ children }) => <ul className="list-disc space-y-2 pl-5">{children}</ul>,
                ol: ({ children }) => <ol className="list-decimal space-y-2 pl-5">{children}</ol>,
                li: ({ children }) => <li className="text-sm leading-6 text-slate-300">{children}</li>,
                a: ({ children, href }) => (
                  <a className="text-slate-100 underline decoration-slate-500 underline-offset-4" href={href}>
                    {children}
                  </a>
                )
              }}
            >
              {eventData.summary}
            </ReactMarkdown>
          </div>
          <img src={thumbnailSrc} alt="Event thumbnail" className="aspect-video w-full rounded-2xl border border-white/10 object-cover shadow-glass" />
          <VideoPlayer src={eventData.video_url} />
        </section>
        <aside className="space-y-6">
          <div className="glass-card subtle-ring p-6">
            <p className="metric-label">Threat score</p>
            <div className="mt-3 text-5xl font-semibold tracking-tight text-white">{eventData.anomaly_score.toFixed(2)}</div>
          </div>
          <div className="glass-card subtle-ring p-6">
            <p className="metric-label">Detected objects</p>
            <div className="mt-4 flex flex-wrap gap-2">
              {eventData.detected_objects.map((object) => (
                <span key={`${object.label}-${object.x1}-${object.y1}`} className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-slate-200">
                  {object.label}
                </span>
              ))}
            </div>
          </div>
          <div className="glass-card subtle-ring p-6">
            <p className="metric-label">Suggested actions</p>
            <div className="mt-4 overflow-hidden rounded-2xl border border-white/10 bg-black/40">
              <img src={thumbnailSrc} alt="Scene thumbnail" className="aspect-video w-full object-cover" />
            </div>
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              className="mt-4 space-y-3 text-sm leading-6 text-slate-300"
              components={{
                p: ({ children }) => <p className="text-sm leading-6 text-slate-300">{children}</p>,
                strong: ({ children }) => <strong className="font-semibold text-white">{children}</strong>,
                ul: ({ children }) => <ul className="list-disc space-y-2 pl-5">{children}</ul>,
                ol: ({ children }) => <ol className="list-decimal space-y-2 pl-5">{children}</ol>,
                li: ({ children }) => <li className="text-sm leading-6 text-slate-300">{children}</li>,
                a: ({ children, href }) => (
                  <a className="text-slate-100 underline decoration-slate-500 underline-offset-4" href={href}>
                    {children}
                  </a>
                )
              }}
            >
              {eventData.escalation_steps}
            </ReactMarkdown>
          </div>
        </aside>
      </div>
    </DashboardShell>
  );
}
