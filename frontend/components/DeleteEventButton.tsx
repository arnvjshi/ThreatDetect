'use client';

import { useRouter } from 'next/navigation';
import { useState } from 'react';

import { deleteEvent } from '@/lib/api';

type DeleteEventButtonProps = {
  eventId: string;
};

export function DeleteEventButton({ eventId }: DeleteEventButtonProps) {
  const router = useRouter();
  const [isDeleting, setIsDeleting] = useState(false);
  const [error, setError] = useState('');

  const handleDelete = async () => {
    if (isDeleting) {
      return;
    }

    const confirmed = window.confirm('Delete this event? This cannot be undone.');
    if (!confirmed) {
      return;
    }

    setError('');
    setIsDeleting(true);

    try {
      const ok = await deleteEvent(eventId);
      if (!ok) {
        throw new Error('Delete failed');
      }
      router.push('/events');
      router.refresh();
    } catch {
      setError('Unable to delete event. Please try again.');
      setIsDeleting(false);
    }
  };

  return (
    <div className="flex flex-col items-start gap-2">
      <button
        type="button"
        onClick={handleDelete}
        className="rounded-full border border-rose-500/30 bg-rose-500/10 px-4 py-2 text-xs font-semibold uppercase tracking-[0.2em] text-rose-100 transition hover:bg-rose-500/20 disabled:cursor-not-allowed disabled:opacity-60"
        disabled={isDeleting}
      >
        {isDeleting ? 'Deleting...' : 'Delete event'}
      </button>
      {error ? <p className="text-xs text-rose-200/80">{error}</p> : null}
    </div>
  );
}
