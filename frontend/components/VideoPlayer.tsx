import { getBackendHttpUrl } from '@/lib/api';

function resolveVideoSrc(src: string): string {
  if (!src) {
    return '';
  }
  if (src.startsWith('http://') || src.startsWith('https://')) {
    return src;
  }
  const backendUrl = getBackendHttpUrl();
  if (src.startsWith('/clips/')) {
    return `${backendUrl}${src}`;
  }

  // Handle legacy stored values like "storage\\clips\\<id>.mp4".
  const segments = src.split(/[/\\]/).filter(Boolean);
  const fileName = segments.at(-1);
  if (!fileName) {
    return src;
  }
  return `${backendUrl}/clips/${fileName}`;
}

export function VideoPlayer({ src }: Readonly<{ src: string }>) {
  const resolvedSrc = resolveVideoSrc(src);
  return (
    <video className="aspect-video w-full rounded-2xl border border-white/10 bg-black/60 shadow-glass" controls playsInline preload="metadata" src={resolvedSrc}>
      <track kind="captions" label="English captions" srcLang="en" default />
      Your browser does not support the video element.
    </video>
  );
}
