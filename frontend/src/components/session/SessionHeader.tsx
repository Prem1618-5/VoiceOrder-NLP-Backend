/* ── SessionHeader — Context bar at top of session content ──────────────── */

import { useEffect, useState, useCallback } from 'react';

interface SessionHeaderProps {
  sessionId: string;
  turn: number;
  expiresAt: Date | null;
  status: 'idle' | 'active' | 'closed';
  onClose: () => void;
}

function computeMinutesLeft(expiresAt: Date | null): number | null {
  if (!expiresAt) return null;
  const diff = expiresAt.getTime() - Date.now();
  return diff > 0 ? Math.ceil(diff / 60_000) : 0;
}

export default function SessionHeader({
  sessionId,
  turn,
  expiresAt,
  status,
  onClose,
}: SessionHeaderProps) {
  const [minutesLeft, setMinutesLeft] = useState<number | null>(() =>
    computeMinutesLeft(expiresAt),
  );

  const tick = useCallback(() => {
    setMinutesLeft(computeMinutesLeft(expiresAt));
  }, [expiresAt]);

  useEffect(() => {
    tick();
    const id = setInterval(tick, 60_000);
    return () => clearInterval(id);
  }, [tick]);

  return (
    <div
      className="bg-white border border-[#E2E8F0] rounded-xl overflow-hidden flex items-center"
      role="banner"
      aria-label="Session information"
    >
      {/* Left accent bar */}
      <div className="w-[3px] self-stretch bg-[#1C1C1E] shrink-0" />

      {/* Content */}
      <div className="flex flex-1 items-center justify-between px-5 py-3 gap-4">
        {/* Left: session info */}
        <div className="flex flex-col gap-0.5 min-w-0">
          <span className="uppercase tracking-wider text-xs font-semibold text-[#6B7280]">
            Session
          </span>
          <span className="text-sm text-[#6B7280] truncate">
            ID: {sessionId.slice(0, 8)}&hellip; · Turn: {turn}
            {minutesLeft !== null && <> · Expires: {minutesLeft} min</>}
          </span>
        </div>

        {/* Right: status + close */}
        <div className="flex items-center gap-3 shrink-0">
          {/* Status badge */}
          {status === 'active' && (
            <span className="inline-flex items-center rounded-full bg-indigo-50 px-2.5 py-0.5 text-xs font-medium text-indigo-700">
              active
            </span>
          )}
          {status === 'closed' && (
            <span className="inline-flex items-center rounded-full bg-gray-100 px-2.5 py-0.5 text-xs font-medium text-gray-600">
              closed
            </span>
          )}

          {/* Close button */}
          <button
            type="button"
            onClick={onClose}
            disabled={status === 'closed'}
            className="text-sm text-[#DC2626] hover:bg-red-50 rounded px-3 py-1 transition disabled:opacity-40 disabled:cursor-not-allowed"
            aria-label="Close session"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
