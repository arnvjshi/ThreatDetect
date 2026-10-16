'use client';

import { useEffect, useMemo, useState } from 'react';

import { StreamMessage } from '../lib/types';
import { ThreatBadge } from './ThreatBadge';

const wsBase = process.env.NEXT_PUBLIC_BACKEND_WS_URL ?? 'ws://localhost:8000';

export function LiveStreamCanvas() {
  const [stream, setStream] = useState<StreamMessage | null>(null);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    const socket = new WebSocket(`${wsBase}/stream`);
    socket.onopen = () => setConnected(true);
    socket.onclose = () => setConnected(false);
    socket.onmessage = (event) => {
      try {
        setStream(JSON.parse(event.data) as StreamMessage);
      } catch {
        // Ignore malformed messages.
      }
    };
    return () => {
      socket.close();
    };
  }, []);

  const frameUrl = useMemo(() => {
    if (!stream?.frame) {
      return '';
    }
    return `data:image/jpeg;base64,${stream.frame}`;
  }, [stream?.frame]);

  return (
    <div className="glass-card subtle-ring overflow-hidden p-4">
      <div className="mb-4 flex items-center justify-between gap-4">
        <div>
          <p className="metric-label">Live stream</p>
          <h2 className="mt-1 text-xl font-semibold text-white">Processed camera feed</h2>
        </div>
        <div className="flex items-center gap-3 text-sm text-slate-300">
          <span className={connected ? 'h-2.5 w-2.5 rounded-full bg-emerald-400' : 'h-2.5 w-2.5 rounded-full bg-slate-500'} />
          <span>{connected ? 'Connected' : 'Disconnected'}</span>
          <ThreatBadge level={stream?.threat_level ?? 'Low'} />
        </div>
      </div>
      <div className="relative overflow-hidden rounded-2xl border border-white/10 bg-black/70">
        {frameUrl ? (
          <img src={frameUrl} alt="Live processed frame" className="h-full w-full object-cover" />
        ) : (
          <div className="flex aspect-video items-center justify-center text-sm text-slate-400">Waiting for stream</div>
        )}
      </div>
      <div className="mt-4 grid gap-3 text-sm text-slate-300 sm:grid-cols-4">
        <div className="rounded-xl border border-white/10 bg-white/5 p-3">
          <div className="metric-label">Anomaly</div>
          <div className="metric-value mt-1 text-xl">{stream?.anomaly_score?.toFixed(2) ?? '0.00'}</div>
        </div>
        <div className="rounded-xl border border-white/10 bg-white/5 p-3">
          <div className="metric-label">Audio Level</div>
          <div className="mt-2 h-4 w-full overflow-hidden rounded-full bg-black/40">
            <div 
              className="h-full bg-emerald-400 transition-all duration-100 ease-linear" 
              style={{ width: `${Math.min(100, (stream?.audio_level ?? 0) / 100)}%` }} 
            />
          </div>
        </div>
        <div className="rounded-xl border border-white/10 bg-white/5 p-3 sm:col-span-2">
          <div className="metric-label">Live Transcript</div>
          <div className="mt-1 max-h-16 overflow-y-auto text-xs italic text-slate-400">
            {stream?.audio_transcription || "Listening..."}
          </div>
        </div>
        <div className="rounded-xl border border-white/10 bg-white/5 p-3 sm:col-span-4">
          <div className="metric-label">Detected objects</div>
          <div className="mt-2 flex flex-wrap gap-2">
            {(stream?.detections ?? []).slice(0, 5).map((detection) => (
              <span key={`${detection.label}-${detection.x1}-${detection.y1}`} className="rounded-full border border-white/10 bg-black/30 px-3 py-1 text-xs text-slate-200">
                {detection.label}
              </span>
            ))}
            {(!stream?.detections || stream.detections.length === 0) && <span className="text-slate-500">No detections yet</span>}
          </div>
        </div>
      </div>
    </div>
  );
}
